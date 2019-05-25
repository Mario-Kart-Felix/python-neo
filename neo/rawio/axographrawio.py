# -*- coding: utf-8 -*-
"""
................
"""
from __future__ import unicode_literals, print_function, division, absolute_import

from .baserawio import (BaseRawIO, _signal_channel_dtype, _unit_channel_dtype,
                        _event_channel_dtype)

from io import open, BufferedReader
from struct import unpack, calcsize

import numpy as np


class AxographRawIO(BaseRawIO):
    """
    ...................
    """
    name = 'AxographRawIO'
    description = 'This IO reads .axgd/.axgx files created with AxoGraph'
    extensions = ['axgd', 'axgx']
    rawmode = 'one-file'

    def __init__(self, filename, force_single_segment=False):
        BaseRawIO.__init__(self)
        self.filename = filename
        self.force_single_segment = force_single_segment

    def _parse_header(self):

        self.header = {}

        self._do_the_heavy_lifting()

        if not self.force_single_segment and self._safe_to_treat_as_episodic():
            self.logger.debug('Will treat as episodic')
            self._convert_to_multi_segment()
        else:
            self.logger.debug('Will not treat as episodic')
        self.logger.debug('')

        self._generate_minimal_annotations()

        # TODO fix blk.channel_indexes name, match id to group id?

    def _source_name(self):
        return self.filename

    def _segment_t_start(self, block_index, seg_index):
        # same for all segments
        return self._t_start

    def _segment_t_stop(self, block_index, seg_index):
        # same for all signals in all segments
        t_stop = self._t_start + \
            len(self._raw_signals[seg_index][0]) * self._sampling_period
        return t_stop

    ###
    # signal and channel zone

    def _get_signal_size(self, block_index, seg_index, channel_indexes):
        # same for all signals in all segments
        return len(self._raw_signals[seg_index][0])

    def _get_signal_t_start(self, block_index, seg_index, channel_indexes):
        # same for all signals in all segments
        return self._t_start

    def _get_analogsignal_chunk(self, block_index, seg_index, i_start, i_stop, channel_indexes):
        assert block_index == 0, 'AxoGraph files do not support multi-block, block_index {} out of range'.format(block_index)

        if channel_indexes is None or np.all(channel_indexes == slice(None, None, None)):
            channel_indexes = range(self.signal_channels_count())

        raw_signals = [self._raw_signals[seg_index][channel_index][slice(i_start, i_stop)] for channel_index in channel_indexes]
        raw_signals = np.array(raw_signals).T # reads memmap and loads data into memory -- TODO: transpose without loading?

        return raw_signals

    ###
    # spiketrain and unit zone

    def _spike_count(self, block_index, seg_index, unit_index):
        raise (NotImplementedError)

    def _get_spike_timestamps(self, block_index, seg_index, unit_index, t_start, t_stop):
        raise (NotImplementedError)

    def _rescale_spike_timestamp(self, spike_timestamps, dtype):
        raise (NotImplementedError)

    ###
    # spike waveforms zone

    def _get_spike_raw_waveforms(self, block_index, seg_index, unit_index, t_start, t_stop):
        raise (NotImplementedError)

    ###
    # event and epoch zone

    def _event_count(self, block_index, seg_index, event_channel_index):
        # Retrieve size of either event or epoch channel:
        #   event_channel_index: 0 AxoGraph Tags, 1 AxoGraph Intervals
        # same for all segments -- TODO verify
        return self._raw_event_epoch_timestamps[event_channel_index].size

    def _get_event_timestamps(self, block_index, seg_index, event_channel_index, t_start, t_stop):
        # Retrieve either event or epoch data, unscaled:
        #   event_channel_index: 0 AxoGraph Tags, 1 AxoGraph Intervals
        # same for all segments -- TODO verify
        timestamps = self._raw_event_epoch_timestamps[event_channel_index]
        durations = self._raw_event_epoch_durations[event_channel_index]
        labels = self._event_epoch_labels[event_channel_index]
        # TODO filter by time
        return timestamps, durations, labels

    def _rescale_event_timestamp(self, event_timestamps, dtype):
        # Scale either event or epoch start times to seconds
        event_times = event_timestamps.astype(dtype) * self._sampling_period # t_start shouldn't be added
        return event_times

    def _rescale_epoch_duration(self, raw_duration, dtype):
        # Scale epoch duration times to seconds
        epoch_durations = raw_duration.astype(dtype) * self._sampling_period # t_start shouldn't be added
        return epoch_durations

    ###
    # multi-segment zone

    def _safe_to_treat_as_episodic(self):

        # The purpose of this fuction is to determine if the file contains any
        # irregularities in its grouping of traces such that it cannot be
        # treated as episodic. Even "continuous" recordings can be treated as
        # single-episode recordings and should be identified as safe by this
        # function. Recordings in which the user has changed groupings to
        # create irregularities should be caught by this function.

        # First check: Old AxoGraph file formats do not contain enough metadata
        # to know for certain that the file is episodic.
        if self.info['format_ver'] < 3:
            self.logger.debug('Cannot treat as episodic because old format contains insufficient metadata')
            return False

        # Second check: If the file is episodic, groups of traces should all
        # contain the same number of traces, one for each episode. This is
        # generally true of "continuous" (single-episode) recordings as well,
        # which normally have 1 trace per group.
        group_id_to_col_indexes = {}
        for group_id, group_header in self.info['group_header_info_list'].items():
            col_indexes = []
            for trace_index, trace_header in self.info['trace_header_info_list'].items():
                if trace_header['group_id_for_this_trace'] == group_id:
                    col_indexes.append(trace_header['y_index'])
            group_id_to_col_indexes[group_id] = col_indexes
        n_traces_by_group = {k:len(v) for k,v in group_id_to_col_indexes.items()}
        all_groups_have_same_number_of_traces = len(np.unique(list(n_traces_by_group.values()))) == 1

        if not all_groups_have_same_number_of_traces:
            self.logger.debug('Cannot treat as episodic because groups differ in number of traces')
            return False

        # Third check: The number of traces in each group should equal n_episodes.
        n_traces_per_group = np.unique(list(n_traces_by_group.values()))
        if n_traces_per_group != self.info['n_episodes']:
            self.logger.debug('Cannot treat as episodic because n_episodes does not match number of traces per group')
            return False

        # Fourth check: If the file is episodic, all traces within a group
        # should have identical signal channel parameters (e.g., name, units)
        # except for their unique ids. This too is generally true of "continuous"
        # (single-episode) files, which normally have 1 trace per group.
        signal_channels_with_ids_dropped = self.header['signal_channels'][[n for n in self.header['signal_channels'].dtype.names if n != 'id']]
        group_has_uniform_signal_parameters = {}
        for group_id, col_indexes in group_id_to_col_indexes.items():
            signal_params_for_group = np.array(signal_channels_with_ids_dropped[np.array(col_indexes)-1]) # subtract 1 because time is missing from signal_channels
            group_has_uniform_signal_parameters[group_id] = len(np.unique(signal_params_for_group)) == 1
        all_groups_have_uniform_signal_parameters = np.all(list(group_has_uniform_signal_parameters.values()))

        if not all_groups_have_uniform_signal_parameters:
            self.logger.debug('Cannot treat as episodic because some groups have heterogeneous signal parameters')
            return False

        # all checks passed
        self.logger.debug('Can treat as episodic')
        return True

    def _convert_to_multi_segment(self):
        # Reshape signal headers and signal data for episodic data

        self.header['nb_segment'] = [self.info['n_episodes']]

        # drop repeated signal headers
        self.header['signal_channels'] = self.header['signal_channels'].reshape(self.info['n_episodes'], -1)[0]

        # reshape signal memmap list
        new_sigs_memmap = []
        n_traces_per_group = len(self.header['signal_channels'])
        sigs_memmap = self._raw_signals[0]
        for first_index in np.arange(0, len(sigs_memmap), n_traces_per_group):
            new_sigs_memmap.append(sigs_memmap[first_index:first_index+n_traces_per_group])
        self._raw_signals = new_sigs_memmap

        self.logger.debug('New number of segments: {}'.format(self.info['n_episodes']))

        return



    def _do_the_heavy_lifting(self):

        with open(self.filename, 'rb') as fid:
            f = StructFile(fid)

            self.logger.debug('filename: {}'.format(self.filename))
            self.logger.debug('')

            # the first 4 bytes are always a 4-character file type identifier
            # - for early versions of AxoGraph, this identifier was 'AxGr'
            # - starting with AxoGraph X, the identifier is 'axgx'
            header_id = f.read(4).decode('utf-8')
            assert header_id in ['AxGr', 'axgx'], 'not an AxoGraph binary file! "{}"'.format(self.filename)

            self.logger.debug('header_id: {}'.format(header_id))

            # the next two numbers store the format version number and the number of data columns to follow
            # - for 'AxGr' files, these numbers are 2-byte unsigned short ints
            # - for 'axgx' files, these numbers are 4-byte long ints
            # - the 4-character identifier changed from 'AxGr' to 'axgx' with format version 3
            if header_id == 'AxGr':
                format_ver, n_cols = f.read_f('HH')
                assert format_ver == 1 or format_ver == 2, 'mismatch between header identifier "{}" and format version "{}"!'.format(header_id, format_ver)
            elif header_id == 'axgx':
                format_ver, n_cols = f.read_f('ll')
                assert format_ver >= 3, 'mismatch between header identifier "{}" and format version "{}"!'.format(header_id, format_ver)
            else:
                raise NotImplementedError('unimplemented file header identifier "{}"!'.format(header_id))

            self.logger.debug('format_ver: {}'.format(format_ver))
            self.logger.debug('n_cols: {}'.format(n_cols))
            self.logger.debug('')


            sigs_memmap = []
            sig_channels = []
            for i in range(n_cols):

                self.logger.debug('== COLUMN INDEX {} =='.format(i))

                ##############################################
                # NUMBER OF DATA POINTS IN COLUMN

                n_points = f.read_f('l')

                self.logger.debug('n_points: {}'.format(n_points))

                ##############################################
                # COLUMN TYPE

                # depending on the format version, data columns may have a type
                # - prior to verion 3, column types did not exist and data was stored in a fixed pattern
                # - beginning with version 3, several data types are available as documented in AxoGraph_ReadWrite.h
                if format_ver == 1 or format_ver == 2:
                    col_type = None
                elif format_ver >= 3:
                    col_type = f.read_f('l')
                else:
                    raise NotImplementedError('unimplemented file format version "{}"!'.format(format_ver))

                self.logger.debug('col_type: {}'.format(col_type))

                ##############################################
                # COLUMN NAME AND UNITS

                # depending on the format version, column titles are stored differently
                # - prior to version 3, column titles were stored as fixed-length 80-byte Pascal strings
                # - beginning with version 3, column titles are stored as variable-length strings (see StructFile.read_string)
                if format_ver == 1 or format_ver == 2:
                    title = f.read_f('80p').decode('utf-8')
                elif format_ver >= 3:
                    title = f.read_f('S')
                else:
                    raise NotImplementedError('unimplemented file format version "{}"!'.format(format_ver))

                self.logger.debug('title: {}'.format(title))

                # units are given in parentheses at the end of a column title, unless units are absent
                if len(title.split()) > 0 and title.split()[-1][0] == '(' and title.split()[-1][-1] == ')':
                    name = ' '.join(title.split()[:-1])
                    units = title.split()[-1].strip('()')
                else:
                    name = title
                    units = ''

                self.logger.debug('name: {}'.format(name))
                self.logger.debug('units: {}'.format(units))

                ##############################################
                # READ COLUMN

                if format_ver == 1:

                    # for format version 1, all columns are arrays of floats

                    dtype = 'f'
                    gain, offset = 1, 0 # data is neither scaled nor off-set

                    if i == 0:

                        # there is no guarantee that this time column is regularly sampled, and
                        # in fact the test file has slight variations in the intervals between
                        # samples (due to numerical imprecision, probably), so technically an
                        # IrregularlySampledSignal is needed here, but I'm going to cheat by
                        # assuming regularity

                        array = np.memmap(self.filename, mode='r', dtype=f.byte_order+dtype, offset=f.tell(), shape=n_points)
                        f.seek(array.nbytes, 1) # advance the file position to after the data array

                        first_value, increment = array[0], np.median(np.diff(array)) # here's the cheat

                        self.logger.debug('interval: {}, freq: {}'.format(increment, 1/increment))
                        self.logger.debug('start: {}, end: {}'.format(first_value, first_value + increment * (n_points-1)))

                        # assume this is the time column
                        t_start, sampling_period = first_value, increment

                        self.logger.debug('')

                        continue # skip saving memmap and header info for time array

                elif format_ver == 2:

                    # for format version 2, the first column is a "series" of regularly spaced values
                    # specified merely by a first value and an increment, and all subsequent columns
                    # are arrays of shorts with a scaling factor

                    if i == 0:

                        # series
                        first_value, increment = f.read_f('ff')

                        self.logger.debug('interval: {}, freq: {}'.format(increment, 1/increment))
                        self.logger.debug('start: {}, end: {}'.format(first_value, first_value + increment * (n_points-1)))

                        # assume this is the time column
                        t_start, sampling_period = first_value, increment

                        self.logger.debug('')

                        continue # skip saving memmap and header info for time array

                    else:

                        # scaled short
                        dtype = 'h'
                        gain, offset = f.read_f('f'), 0 # data is scaled without offset

                elif format_ver >= 3:

                    # for format versions 3 and later, the column type determines how the data should be read
                    # - column types 1, 2, 3, and 8 are not defined in AxoGraph_ReadWrite.h
                    # - column type 9 is different from the others in that it represents regularly spaced values
                    #   (such as times at a fixed frequency) specified by a first value and an increment,
                    #   without storing a large data array

                    if col_type is 9:

                        # series
                        first_value, increment = f.read_f('dd')

                        self.logger.debug('interval: {}, freq: {}'.format(increment, 1/increment))
                        self.logger.debug('start: {}, end: {}'.format(first_value, first_value + increment * (n_points-1)))

                        if i == 0:

                            # assume this is the time column
                            t_start, sampling_period = first_value, increment

                            self.logger.debug('')

                            continue # skip saving memmap and header info for time array

                        else:

                            raise NotImplementedError('series data are supported only for the first data column (time)!')

                    elif col_type is 4:

                        # short
                        dtype = 'h'
                        gain, offset = 1, 0 # data is neither scaled nor off-set

                    elif col_type is 5:

                        # long
                        dtype = 'l'
                        gain, offset = 1, 0 # data is neither scaled nor off-set

                    elif col_type is 6:

                        # float
                        dtype = 'f'
                        gain, offset = 1, 0 # data is neither scaled nor off-set

                    elif col_type is 7:

                        # double
                        dtype = 'd'
                        gain, offset = 1, 0 # data is neither scaled nor off-set

                    elif col_type is 10:

                        # scaled short
                        dtype = 'h'
                        gain, offset = f.read_f('dd') # data is scaled with offset

                    else:

                        raise NotImplementedError('unimplemented column type "{}"!'.format(col_type))

                else:

                    raise NotImplementedError('unimplemented file format version "{}"!'.format(format_ver))

                array = np.memmap(self.filename, mode='r', dtype=f.byte_order+dtype, offset=f.tell(), shape=n_points)
                f.seek(array.nbytes, 1) # advance the file position to after the data array

                self.logger.debug('gain: {}, offset: {}'.format(gain, offset))
                self.logger.debug('initial data: {}'.format(array[:5] * gain + offset))

                channel_id = i # TODO: what is this Neo thing for?
                group_id = 0   # TODO: what is this Neo thing for?
                channel_info = (name, channel_id, 1/sampling_period, f.byte_order+dtype, units, gain, offset, group_id) # follows _signal_channel_dtype

                self.logger.debug('channel_info: {}'.format(channel_info))
                self.logger.debug('')

                sigs_memmap.append(array)
                sig_channels.append(channel_info)


            if format_ver == 1 or format_ver == 2:

                # for format versions 1 and 2, metadata like graph display information
                # was stored separately in the "resource fork" of the file, so there
                # is nothing more to do here, and the rest of the file is empty

                rest_of_the_file = f.read()
                assert rest_of_the_file == b''

                raw_event_timestamps = []
                raw_epoch_timestamps = []
                raw_epoch_durations = []
                event_labels = []
                epoch_labels = []

            elif format_ver >= 3:

                # for format versions 3 and later, there is a lot more!

                self.logger.debug('== COMMENT ==')

                comment = f.read_f('S')

                self.logger.debug(comment if comment else 'no comment!')
                self.logger.debug('')


                self.logger.debug('== NOTES ==')

                notes = f.read_f('S')

                self.logger.debug(notes if notes else 'no notes!')
                self.logger.debug('')


                self.logger.debug('== TRACES ==')

                n_traces = f.read_f('l')

                self.logger.debug('n_traces: {}'.format(n_traces))
                self.logger.debug('')

                trace_header_info_list = {}
                group_ids = []
                for i in range(n_traces):

                    self.logger.debug('== TRACE #{} =='.format(i+1)) # AxoGraph traces are 1-indexed in GUI

                    trace_header_info = {}

                    if format_ver < 6:
                        # before format version 6, there was only one version of the
                        # header, and version numbers were not provided
                        trace_header_info['trace_header_version'] = 1
                    else:
                        # for format versions 6 and later, the header version must be read
                        trace_header_info['trace_header_version'] = f.read_f('l')

                    if trace_header_info['trace_header_version'] == 1:
                        TraceHeaderDescription = TraceHeaderDescriptionV1
                    elif trace_header_info['trace_header_version'] == 2:
                        TraceHeaderDescription = TraceHeaderDescriptionV2
                    else:
                        raise NotImplementedError('unimplemented trace header version "{}"!'.format(trace_header_info['trace_header_version']))

                    for key, fmt in TraceHeaderDescription:
                        trace_header_info[key] = f.read_f(fmt)
                    trace_header_info_list[i+1] = trace_header_info # AxoGraph traces are 1-indexed in GUI
                    group_ids.append(trace_header_info['group_id_for_this_trace'])

                    self.logger.debug(trace_header_info)
                    self.logger.debug('')


                self.logger.debug('== GROUPS ==')

                n_groups = f.read_f('l')
                group_ids = np.sort(list(set(group_ids))) # remove duplicates and sort
                assert n_groups == len(group_ids), 'expected group_ids to have length {}: {}'.format(n_groups, group_ids)

                self.logger.debug('n_groups: {}'.format(n_groups))
                self.logger.debug('group_ids: {}'.format(group_ids))
                self.logger.debug('')

                group_header_info_list = {}
                for i in group_ids:

                    self.logger.debug('== GROUP #{} =='.format(i)) # AxoGraph groups are 0-indexed in GUI

                    group_header_info = {}

                    if format_ver < 6:
                        # before format version 6, there was only one version of the
                        # header, and version numbers were not provided
                        group_header_info['group_header_version'] = 1
                    else:
                        # for format versions 6 and later, the header version must be read
                        group_header_info['group_header_version'] = f.read_f('l')

                    if group_header_info['group_header_version'] == 1:
                        GroupHeaderDescription = GroupHeaderDescriptionV1
                    else:
                        raise NotImplementedError('unimplemented group header version "{}"!'.format(group_header_info['group_header_version']))

                    for key, fmt in GroupHeaderDescription:
                        group_header_info[key] = f.read_f(fmt)
                    group_header_info_list[i] = group_header_info # AxoGraph groups are 0-indexed in GUI

                    self.logger.debug(group_header_info)
                    self.logger.debug('')


                self.logger.debug('>> UNKNOWN 1 <<')

                unknowns = f.read_f('9l') # 36 bytes of undeciphered data (types here are guesses)

                self.logger.debug(unknowns)
                self.logger.debug('')


                self.logger.debug('== EPISODES ==')

                episodes_in_review = []
                n_episodes = f.read_f('l')
                for i in range(n_episodes):
                    episode_bool = f.read_f('Z')
                    if episode_bool:
                        episodes_in_review.append(i+1)

                self.logger.debug('n_episodes: {}'.format(n_episodes))
                self.logger.debug('episodes_in_review: {}'.format(episodes_in_review))

                if format_ver == 5:

                    # undeciphered data
                    old_unknown_episode_list = []
                    n_episodes2 = f.read_f('l')
                    for i in range(n_episodes2):
                        episode_bool = f.read_f('Z')
                        if episode_bool:
                            old_unknown_episode_list.append(i+1)

                    self.logger.debug('old_unknown_episode_list: {}'.format(old_unknown_episode_list))
                    if n_episodes2 != n_episodes:
                        self.logger.debug('n_episodes2 ({}) and n_episodes ({}) differ!'.format(n_episodes2, n_episodes))

                # undeciphered data
                unknown_episode_list = []
                n_episodes3 = f.read_f('l')
                for i in range(n_episodes3):
                    episode_bool = f.read_f('Z')
                    if episode_bool:
                        unknown_episode_list.append(i+1)

                self.logger.debug('unknown_episode_list: {}'.format(unknown_episode_list))
                if n_episodes3 != n_episodes:
                    self.logger.debug('n_episodes3 ({}) and n_episodes ({}) differ!'.format(n_episodes3, n_episodes))

                masked_episodes = []
                n_episodes4 = f.read_f('l')
                for i in range(n_episodes4):
                    episode_bool = f.read_f('Z')
                    if episode_bool:
                        masked_episodes.append(i+1)

                self.logger.debug('masked_episodes: {}'.format(masked_episodes))
                if n_episodes4 != n_episodes:
                    self.logger.debug('n_episodes4 ({}) and n_episodes ({}) differ!'.format(n_episodes4, n_episodes))
                self.logger.debug('')


                self.logger.debug('>> UNKNOWN 2 <<')

                unknowns = f.read_f('d 9l d 4l') # 68 bytes of undeciphered data (types here are guesses)

                self.logger.debug(unknowns)
                self.logger.debug('')


                if format_ver >= 6:
                    font_categories = ['axis titles', 'axis labels (ticks)', 'notes', 'graph title']
                else:
                    font_categories = ['everything (?)'] # would need an old version of AxoGraph to determine how it used these settings

                font_settings_info_list = {}
                for i in font_categories:

                    self.logger.debug('== FONT SETTINGS FOR {} =='.format(i))

                    font_settings_info = {}
                    for key, fmt in FontSettingsDescription:
                        font_settings_info[key] = f.read_f(fmt)

                    # I don't know why two arbitrary values were selected to
                    # represent this switch, but it seems they were
                    assert font_settings_info['setting1'] in [FONT_BOLD, FONT_NOT_BOLD], \
                        'expected setting1 ({}) to have value FONT_BOLD ({}) or FONT_NOT_BOLD ({})'.format(font_settings_info['setting1'], FONT_BOLD, FONT_NOT_BOLD)

                    font_settings_info['size'] = font_settings_info['size'] / 10.0 # size is stored 10 times bigger than real value
                    font_settings_info['bold'] = bool(font_settings_info['setting1'] == FONT_BOLD)
                    font_settings_info['italics'] = bool(font_settings_info['setting2'] & FONT_ITALICS)
                    font_settings_info['underline'] = bool(font_settings_info['setting2'] & FONT_UNDERLINE)
                    font_settings_info['strikeout'] = bool(font_settings_info['setting2'] & FONT_STRIKEOUT)
                    font_settings_info_list[i] = font_settings_info

                    self.logger.debug(font_settings_info)
                    self.logger.debug('')


                self.logger.debug('== X-AXIS SETTINGS ==')

                x_axis_settings_info = {}
                for key, fmt in XAxisSettingsDescription:
                    x_axis_settings_info[key] = f.read_f(fmt)

                self.logger.debug(x_axis_settings_info)
                self.logger.debug('')


                self.logger.debug('>> UNKNOWN 3 <<')

                unknowns = f.read_f('8l 3d 13l') # 108 bytes of undeciphered data (types here are guesses)

                self.logger.debug(unknowns)
                self.logger.debug('')


                self.logger.debug('=== EVENTS ===')

                n_events, n_events_again = f.read_f('ll')

                self.logger.debug('n_events: {}'.format(n_events))

                raw_event_timestamps = []
                event_labels = []
                for i in range(n_events_again):
                    event_index = f.read_f('l')
                    raw_event_timestamps.append(event_index)
                n_events_yet_again = f.read_f('l')
                for i in range(n_events_yet_again):
                    title = f.read_f('S')
                    event_labels.append(title)

                event_list = []
                for event_label, event_index in zip(event_labels, raw_event_timestamps):
                    event_time = event_index * sampling_period # t_start shouldn't be added
                    event_list.append({'title': event_label, 'time': event_time})
                for event in event_list:
                    self.logger.debug(event)
                self.logger.debug('')


                self.logger.debug('>> UNKNOWN 4 <<')

                unknowns = f.read_f('7l') # 28 bytes of undeciphered data (types here are guesses)

                self.logger.debug(unknowns)
                self.logger.debug('')


                self.logger.debug('=== EPOCHS ===')

                n_epochs = f.read_f('l')

                self.logger.debug('n_epochs: {}'.format(n_epochs))

                epoch_list = []
                for i in range(n_epochs):
                    epoch_info = {}
                    for key, fmt in EpochInfoDescription:
                        epoch_info[key] = f.read_f(fmt)
                    epoch_list.append(epoch_info)

                raw_epoch_timestamps = []
                raw_epoch_durations = []
                epoch_labels = []
                for epoch in epoch_list:
                    raw_epoch_timestamps.append(epoch['t_start']/sampling_period)
                    raw_epoch_durations.append((epoch['t_stop']-epoch['t_start'])/sampling_period)
                    epoch_labels.append(epoch['title'])
                    self.logger.debug(epoch)
                self.logger.debug('')


                self.logger.debug('>> UNKNOWN 5 (includes y-axis plot ranges) <<')

                rest_of_the_file = f.read()#.decode('utf-8', 'replace') # undeciphered data

                self.logger.debug(rest_of_the_file)

        self.logger.debug('')


        # organize header
        event_channels = []
        event_channels.append(('AxoGraph Tags',      '', 'event')) # follows _event_channel_dtype
        event_channels.append(('AxoGraph Intervals', '', 'epoch')) # follows _event_channel_dtype
        self.header['nb_block'] = 1
        self.header['nb_segment'] = [1]
        self.header['signal_channels'] = np.array(sig_channels, dtype=_signal_channel_dtype)
        self.header['event_channels'] = np.array(event_channels, dtype=_event_channel_dtype)
        self.header['unit_channels'] = np.array([], dtype=_unit_channel_dtype)


        # organize data
        self._sampling_period = sampling_period
        self._t_start = t_start
        self._raw_signals = [sigs_memmap] # first index is seg_index
        self._raw_event_epoch_timestamps = [np.array(raw_event_timestamps), np.array(raw_epoch_timestamps)]
        self._raw_event_epoch_durations = [None, np.array(raw_epoch_durations)]
        self._event_epoch_labels = [np.array(event_labels, dtype='U'), np.array(epoch_labels, dtype='U')]


        # keep other details
        self.info = {}

        self.info['header_id'] = header_id
        self.info['format_ver'] = format_ver

        self.info['t_start'] = t_start
        self.info['sampling_period'] = sampling_period

        if format_ver >= 3:
            self.info['n_cols'] = n_cols
            self.info['n_traces'] = n_traces
            self.info['n_groups'] = n_groups
            self.info['n_episodes'] = n_episodes
            self.info['n_events'] = n_events
            self.info['n_epochs'] = n_epochs

            self.info['comment'] = comment
            self.info['notes'] = notes

            self.info['trace_header_info_list'] = trace_header_info_list
            self.info['group_header_info_list'] = group_header_info_list
            self.info['event_list'] = event_list
            self.info['epoch_list'] = epoch_list

            self.info['episodes_in_review'] = episodes_in_review
            self.info['masked_episodes'] = masked_episodes

            self.info['font_settings_info_list'] = font_settings_info_list
            self.info['x_axis_settings_info'] = x_axis_settings_info


