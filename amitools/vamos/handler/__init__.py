"""AmigaDOS-style file system handler API.

See :mod:`amitools.vamos.handler.base` for the API and
:mod:`amitools.vamos.handler.mgr` for the volume/device registry.
"""

from .base import (
    Handler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
)
from .mgr import HandlerManager
from .filesys import HostFileSysHandler
from .protection import DosProtection

__all__ = [
    "Handler",
    "HandlerError",
    "HandlerFile",
    "HandlerFileInfo",
    "HandlerInfoData",
    "HandlerLock",
    "HandlerManager",
    "HostFileSysHandler",
    "DosProtection",
    "MODE_NEWFILE",
    "MODE_OLDFILE",
    "MODE_READWRITE",
]
