"""
:mod:`neo.io` provides classes for reading and/or writing
electrophysiological data files.

Note that if the package dependency is not satisfied for one io, it does not
raise an error but a warning.

:attr:`neo.io.iolist` provides a list of successfully imported io classes.

Functions:

.. autofunction:: neo.io.get_io


Classes:

* :attr:`AlphaOmegaIO`
* :attr:`AsciiImageIO`
* :attr:`AsciiSignalIO`
* :attr:`AsciiSpikeTrainIO`
* :attr:`AxographIO`
* :attr:`AxonIO`
* :attr:`BCI2000IO`
* :attr:`BlackrockIO`
* :attr:`BlkIO`
* :attr:`BrainVisionIO`
* :attr:`BrainwareDamIO`
* :attr:`BrainwareF32IO`
* :attr:`BrainwareSrcIO`
* :attr:`ElanIO`
* :attr:`IgorIO`
* :attr:`IntanIO`
* :attr:`MEArecIO`
* :attr:`KlustaKwikIO`
* :attr:`KwikIO`
* :attr:`MicromedIO`
* :attr:`NeoHdf5IO`
* :attr:`NeoMatlabIO`
* :attr:`NestIO`
* :attr:`NeuralynxIO`
* :attr:`NeuroExplorerIO`
* :attr:`NeuroScopeIO`
* :attr:`NeuroshareIO`
* :attr:`NixIO`
* :attr:`NSDFIO`
* :attr:`NWBIO`
* :attr:`OpenEphysIO`
* :attr:`PickleIO`
* :attr:`PlexonIO`
* :attr:`RawBinarySignalIO`
* :attr:`RawMCSIO`
* :attr:`Spike2IO`
* :attr:`SpikeGLXIO`
* :attr:`StimfitIO`
* :attr:`TdtIO`
* :attr:`TiffIO`
* :attr:`WinEdrIO`
* :attr:`WinWcpIO`


.. autoclass:: neo.io.AlphaOmegaIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.AsciiImageIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.AsciiSignalIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.AsciiSpikeTrainIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.AxographIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.AxonIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.BCI2000IO

    .. autoattribute:: extensions

.. autoclass:: neo.io.BlackrockIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.BlkIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.BrainVisionIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.BrainwareDamIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.BrainwareF32IO

    .. autoattribute:: extensions

.. autoclass:: neo.io.BrainwareSrcIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.ElanIO

    .. autoattribute:: extensions

.. .. autoclass:: neo.io.ElphyIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.IgorIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.IntanIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.KlustaKwikIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.KwikIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.MEArecIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.MicromedIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NeoHdf5IO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NeoMatlabIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NestIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NeuralynxIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NeuroExplorerIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NeuroScopeIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NeuroshareIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NixIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NSDFIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.NWBIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.OpenEphysIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.PickleIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.PlexonIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.RawBinarySignalIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.RawMCSIO

    .. autoattribute:: extensions

.. autoclass:: Spike2IO

    .. autoattribute:: extensions

.. autoclass:: SpikeGLXIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.StimfitIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.TdtIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.TiffIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.WinEdrIO

    .. autoattribute:: extensions

.. autoclass:: neo.io.WinWcpIO

    .. autoattribute:: extensions

"""

import os.path

# try to import the neuroshare library.
# if it is present, use the neuroshareapiio to load neuroshare files
# if it is not present, use the neurosharectypesio to load files
try:
    import neuroshare as ns
except ImportError as err:
    from neo.io.neurosharectypesio import NeurosharectypesIO as NeuroshareIO
    # print("\n neuroshare library not found, loading data with ctypes" )
    # print("\n to use the API be sure to install the library found at:")
    # print("\n www.http://pythonhosted.org/neuroshare/")

else:
    from neo.io.neuroshareapiio import NeuroshareapiIO as NeuroshareIO
    # print("neuroshare library successfully imported")
    # print("\n loading with API...")