class StructFile(BufferedReader):

    def __init__(self, *args, **kwargs):
        # As far as I've seen, every AxoGraph file uses big-endian encoding,
        # regardless of the system architecture on which it was created, but
        # here I provide means for controlling byte ordering in case a counter
        # example is found.
        self.byte_order = kwargs.pop('byte_order', '>')
        if self.byte_order == '>':
            # big-endian
            self.utf_16_decoder = 'utf-16-be'
        elif self.byte_order == '<':
            # little-endian
            self.utf_16_decoder = 'utf-16-le'
        else:
            # unspecified
            self.utf_16_decoder = 'utf-16'
        super(StructFile, self).__init__(*args, **kwargs)

    def read_and_unpack(self, fmt):
        # Calculate the number of bytes corresponding to the format string, read
        # in that number of bytes, and unpack them according to the format string.
        return unpack(self.byte_order + fmt, self.read(calcsize(self.byte_order + fmt)))

    def read_string(self):
        # The most common string format in AxoGraph files is a variable length
        # string with UTF-16 encoding, preceded by a 4-byte integer (long)
        # specifying the length of the string in bytes. Unlike a Pascal string
        # ('p' format), these strings are not stored in a fixed number of bytes
        # with padding at the end.

        length = self.read_and_unpack('l')[0] # may be -1, 0, or a positive integer
        if length > 0:
            return self.read(length).decode(self.utf_16_decoder)
        else:
            return ''

    def read_bool(self):
        # AxoGraph files encode each boolean as 4-byte integer (long) with value
        # 1 = True, 0 = False
        return bool(self.read_and_unpack('l')[0])

    def read_f(self, fmt, offset=None):
        # A wrapper for read_and_unpack that adds compatibility with two new
        # format strings:
        #     'S': a variable length UTF-16 string, readable with read_string
        #     'Z': a boolean encoded as a 4-byte integer, readable with read_bool
        # This method does not implement support for numbers before the new format
        # strings, such as '2Z' to represent 2 bools (use 'ZZ' instead).

        if offset is not None:
            self.seek(offset)

        # place commas before and after each instance of S or Z
        for special in ['S', 'Z']:
            fmt = fmt.replace(special, ',' + special + ',')

        # split S and Z into isolated strings
        fmt = fmt.split(',')

        # construct a tuple of unpacked data
        data = ()
        for subfmt in fmt:
            if subfmt == 'S':
                data += (self.read_string(),)
            elif subfmt == 'Z':
                data += (self.read_bool(),)
            else:
                data += self.read_and_unpack(subfmt)

        if len(data) == 1:
            return data[0]
        else:
            return data


