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
from .filesys import HostFileSysHandler
from .mgr import HandlerManager, build_handler_manager
from .protection import DosProtection
from .registry import HandlerRegistry, default_registry

__all__ = [
    "MODE_NEWFILE",
    "MODE_OLDFILE",
    "MODE_READWRITE",
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
    "build_handler_manager",
    "default_registry",
]
