"""AmigaDOS-style file system handler API.

See :mod:`amitools.vamos.handler.base` for the API and
:mod:`amitools.vamos.handler.mgr` for the volume/device registry.
"""

from .base import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    Handler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
)
from .console import ConsoleHandler
from .filesys import HostFileSysHandler
from .mgr import HandlerManager, build_handler_manager
from .nil import NilHandler
from .protection import DosProtection
from .ram import RamHandler
from .registry import HandlerRegistry, default_registry

__all__ = [
    "MODE_NEWFILE",
    "MODE_OLDFILE",
    "MODE_READWRITE",
    "ConsoleHandler",
    "DosProtection",
    "Handler",
    "HandlerError",
    "HandlerFile",
    "HandlerFileInfo",
    "HandlerInfoData",
    "HandlerLock",
    "HandlerManager",
    "HandlerRegistry",
    "HostFileSysHandler",
    "NilHandler",
    "RamHandler",
    "build_handler_manager",
    "default_registry",
]
