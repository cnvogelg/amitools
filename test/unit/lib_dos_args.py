"""dos.library argument/template functions.

These tests drive the real :class:`DosLibrary` front-ends that delegate to
``amitools.vamos.lib.dos.Args``:

``ReadArgs``, ``FindArg``, ``ReadItem``, ``StrToLong`` and ``FreeArgs``.

``ReadArgs`` reads its command line from the current process' input file, so a
tiny fake file handle is wired into the context. Everything else is plain
``MockMemory`` + ``MemoryAlloc``.
"""

from types import SimpleNamespace

from amitools.vamos.lib.dos.Error import (
    ERROR_BAD_TEMPLATE,
    ERROR_REQUIRED_ARG_MISSING,
)
from amitools.vamos.lib.dos.Item import ItemParser
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import CSourceStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc


class _FakeInput:
    """minimal DOS file handle used as ReadArgs' line source"""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.is_nil = False

    def getc(self):
        if self.pos >= len(self.data):
            return -1
        ch = self.data[self.pos]
        self.pos += 1
        return ch

    def ungetc(self, ch=None):
        if self.pos > 0:
            self.pos -= 1


class _FakeOutput:
    """discard the argument help prompt output"""

    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data


def _make_lib(line=b""):
    mem = MockMemory(size_kib=64)
    cpu = MockCPU()
    alloc = MemoryAlloc(mem)
    process = SimpleNamespace(
        get_input=lambda: _FakeInput(line),
        get_output=lambda: _FakeOutput(),
        this_task=None,
    )
    lib = DosLibrary()
    # only the state Args.py touches is wired up
    lib.alloc = alloc
    lib.mem_allocs = {}
    lib.rdargs = {}
    lib.io_err = 0
    ctx = SimpleNamespace(mem=mem, cpu=cpu, alloc=alloc, process=process)
    return lib, ctx, mem, cpu


def _make_csource(mem, csrc_addr, buf_addr, text):
    mem.w_block(buf_addr, text)
    csrc = CSourceStruct(mem, csrc_addr)
    csrc.CS_Buffer.aptr = buf_addr
    csrc.CS_Length.val = len(text)
    csrc.CS_CurChr.val = 0
    return csrc


# ----- ReadArgs -----


def lib_dos_args_readargs_parse_test():
    lib, ctx, mem, _cpu = _make_lib(b"in.txt out.txt\n")
    mem.w_cstr(0x400, "FROM/A,TO/A,ALL/S")
    array = 0x500
    mem.clear_block(array, 3 * 4, 0)

    rdargs = lib.ReadArgs(ctx, 0x400, array, 0)
    assert rdargs != 0
    assert lib.io_err == 0

    from_ptr = mem.r32(array)
    to_ptr = mem.r32(array + 4)
    assert mem.r_cstr(from_ptr) == "in.txt"
    assert mem.r_cstr(to_ptr) == "out.txt"
    # the /S switch was not given: its slot is left as zero
    assert mem.r32(array + 8) == 0

    # the returned RDArgs is tracked and owns its extra buffer
    struct, own = lib.rdargs[rdargs]
    assert own is True
    assert struct.RDA_Buffer.aptr == from_ptr
    assert struct.RDA_BufSiz.val == len("in.txt") + 1 + len("out.txt") + 1


def lib_dos_args_readargs_switch_test():
    lib, ctx, mem, _cpu = _make_lib(b"in.txt out.txt all\n")
    mem.w_cstr(0x400, "FROM/A,TO/A,ALL/S")
    array = 0x500
    mem.clear_block(array, 3 * 4, 0)

    rdargs = lib.ReadArgs(ctx, 0x400, array, 0)
    assert rdargs != 0
    assert lib.io_err == 0
    assert mem.r_cstr(mem.r32(array)) == "in.txt"
    assert mem.r_cstr(mem.r32(array + 4)) == "out.txt"
    # the /S switch was present -> all bits set
    assert mem.r32(array + 8) == 0xFFFFFFFF


def lib_dos_args_readargs_missing_required_test():
    # an empty command line leaves the /A arguments unset
    lib, ctx, mem, _cpu = _make_lib(b"\n")
    mem.w_cstr(0x400, "FROM/A,TO/A")
    assert lib.ReadArgs(ctx, 0x400, 0x500, 0) == 0
    assert lib.io_err == ERROR_REQUIRED_ARG_MISSING


def lib_dos_args_readargs_bad_template_test():
    # a leading '=' in the input is reported as a bad template
    lib, ctx, mem, _cpu = _make_lib(b"=oops\n")
    mem.w_cstr(0x400, "FROM/A")
    assert lib.ReadArgs(ctx, 0x400, 0x500, 0) == 0
    assert lib.io_err == ERROR_BAD_TEMPLATE


