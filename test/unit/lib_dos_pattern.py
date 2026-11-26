"""dos.library pattern parsing and matching (ParsePattern / MatchPattern) plus
the anchor based directory matcher (MatchFirst / MatchNext / MatchEnd).

The typed front-ends in ``amitools/vamos/lib/DosLibrary.py`` are driven directly
with a ``MockMemory`` and a real ``MemoryAlloc``.  For the matcher the path and
lock managers are replaced by small stand-ins that expose a fixed directory
listing, so the real ``MatchFirstNext`` state machine can be exercised end to
end without a file system.
"""

from types import SimpleNamespace

from amitools.vamos.lib.dos.Error import (
    ERROR_BAD_TEMPLATE,
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_NOT_FOUND,
    NO_ERROR,
)
from amitools.vamos.lib.dos.PatternMatch import pattern_parse
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import AnchorPathStruct
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


def _make_lib():
    """a bare DosLibrary with just the state the pattern/matcher code needs"""
    lib = DosLibrary()
    lib.io_err = NO_ERROR
    lib.matches = {}
    return lib


def _make_ctx(mem, alloc):
    return SimpleNamespace(mem=mem, alloc=alloc, process=None)


# ----- ParsePattern / ParsePatternNoCase -----


def lib_dos_parse_pattern_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = _make_lib()
    ctx = _make_ctx(mem, alloc)
    src = alloc.alloc_memory(64)
    buf = alloc.alloc_memory(128)
    try:
        # wildcards and block expressions are tokenized into control bytes
        for pattern in ("#?", "?", "(a|b)", "~(x)"):
            mem.w_cstr(src.addr, pattern)
            parsed = pattern_parse(pattern, ignore_case=False)
            assert parsed is not None and parsed.has_wildcard
            assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 1
            assert mem.r_cstr(buf.addr) == parsed.pat_str
            assert lib.io_err == NO_ERROR
        # a lone '~' is an ordinary character, not a wildcard
        mem.w_cstr(src.addr, "~")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 0
        assert mem.r_cstr(buf.addr) == "~"
        # a plain name has no wildcard -> 0
        mem.w_cstr(src.addr, "test.o")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 0
        assert mem.r_cstr(buf.addr) == "test.o"
        assert lib.io_err == NO_ERROR
    finally:
        alloc.free_memory(src)
        alloc.free_memory(buf)
    assert alloc.is_all_free()


def lib_dos_parse_pattern_buffer_too_small_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = _make_lib()
    ctx = _make_ctx(mem, alloc)
    src = alloc.alloc_cstr("#?")
    buf = alloc.alloc_memory(1)
    try:
        # the parsed pattern needs len+1 bytes including the NUL terminator
        mem.w8(buf.addr, 0xAB)
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 1) == -1
        assert mem.r8(buf.addr) == 0xAB
    finally:
        alloc.free_cstr(src)
        alloc.free_memory(buf)
    assert alloc.is_all_free()


def lib_dos_parse_pattern_bad_template_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = _make_lib()
    ctx = _make_ctx(mem, alloc)
    src = alloc.alloc_memory(64)
    buf = alloc.alloc_memory(128)
    try:
        # '#' without a following expression
        mem.w_cstr(src.addr, "#")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == -1
        assert lib.io_err == ERROR_BAD_TEMPLATE
        # unterminated OR block
        mem.w_cstr(src.addr, "(a")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == -1
        assert lib.io_err == ERROR_BAD_TEMPLATE
    finally:
        alloc.free_memory(src)
        alloc.free_memory(buf)
    assert alloc.is_all_free()


