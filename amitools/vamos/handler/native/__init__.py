"""Native (68k) AmigaDOS handler support (HANDLER.md step 23).

A ``?handler=native`` volume runs an original AmigaDOS file system handler as
its own task in the emulator and drives it with real ``DosPacket``s.
"""

from .config import NativeConfig
from .handler import NativeHandler, native_factory
from .manager import (
    HandlerProgram,
    NativeHandlerManager,
    build_native_manager,
)

__all__ = [
    "NativeConfig",
    "NativeHandler",
    "native_factory",
    "NativeHandlerManager",
    "HandlerProgram",
    "build_native_manager",
]