def lib_dos_args_readargs_free_test():
    # FreeArgs releases the RDArgs and the extra buffer ReadArgs allocated
    lib, ctx, mem, _cpu = _make_lib(b"a b\n")
    mem.w_cstr(0x400, "FROM/A,TO/A")
    array = 0x500
    mem.clear_block(array, 2 * 4, 0)

    rdargs = lib.ReadArgs(ctx, 0x400, array, 0)
    assert rdargs != 0
    struct, _own = lib.rdargs[rdargs]
    buf_addr = struct.RDA_Buffer.aptr
    assert buf_addr != 0
    assert buf_addr in lib.mem_allocs

    assert lib.FreeArgs(ctx, rdargs) is None
    assert rdargs not in lib.rdargs
    assert buf_addr not in lib.mem_allocs
    assert len(lib.mem_allocs) == 0


# ----- FindArg -----


def lib_dos_args_findarg_test():
    lib, ctx, mem, _cpu = _make_lib()
    mem.w_cstr(0x400, "FROM/A,TO/A,ALL/S")

    mem.w_cstr(0x500, "to")
    assert lib.FindArg(ctx, 0x400, 0x500) == 1
    # keys are matched case-insensitively
    mem.w_cstr(0x500, "ALL")
    assert lib.FindArg(ctx, 0x400, 0x500) == 2
    # aliases share the same position
    mem.w_cstr(0x400, "FROM/A,TO=DST/A")
    mem.w_cstr(0x500, "dst")
    assert lib.FindArg(ctx, 0x400, 0x500) == 1
    # unknown keyword
    mem.w_cstr(0x400, "FROM/A,TO/A,ALL/S")
    mem.w_cstr(0x500, "missing")
    assert lib.FindArg(ctx, 0x400, 0x500) == -1


# ----- ReadItem -----


def lib_dos_args_readitem_csource_test():
    lib, ctx, mem, _cpu = _make_lib()
    csrc_addr = 0x600
    out = 0x800
    _make_csource(mem, csrc_addr, 0x700, b"hello world\n")

    assert lib.ReadItem(ctx, out, 32, csrc_addr) == ItemParser.ITEM_UNQUOTED
    assert mem.r_cstr(out) == "hello"
    assert lib.ReadItem(ctx, out, 32, csrc_addr) == ItemParser.ITEM_UNQUOTED
    assert mem.r_cstr(out) == "world"
    # end of line -> no more items
    assert lib.ReadItem(ctx, out, 32, csrc_addr) == ItemParser.ITEM_NOTHING


def lib_dos_args_readitem_quoted_test():
    lib, ctx, mem, _cpu = _make_lib()
    csrc_addr = 0x600
    out = 0x800
    _make_csource(mem, csrc_addr, 0x700, b'"quoted arg" rest\n')

    assert lib.ReadItem(ctx, out, 32, csrc_addr) == ItemParser.ITEM_QUOTED
    assert mem.r_cstr(out) == "quoted arg"
    assert lib.ReadItem(ctx, out, 32, csrc_addr) == ItemParser.ITEM_UNQUOTED
    assert mem.r_cstr(out) == "rest"


def lib_dos_args_readitem_edge_test():
    lib, ctx, mem, _cpu = _make_lib()
    csrc_addr = 0x600
    out = 0x800
    _make_csource(mem, csrc_addr, 0x700, b"abc\n")

    # a NULL buffer just returns ITEM_NOTHING
    assert lib.ReadItem(ctx, 0, 32, csrc_addr) == ItemParser.ITEM_NOTHING
    # maxchars == 0 still clears the first byte and reports nothing
    mem.w8(out, 0xAA)
    assert lib.ReadItem(ctx, out, 0, csrc_addr) == ItemParser.ITEM_NOTHING
    assert mem.r8(out) == 0


# ----- StrToLong -----


def lib_dos_args_strtolong_test():
    lib, ctx, mem, _cpu = _make_lib()
    val = 0x500

    mem.w_cstr(0x400, "1234")
    assert lib.StrToLong(ctx, 0x400, val) == 4
    assert mem.r32(val) == 1234

    # a leading sign is consumed
    mem.w_cstr(0x400, "+42")
    assert lib.StrToLong(ctx, 0x400, val) == 3
    assert mem.r32(val) == 42

    # only the leading digits are converted
    mem.w_cstr(0x400, "12abc")
    assert lib.StrToLong(ctx, 0x400, val) == 2
    assert mem.r32(val) == 12


def lib_dos_args_strtolong_fail_test():
    lib, ctx, mem, _cpu = _make_lib()
    val = 0x500
    mem.w32(val, 0xDEADBEEF)

    # no leading digits -> 0 and the target is left untouched
    mem.w_cstr(0x400, "abc")
    assert lib.StrToLong(ctx, 0x400, val) == 0
    assert mem.r32(val) == 0xDEADBEEF
