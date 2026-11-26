"""Minimal ``workbench.library`` implementation.

vamos has no Workbench, so the GUI functions cannot display anything.  Only
``WBInfo`` is needed by a CLI program (``C:WBInfo``): it is reported as
successful so the command finishes instead of failing.  The remaining functions
are left to the generic "missing" stubs.
"""

from amitools.vamos.libcore import LibImpl


class WorkbenchLibrary(LibImpl):
    def WBInfo(self, ctx, lock, name, screen):
        # The info window requires a running Workbench.  Report success so
        # callers such as ``C:WBInfo`` complete normally.
        return 1
