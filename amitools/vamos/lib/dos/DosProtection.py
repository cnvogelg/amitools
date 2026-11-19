"""Backward-compatible import location for :class:`DosProtection`.

The canonical implementation now lives in
:mod:`amitools.vamos.handler.protection` because the protection mask is
returned by file system handlers.
"""

from amitools.vamos.handler.protection import DosProtection

__all__ = ["DosProtection"]
