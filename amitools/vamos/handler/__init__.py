"""AmigaDOS-style file system handler API.

See :mod:`amitools.vamos.handler.base` for the API and
:mod:`amitools.vamos.handler.mgr` for the volume/device registry.
"""

from .base import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    DeviceLock,
    Handler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
)
from .adfs import AdfsHandler, open_adfs_blkdev
from .console import ConsoleHandler
from .decode import PacketDecoder
from .dispatch import HandlerDispatcher
from .dospkt import DosPktHandler
from .filesys import HostFileSysHandler
from .mgr import HandlerManager, build_handler_manager
from .nil import NilHandler
from .packet import PacketFile, PacketHandler, PacketLock
from .protection import DosProtection
from .ram import RamHandler
from .registry import HandlerRegistry, default_registry

__all__ = [
    "MODE_NEWFILE",
    "MODE_OLDFILE",
    "MODE_READWRITE",
    "AdfsHandler",
    "ConsoleHandler",
    "DeviceLock",
    "DosProtection",
    "DosPktHandler",
    "Handler",
    "HandlerDispatcher",
    "HandlerError",
    "HandlerFile",
    "HandlerFileInfo",
    "HandlerInfoData",
    "HandlerLock",
    "HandlerManager",
    "HandlerRegistry",
    "HostFileSysHandler",
    "NilHandler",
    "PacketDecoder",
    "PacketFile",
    "PacketHandler",
    "PacketLock",
    "RamHandler",
    "build_handler_manager",
    "default_registry",
    "open_adfs_blkdev",
]