from neo.io.alphaomegaio import AlphaOmegaIO
from neo.io.asciiimageio import AsciiImageIO
from neo.io.asciisignalio import AsciiSignalIO
from neo.io.asciispiketrainio import AsciiSpikeTrainIO
from neo.io.axographio import AxographIO
from neo.io.axonio import AxonIO
from neo.io.blackrockio import BlackrockIO
from neo.io.blackrockio_v4 import BlackrockIO as OldBlackrockIO
from neo.io.blkio import BlkIO
from neo.io.bci2000io import BCI2000IO
from neo.io.brainvisionio import BrainVisionIO
from neo.io.brainwaredamio import BrainwareDamIO
from neo.io.brainwaref32io import BrainwareF32IO
from neo.io.brainwaresrcio import BrainwareSrcIO
from neo.io.elanio import ElanIO
# from neo.io.elphyio import ElphyIO
from neo.io.exampleio import ExampleIO
from neo.io.igorproio import IgorIO
from neo.io.intanio import IntanIO
from neo.io.klustakwikio import KlustaKwikIO
from neo.io.kwikio import KwikIO
from neo.io.mearecio import MEArecIO
from neo.io.micromedio import MicromedIO
from neo.io.hdf5io import NeoHdf5IO
from neo.io.neomatlabio import NeoMatlabIO
from neo.io.nestio import NestIO
from neo.io.neuralynxio import NeuralynxIO
from neo.io.neuralynxio_v1 import NeuralynxIO as OldNeuralynxIO
from neo.io.neuroexplorerio import NeuroExplorerIO
from neo.io.neuroscopeio import NeuroScopeIO
from neo.io.nixio import NixIO
from neo.io.nixio_fr import NixIO as NixIOFr
from neo.io.nsdfio import NSDFIO
from neo.io.nwbio import NWBIO
from neo.io.openephysio import OpenEphysIO
from neo.io.pickleio import PickleIO
from neo.io.plexonio import PlexonIO
from neo.io.rawbinarysignalio import RawBinarySignalIO
from neo.io.rawmcsio import RawMCSIO
from neo.io.spike2io import Spike2IO
from neo.io.spikeglxio import SpikeGLXIO
from neo.io.stimfitio import StimfitIO
from neo.io.tdtio import TdtIO
from neo.io.tiffio import TiffIO
from neo.io.winedrio import WinEdrIO
from neo.io.winwcpio import WinWcpIO

iolist = [
    AlphaOmegaIO,
    AsciiImageIO,
    AsciiSignalIO,
    AsciiSpikeTrainIO,
    AxographIO,
    AxonIO,
    BCI2000IO,
    BlackrockIO,
    BlkIO,
    BrainVisionIO,
    BrainwareDamIO,
    BrainwareF32IO,
    BrainwareSrcIO,
    ElanIO,
    # ElphyIO,
    ExampleIO,
    IgorIO,
    IntanIO,
    KlustaKwikIO,
    KwikIO,
    MicromedIO,
    NixIO,  # place NixIO before NeoHdf5IO and MEArecIO to make it the default for .h5 files
    MEArecIO,
    NeoHdf5IO,
    NeoMatlabIO,
    NestIO,
    NeuralynxIO,
    NeuroExplorerIO,
    NeuroScopeIO,
    NeuroshareIO,
    NSDFIO,
    NWBIO,
    OpenEphysIO,
    PickleIO,
    PlexonIO,
    RawBinarySignalIO,
    RawMCSIO,
    Spike2IO,
    SpikeGLXIO,
    StimfitIO,
    TdtIO,
    TiffIO,
    WinEdrIO,
    WinWcpIO
]


def get_io(filename, *args, **kwargs):
    """
    Return a Neo IO instance, guessing the type based on the filename suffix.

    The first matching IO that is found will be returned.

    See also: `get_compatible_io_classes`
    """
    extension = os.path.splitext(filename)[1][1:]
    for io_cls in iolist:
        if extension in io_cls.extensions:
            return io_cls(filename, *args, **kwargs)

    raise IOError("File extension %s not registered" % extension)


def get_compatible_io_classes(filename, *args, **kwargs):
    """
    Return a list of all Neo IO instances that support the given filename extension.

    """
    compatible_ios = []
    extension = os.path.splitext(filename)[1][1:]
    for io_cls in iolist:
        if extension in io_cls.extensions:
            try:
                io_obj = io_cls(filename, *args, **kwargs)
            except Exception:
                pass
            else:
                compatible_ios.append(io_obj)
    return compatible_ios