def lib_dos_parse_pattern_nocase_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = _make_lib()
    ctx = _make_ctx(mem, alloc)
    src = alloc.alloc_memory(64)
    buf = alloc.alloc_memory(128)
    buf_nc = alloc.alloc_memory(128)
    try:
        # only difference: NoCase lower-cases the literal characters
        mem.w_cstr(src.addr, "TEST.O")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 0
        assert lib.ParsePatternNoCase(ctx, src.addr, buf_nc.addr, 128) == 0
        assert mem.r_cstr(buf.addr) == "TEST.O"
        assert mem.r_cstr(buf_nc.addr) == "test.o"
        # wildcard patterns are tokenized the same way, only the literals differ
        mem.w_cstr(src.addr, "SUB/#?.O")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 1
        assert lib.ParsePatternNoCase(ctx, src.addr, buf_nc.addr, 128) == 1
        assert (
            mem.r_cstr(buf.addr) == pattern_parse("SUB/#?.O", ignore_case=False).pat_str
        )
        assert (
            mem.r_cstr(buf_nc.addr)
            == pattern_parse("SUB/#?.O", ignore_case=True).pat_str
        )
        assert mem.r_cstr(buf.addr) != mem.r_cstr(buf_nc.addr)
    finally:
        alloc.free_memory(src)
        alloc.free_memory(buf)
        alloc.free_memory(buf_nc)
    assert alloc.is_all_free()


# ----- MatchPattern / MatchPatternNoCase -----


def lib_dos_match_pattern_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = _make_lib()
    ctx = _make_ctx(mem, alloc)
    src = alloc.alloc_memory(64)
    buf = alloc.alloc_memory(128)
    txt = alloc.alloc_memory(64)

    def match(pat_addr, text):
        mem.w_cstr(txt.addr, text)
        return lib.MatchPattern(ctx, pat_addr, txt.addr)

    try:
        # exact name (case sensitive)
        mem.w_cstr(src.addr, "test.o")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 0
        assert match(buf.addr, "test.o") == -1
        assert match(buf.addr, "TEST.o") == 0
        assert match(buf.addr, "testo.o") == 0
        # '#?' matches anything (including the empty string)
        mem.w_cstr(src.addr, "#?")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 1
        assert match(buf.addr, "bla") == -1
        assert match(buf.addr, "") == -1
        # 'a#?' only matches names starting with 'a'
        mem.w_cstr(src.addr, "a#?")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 1
        assert match(buf.addr, "alpha") == -1
        assert match(buf.addr, "bravo") == 0
        # '?' consumes exactly one character
        mem.w_cstr(src.addr, "?")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 1
        assert match(buf.addr, "a") == -1
        assert match(buf.addr, "ab") == 0
    finally:
        alloc.free_memory(src)
        alloc.free_memory(buf)
        alloc.free_memory(txt)
    assert alloc.is_all_free()


def lib_dos_match_pattern_nocase_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = _make_lib()
    ctx = _make_ctx(mem, alloc)
    src = alloc.alloc_memory(64)
    buf = alloc.alloc_memory(128)
    txt = alloc.alloc_memory(64)

    def match_nc(pat_addr, text):
        mem.w_cstr(txt.addr, text)
        return lib.MatchPatternNoCase(ctx, pat_addr, txt.addr)

    try:
        mem.w_cstr(src.addr, "TEST.O")
        assert lib.ParsePatternNoCase(ctx, src.addr, buf.addr, 128) == 0
        assert mem.r_cstr(buf.addr) == "test.o"
        # NoCase matcher folds the compared text, so any casing matches
        assert match_nc(buf.addr, "test.o") == -1
        assert match_nc(buf.addr, "TEST.O") == -1
        assert match_nc(buf.addr, "TeSt.O") == -1
        assert match_nc(buf.addr, "testo.o") == 0
        # a case preserving pattern only matches its exact casing...
        mem.w_cstr(src.addr, "TEST.O")
        assert lib.ParsePattern(ctx, src.addr, buf.addr, 128) == 0
        mem.w_cstr(txt.addr, "TEST.O")
        assert lib.MatchPattern(ctx, buf.addr, txt.addr) == -1
        mem.w_cstr(txt.addr, "test.o")
        assert lib.MatchPattern(ctx, buf.addr, txt.addr) == 0
        # ...but the NoCase matcher folds the pattern as well, so the
        # case-preserving pattern above still matches any casing
        mem.w_cstr(txt.addr, "TEST.O")
        assert lib.MatchPatternNoCase(ctx, buf.addr, txt.addr) == -1
        mem.w_cstr(txt.addr, "test.o")
        assert lib.MatchPatternNoCase(ctx, buf.addr, txt.addr) == -1
    finally:
        alloc.free_memory(src)
        alloc.free_memory(buf)
        alloc.free_memory(txt)
    assert alloc.is_all_free()


