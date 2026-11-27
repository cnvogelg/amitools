"""Shared scaffolding for the ``exec.library`` topic-mixin unit tests.

Each topic test drives a mixin directly, the way ``lib_exec_softint.py`` does,
without building a full ``exec.library``. The helper only provides the state a
mixin reaches for through ``self`` (``ctx``, ``mem``, ``alloc``, ``exec_lib``).
"""

from types import SimpleNamespace

from amitools.vamos.libstructs import ExecLibraryStruct
from amitools.vamos.libtypes import ExecLibrary
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc


def make_exec_lib(mem=None):
    """allocate an ``ExecLibrary`` (lists initialised) in mock memory."""
    if mem is None:
        mem = MockMemory()
    alloc = MemoryAlloc(mem, addr=0x1000, alignment=8)
    struct = alloc.alloc_astruct(ExecLibraryStruct, label="ExecLibrary")
    el = ExecLibrary(mem, struct.addr)
    el.new()
    return mem, alloc, el


class ExecHost:
    """minimal host combining a topic mixin with the shared exec state."""

    def __init__(
        self, mem, alloc, exec_lib, cpu=None, task=None, scheduler=None, machine=None
    ):
        self.mem = mem
        self.alloc = alloc
        self.exec_lib = exec_lib
        self._added_tasks = []
        self.ctx = SimpleNamespace(
            mem=mem,
            alloc=alloc,
            cpu=cpu if cpu is not None else MockCPU(),
            task=task,
            scheduler=scheduler,
            machine=machine,
        )