FONT_BOLD = 75     # mysterious arbitrary constant
FONT_NOT_BOLD = 50 # mysterious arbitrary constant
FONT_ITALICS = 1
FONT_UNDERLINE = 2
FONT_STRIKEOUT = 4

TraceHeaderDescriptionV1 = [
    # these are documented in AxoGraph's developer
    # documentation in AxoGraph_ReadWrite.h
    ('x_index', 'l'),
    ('y_index', 'l'),
    ('err_bar_index', 'l'),
    ('group_id_for_this_trace', 'l'),
    ('hidden', 'Z'), # AxoGraph_ReadWrite.h incorrectly states "shown" instead
    ('min_x', 'd'),
    ('max_x', 'd'),
    ('min_positive_x', 'd'),
    ('x_is_regularly_spaced', 'Z'),
    ('x_increases_monotonically', 'Z'),
    ('x_interval_if_regularly_spaced', 'd'),
    ('min_y', 'd'),
    ('max_y', 'd'),
    ('min_positive_y', 'd'),
    ('trace_color', 'xBBB'),
    ('display_joined_line_plot', 'Z'),
    ('line_thickness', 'd'),
    ('pen_style', 'l'),
    ('display_symbol_plot', 'Z'),
    ('symbol_type', 'l'),
    ('symbol_size', 'l'),
    ('draw_every_data_point', 'Z'),
    ('skip_points_by_distance_instead_of_pixels', 'Z'),
    ('pixels_between_symbols', 'l'),
    ('display_histogram_plot', 'Z'),
    ('histogram_type', 'l'),
    ('histogram_bar_separation', 'l'),
    ('display_error_bars', 'Z'),
    ('display_pos_err_bar', 'Z'),
    ('display_neg_err_bar', 'Z'),
    ('err_bar_width', 'l'),
]

