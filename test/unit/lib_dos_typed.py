"""dos.library typed-arg contract (HANDLER.md step 22a).

Every non-hole fd function of ``DosLibrary`` must declare exactly its fd
arguments, so the lib stub reads them from registers and the method body never
touches ``ctx.cpu`` by hand. The scanner in ``libcore/impl.py`` marks a method
as *raw* (``extra_args is None``) when it declares no extra args for an fd
function that has some; ``libcore/stub.py`` then calls it with only ``ctx``.

This guard asserts the raw set equals the explicit ``_PENDING`` set below, so
each migration batch (22b..22j) must delete its own names. By 22j the set is
empty and no fd method reads ``ctx.cpu`` anymore.
"""

import ast
import inspect

from amitools.fd import read_lib_fd
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libcore.impl import LibImplScanner

# fd functions whose DosLibrary method is still on the manual ``(self, ctx)``
# scheme (it declares no fd args or delegates to a helper that reads ctx.cpu).
# Emptied batch by batch in steps 22b..22j.
_PENDING = {
    "AbortPkt",
    "AddDosEntry",
    "AddPart",
    "AddSegment",
    "AllocDosObject",
    "AssignLock",
    "AttemptLockDosList",
    "CheckSignal",
    "CurrentDir",
    "DateStamp",
    "DateToStr",
    "Delay",
    "DeleteVar",
    "DoPkt",
    "DosGetString",
    "DupLock",
    "DupLockFromFH",
    "ExNext",
    "Examine",
    "ExamineFH",
    "Fault",
    "FilePart",
    "FindArg",
    "FindDosEntry",
    "FindSegment",
    "FindVar",
    "FreeArgs",
    "FreeDeviceProc",
    "FreeDosEntry",
    "FreeDosObject",
    "GetDeviceProc",
    "GetProgramName",
    "GetVar",
    "Info",
    "InternalLoadSeg",
    "IsFileSystem",
    "LoadSeg",
    "Lock",
    "LockDosList",
    "MakeDosEntry",
    "MatchEnd",
    "MatchFirst",
    "MatchNext",
    "MatchPattern",
    "MatchPatternNoCase",
    "NameFromFH",
    "NameFromLock",
    "NextDosEntry",
    "OpenFromLock",
    "ParentDir",
    "ParentOfFH",
    "ParsePattern",
    "ParsePatternNoCase",
    "PathPart",
    "PrintFault",
    "ReadArgs",
    "ReadItem",
    "RemDosEntry",
    "RunCommand",
    "SameLock",
    "SendPkt",
    "SetCurrentDirName",
    "SetFileSysTask",
    "SetIoErr",
    "SetPrompt",
    "SetVar",
    "StrToLong",
    "UnLoadSeg",
    "UnLock",
    "UnLockDosList",
}


def _scan():
    fd = read_lib_fd("dos.library", add_std_calls=False)
    scan = LibImplScanner().scan("dos.library", DosLibrary(), fd)
    return fd, scan


def _raw_names(scan):
    """fd funcs whose method declares no extra args although the fd has some"""
    raw = set()
    for name, impl_func in scan.get_valid_funcs().items():
        if impl_func.fd_func.get_args() and impl_func.extra_args is None:
            raw.add(name)
    return raw


def lib_dos_typed_extra_args_count_test():
    """typed methods declare exactly the fd arg count, raw ones are pending"""
    fd, scan = _scan()
    for name, impl_func in scan.get_valid_funcs().items():
        fd_args = impl_func.fd_func.get_args()
        extra = impl_func.extra_args
        if not fd_args:
            assert extra is None, name
        elif extra is not None:
            assert len(extra) == len(fd_args), name


def lib_dos_typed_pending_set_test():
    """the set of still-raw fd methods equals ``_PENDING`` exactly"""
    _, scan = _scan()
    raw = _raw_names(scan)
    assert raw == _PENDING, "raw=%s\npending=%s" % (
        sorted(raw),
        sorted(_PENDING),
    )


def _cpu_methods():
    """fd-named methods in the DosLibrary source that read ``ctx.cpu``"""
    fd = read_lib_fd("dos.library", add_std_calls=False)
    fd_names = {f.get_name() for f in fd.get_funcs()}
    path = inspect.getsourcefile(DosLibrary)
    with open(path) as fh:
        tree = ast.parse(fh.read())
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "DosLibrary":
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name not in fd_names:
                continue
            for sub in ast.walk(item):
                if (
                    isinstance(sub, ast.Attribute)
                    and sub.attr == "cpu"
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id == "ctx"
                ):
                    found.add(item.name)
                    break
    return found


def lib_dos_typed_no_cpu_reads_test():
    """no fd method reads CPU registers unless it is still pending"""
    cpu = _cpu_methods()
    assert cpu <= _PENDING, "raw cpu readers: %s" % sorted(cpu - _PENDING)