def lib_dos_match_pattern_nocase_raw_test():
    """MatchPatternNoCase folds a raw pattern that was not parsed first.

    C:Search builds an upper-case pattern and passes it straight to
    MatchPatternNoCase() (it never calls ParsePatternNoCase()), relying on the
    matcher to fold the text -- and the pattern -- case-insensitively.
    """
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = _make_lib()
    ctx = _make_ctx(mem, alloc)
    pat = alloc.alloc_memory(64)
    txt = alloc.alloc_memory(64)

    def match_nc(pattern, text):
        mem.w_cstr(pat.addr, pattern)
        mem.w_cstr(txt.addr, text)
        return lib.MatchPatternNoCase(ctx, pat.addr, txt.addr)

    try:
        assert match_nc("HELLO", "hello") == -1
        assert match_nc("hello", "HELLO") == -1
        assert match_nc("HeLLo", "hEllO") == -1
        assert match_nc("HELLO", "world") == 0
        assert match_nc("README.TXT", "readme.txt") == -1
        assert match_nc("README.TXT", "readme.tx") == 0
    finally:
        alloc.free_memory(pat)
        alloc.free_memory(txt)
    assert alloc.is_all_free()


# ----- MatchFirst / MatchNext / MatchEnd -----


class _FakeLock:
    """lock stub: records examine_lock() calls and fills in a file name"""

    def __init__(self, mem, name=""):
        self.mem = SimpleNamespace(addr=0x1000)
        self._mem = mem
        self.name = name
        self.examined = []

    def examine_lock(self, fib):
        self.examined.append(fib.addr)
        self._mem.w_cstr(fib.fib_FileName.addr, self.name)
        return NO_ERROR


class _FakeLockMgr:
    def __init__(self, mem):
        self.mem = mem
        self.created = []
        self.released = []

    def create_lock(self, cur_dir, ami_path, exclusive):
        self.created.append(ami_path)
        return _FakeLock(self.mem, ami_path)

    def get_by_b_addr(self, b_addr):
        return None

    def release_lock(self, lock):
        self.released.append(lock)


class _FakePathMgr:
    """flat directory listing used by the PathMatch wildcard scanner"""

    def __init__(self, entries):
        self.entries = list(entries)

    def ami_list_dir(self, lock, path):
        return list(self.entries) if path == "" else None

    def ami_path_exists(self, lock, path):
        return path in self.entries

    def ami_name_of_path(self, lock, path):
        return path

    def ami_dir_of_path(self, lock, path):
        return ""

    def ami_abs_path(self, lock, path):
        return path


class _MatchEnv:
    """DosLibrary plus fake path/lock managers and a real AnchorPath in memory"""

    def __init__(self, entries=("alpha", "bravo", "charlie")):
        self.mem = MockMemory(size_kib=64)
        self.alloc = MemoryAlloc(self.mem)
        self.lib = _make_lib()
        self.lock = _FakeLock(self.mem)
        self.lib.path_mgr = _FakePathMgr(entries)
        self.lib.lock_mgr = _FakeLockMgr(self.mem)
        self.lib.get_current_dir = lambda ctx: self.lock
        self.ctx = _make_ctx(self.mem, self.alloc)
        self.anchor_mem = self.alloc.alloc_memory(
            AnchorPathStruct.get_size() + 256, label="AnchorPath"
        )
        self.anchor_ptr = self.anchor_mem.addr
        self.anchor = AnchorPathStruct(self.mem, self.anchor_ptr)
        self.anchor.ap_Strlen.val = 255
        self.anchor.ap_Flags.val = 0
        self.pat = self.alloc.alloc_cstr("")

    def set_pattern(self, pattern):
        self.alloc.free_cstr(self.pat)
        self.pat = self.alloc.alloc_cstr(pattern)

    def buf(self):
        return self.mem.r_cstr(self.anchor.ap_Buf.addr)

    def close(self):
        if self.anchor_ptr in self.lib.matches:
            self.lib.MatchEnd(self.ctx, self.anchor_ptr)
        self.alloc.free_cstr(self.pat)
        self.alloc.free_memory(self.anchor_mem)
        assert self.alloc.is_all_free()