# documented in AxoGraph_ReadWrite.h
TraceHeaderDescriptionV2 = list(TraceHeaderDescriptionV1) # make a copy
TraceHeaderDescriptionV2.insert(3, ('neg_err_bar_index', 'l')) # only difference between versions 1 and 2

GroupHeaderDescriptionV1 = [
    # undocumented and reverse engineered
    ('title', 'S'),
    ('unknown1', 'h'),    # 2 bytes of undeciphered data (types here are guesses)
    ('units', 'S'),
    ('unknown2', 'hll'),  # 10 bytes of undeciphered data (types here are guesses)
]

FontSettingsDescription = [
    # undocumented and reverse engineered
    ('font', 'S'),
    ('size', 'h'),        # this 2-byte integer must be divided by 10 to get the font size
    ('unknown1', '5b'),   # 5 bytes of undeciphered data (types here are guesses)
    ('setting1', 'B'),    # contains bold setting and possibly some other undeciphered data as bitmask
    ('setting2', 'B'),    # contains italics, underline, strikeout settings as bitmask
]

XAxisSettingsDescription = [
    # undocumented and reverse engineered
    ('unknown1', '3l2d'), # 28 bytes of undeciphered data (types here are guesses)
    ('plotted_x_range', 'dd'),
    ('unknown2', 'd'),    # 8 bytes of undeciphered data (types here are guesses)
    ('auto_x_ticks', 'Z'),
    ('x_minor_ticks', 'd'),
    ('x_major_ticks', 'd'),
    ('x_axis_title', 'S'),
    ('unknown3', 'h'),    # 2 bytes of undeciphered data (types here are guesses)
    ('units', 'S'),
    ('unknown4', 'h'),    # 2 bytes of undeciphered data (types here are guesses)
]

EpochInfoDescription = [
    # undocumented and reverse engineered
    ('title', 'S'),
    ('t_start', 'd'),
    ('t_stop', 'd'),
    ('y_pos', 'd'),
]