def lib_dos_match_first_test():
    env = _MatchEnv()
    env.set_pattern("#?")
    try:
        err = env.lib.MatchFirst(env.ctx, env.pat.addr, env.anchor_ptr)
        assert err == NO_ERROR
        assert env.lib.io_err == NO_ERROR
        # matcher kept for the following MatchNext calls
        assert env.anchor_ptr in env.lib.matches
        mfn = env.lib.matches[env.anchor_ptr]
        assert mfn.name == "alpha"
        assert mfn.path == "alpha"
        # first match is also written to the anchor buffer and the FIB
        assert env.buf() == "alpha"
        assert env.mem.r_cstr(env.anchor.ap_Info.fib_FileName.addr) == "alpha"
        # base/last achain was created
        assert env.anchor.ap_Base.aptr != 0
        assert env.anchor.ap_Last.aptr == env.anchor.ap_Base.aptr
    finally:
        env.close()


def lib_dos_match_first_no_match_test():
    env = _MatchEnv()
    env.set_pattern("#?z")  # no listing entry ends in 'z'
    try:
        err = env.lib.MatchFirst(env.ctx, env.pat.addr, env.anchor_ptr)
        assert err == ERROR_OBJECT_NOT_FOUND
        assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND
        # a matcher is still created so MatchEnd can release it
        assert env.anchor_ptr in env.lib.matches
    finally:
        env.close()


def lib_dos_match_first_bad_pattern_test():
    env = _MatchEnv()
    env.set_pattern("#")  # PathMatch.parse() rejects this template
    try:
        err = env.lib.MatchFirst(env.ctx, env.pat.addr, env.anchor_ptr)
        assert err == ERROR_BAD_TEMPLATE
        assert env.lib.io_err == ERROR_BAD_TEMPLATE
        assert env.anchor_ptr in env.lib.matches
    finally:
        env.close()


def lib_dos_match_next_test():
    env = _MatchEnv()
    env.set_pattern("#?")
    try:
        assert env.lib.MatchFirst(env.ctx, env.pat.addr, env.anchor_ptr) == NO_ERROR
        assert env.buf() == "alpha"
        # iterate through the remaining entries in listing order
        assert env.lib.MatchNext(env.ctx, env.anchor_ptr) == NO_ERROR
        assert env.buf() == "bravo"
        assert env.lib.MatchNext(env.ctx, env.anchor_ptr) == NO_ERROR
        assert env.buf() == "charlie"
        # exhausted
        assert env.lib.MatchNext(env.ctx, env.anchor_ptr) == ERROR_NO_MORE_ENTRIES
        assert env.lib.io_err == ERROR_NO_MORE_ENTRIES
    finally:
        env.close()


def lib_dos_match_end_test():
    env = _MatchEnv()
    env.set_pattern("#?")
    try:
        assert env.lib.MatchFirst(env.ctx, env.pat.addr, env.anchor_ptr) == NO_ERROR
        mfn = env.lib.matches[env.anchor_ptr]
        achain = mfn.achain_dummy
        assert achain is not None
        assert env.alloc.get_memory(achain.addr) is not None
        # MatchEnd drops the matcher and frees its anchor chain
        env.lib.MatchEnd(env.ctx, env.anchor_ptr)
        assert env.anchor_ptr not in env.lib.matches
        assert env.alloc.get_memory(achain.addr) is None
    finally:
        env.close()


def lib_dos_match_end_twice_test():
    # some programs (e.g. the OS 3.2.3 Type) call MatchEnd twice for the same
    # anchor; the second call must be a harmless no-op, not an internal error
    env = _MatchEnv()
    env.set_pattern("#?")
    try:
        assert env.lib.MatchFirst(env.ctx, env.pat.addr, env.anchor_ptr) == NO_ERROR
        env.lib.MatchEnd(env.ctx, env.anchor_ptr)
        assert env.anchor_ptr not in env.lib.matches
        env.lib.MatchEnd(env.ctx, env.anchor_ptr)
        assert env.anchor_ptr not in env.lib.matches
    finally:
        env.close()
