import io
import struct
from types import SimpleNamespace

import pytest

from amitools.fd import read_lib_fd
from amitools.vamos.lib.AslLibrary import TB, AslLibrary
from amitools.vamos.lib.DatatypesLibrary import DatatypesLibrary
from amitools.vamos.lib.DiskfontLibrary import DiskfontLibrary
from amitools.vamos.lib.IconLibrary import IconLibrary
from amitools.vamos.lib.IFFParseLibrary import IFFParseLibrary
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
from amitools.vamos.lib.picture_datatype import decode_ilbm
from amitools.vamos.libcore.impl import LibImplScanner
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc


@pytest.mark.parametrize(
    "source,result",
    [
        (65, 97),
        (90, 122),
        (192, 224),
        (222, 254),
        (215, 215),
        (223, 223),
        (255, 255),
        (0x141, 97),
    ],
)
def utility_lower_latin1_test(os_ctx, source, result):
    from amitools.vamos.lib.UtilityLibrary import UtilityLibrary
    from amitools.vamos.machine import REG_D0

    os_ctx.cpu.w_reg(REG_D0, source)
    assert UtilityLibrary().ToLower(os_ctx) == result


@pytest.fixture
def os_ctx():
    mem = MockMemory(size_kib=512)
    alloc = MemoryAlloc(mem)
    ctx = SimpleNamespace(mem=mem, cpu=MockCPU(), alloc=alloc)
    yield ctx
    assert alloc.is_all_free()


@pytest.mark.parametrize(
    "name,cls",
    [
        ("asl", AslLibrary),
        ("diskfont", DiskfontLibrary),
        ("iffparse", IFFParseLibrary),
        ("icon", IconLibrary),
        ("datatypes", DatatypesLibrary),
        ("intuition", IntuitionLibrary),
    ],
)
def os_library_vector_signatures_test(name, cls):
    name += ".library"
    scan = LibImplScanner().scan(name, cls(), read_lib_fd(name))
    assert not scan.error_funcs
    assert not scan.invalid_funcs


def iff_nested_roundtrip_test(os_ctx):
    ctx = os_ctx
    stream = io.BytesIO()
    ctx.dos_lib = SimpleNamespace(
        file_mgr=SimpleNamespace(get_by_b_addr=lambda addr: stream)
    )
    lib = IFFParseLibrary()
    lib.setup_lib(ctx, 0)
    iff = lib.AllocIFF(ctx)
    buffer = ctx.alloc.alloc_memory(64)
    lib.InitIFFasDOS(ctx, iff)
    assert lib.OpenIFF(ctx, iff, 1) == 0
    FORM, PREF, TEST, DATA = (
        int.from_bytes(s, "big") for s in (b"FORM", b"PREF", b"TEST", b"DATA")
    )
    assert lib.PushChunk(ctx, iff, PREF, FORM, 0xFFFFFFFF) == 0
    assert lib.PushChunk(ctx, iff, 0, TEST, 3) == 0
    ctx.mem.w_block(buffer.addr, b"abc")
    assert lib.WriteChunkBytes(ctx, iff, buffer.addr, 3) == 3
    assert lib.PopChunk(ctx, iff) == 0
    assert lib.PushChunk(ctx, iff, PREF, FORM, 0xFFFFFFFF) == 0
    assert lib.PushChunk(ctx, iff, 0, DATA, 4) == 0
    ctx.mem.w_block(buffer.addr, b"1234")
    assert lib.WriteChunkRecords(ctx, iff, buffer.addr, 2, 2) == 2
    assert lib.PopChunk(ctx, iff) == 0
    assert lib.PopChunk(ctx, iff) == 0
    assert lib.PopChunk(ctx, iff) == 0
    expected = (
        b"FORM\x00\x00\x00(PREFTEST\x00\x00\x00\x03abc\0FORM\x00\x00\x00\x10"
        b"PREFDATA\x00\x00\x00\x041234"
    )
    assert stream.getvalue() == expected
    lib.CloseIFF(ctx, iff)
    assert not stream.closed
    stream.seek(0)
    assert lib.OpenIFF(ctx, iff, 0) == 0
    lib.PropChunk(ctx, iff, PREF, TEST)
    lib.StopChunk(ctx, iff, PREF, DATA)
    assert lib.ParseIFF(ctx, iff, 0) == 0
    node = lib.CurrentChunk(ctx, iff)
    assert ctx.mem.r32(node + 8) == DATA
    assert ctx.mem.r32(node + 16) == 4
    assert ctx.mem.r32(iff + 8) == 3
    assert lib.ParentChunk(ctx, node)
    prop = lib.FindProp(ctx, iff, PREF, TEST)
    assert prop and ctx.mem.r32(prop) == 3
    assert bytes(ctx.mem.r_block(ctx.mem.r32(prop + 4), 3)) == b"abc"
    assert lib.ReadChunkBytes(ctx, iff, buffer.addr, 100) == 4
    assert bytes(ctx.mem.r_block(buffer.addr, 4)) == b"1234"
    assert lib.ParseIFF(ctx, iff, 0) == -1
    assert lib.CurrentChunk(ctx, iff) == 0
    lib.FreeIFF(ctx, iff)
    ctx.alloc.free_memory(buffer)


@pytest.mark.parametrize(
    "raw,err",
    [
        (b"NOPE\0\0\0\0", -10),
        (b"FORM\0\0\0\x04PREF", -1),
        (b"FORM\0\0\0\x0cPREFDATA\0\0\0\x20", -8),
        (b"FORM\0\0\0\x0cPREFDA", -5),
    ],
)
def iff_invalid_input_test(os_ctx, raw, err):
    ctx = os_ctx
    ctx.dos_lib = SimpleNamespace(
        file_mgr=SimpleNamespace(get_by_b_addr=lambda addr: io.BytesIO(raw))
    )
    lib = IFFParseLibrary()
    lib.setup_lib(ctx, 0)
    iff = lib.AllocIFF(ctx)
    lib.InitIFFasDOS(ctx, iff)
    assert lib.OpenIFF(ctx, iff, 0) == 0
    assert lib.ParseIFF(ctx, iff, 0) == err
    lib.FreeIFF(ctx, iff)


def icon_guest_roundtrip_test(os_ctx):
    ctx = os_ctx
    lib = IconLibrary()
    lib.setup_lib(ctx, 0)
    obj = lib.NewDiskObject(ctx, 3)
    assert ctx.mem.r16(obj) == 0xE310
    image = ctx.mem.r32(obj + 22)
    assert ctx.mem.r16(image + 4) == 16
    assert ctx.mem.r32(image + 10) > image
    raw = lib._export(ctx, obj)
    copy = lib._import(ctx, raw)
    assert copy != obj and ctx.mem.r32(copy + 22) != image
    assert lib._export(ctx, copy) == raw
    lib.FreeDiskObject(ctx, obj)
    assert lib._export(ctx, copy) == raw
    lib.FreeDiskObject(ctx, copy)


def icon_tooltypes_test(os_ctx):
    ctx = os_ctx
    lib = IconLibrary()
    lib.setup_lib(ctx, 0)
    strings = [
        ctx.alloc.alloc_cstr(s)
        for s in ("DISPLAY=WINDOW|CUSTOM", "QUIET", "display", "WINDOW", "quiet")
    ]
    array = ctx.alloc.alloc_memory(12)
    for i, string in enumerate(strings[:2]):
        ctx.mem.w32(array.addr + i * 4, string.addr)
    value = lib.FindToolType(ctx, array.addr, strings[2].addr)
    assert ctx.mem.r_cstr(value) == "WINDOW|CUSTOM"
    assert lib.MatchToolValue(ctx, value, strings[3].addr) == 1
    assert lib.MatchToolValue(ctx, 0, strings[3].addr) == 0
    flag = lib.FindToolType(ctx, array.addr, strings[4].addr)
    assert flag and ctx.mem.r_cstr(flag) == ""
    ctx.alloc.free_memory(array)
    for string in strings:
        ctx.alloc.free_cstr(string)


def asl_selection_and_cancel_test(os_ctx):
    ctx = os_ctx
    lib = AslLibrary()
    lib.setup_lib(ctx, 0)
    req = lib.AllocAslRequest(ctx, 0, 0)
    assert ctx.mem.r_cstr(ctx.mem.r32(req + 52)) == "#?"
    lib.backend = lambda title, fields: None
    assert lib.AslRequest(ctx, req, 0) == 0
    lib.backend = lambda title, fields: ["SYS:Prefs", "file.prefs"]
    assert lib.AslRequest(ctx, req, 0) == 1
    assert ctx.mem.r_cstr(ctx.mem.r32(req + 8)) == "SYS:Prefs"
    assert ctx.mem.r_cstr(ctx.mem.r32(req + 4)) == "file.prefs"

    def cancel_again(title, fields):
        assert fields == [("Drawer", "SYS:Prefs"), ("File", "file.prefs")]

    lib.backend = cancel_again
    assert lib.AslRequest(ctx, req, 0) == 0
    lib.FreeAslRequest(ctx, req)
    assert lib.AllocAslRequest(ctx, 99, 0) == 0
    req = lib.AllocAslRequest(ctx, 1, 0)
    lib.backend = lambda title, fields: ["topaz.font", "12"]
    assert lib.AslRequest(ctx, req, 0) == 1
    assert ctx.mem.r16(req + 12) == 12
    assert ctx.mem.r32(req + 32) == ctx.mem.r32(req + 8)
    lib.finish_lib(ctx)


def diskfont_avail_bounds_test(os_ctx):
    ctx = os_ctx
    lib = DiskfontLibrary()
    block = ctx.alloc.alloc_memory(64)
    ctx.mem.clear_block(block.addr, 64, 0xCC)
    assert lib.AvailFonts(ctx, block.addr, 1, 1) == 22
    assert ctx.mem.r8(block.addr) == 0xCC
    assert lib.AvailFonts(ctx, block.addr, 23, 1) == 0
    assert ctx.mem.r16(block.addr) == 1
    assert ctx.mem.r_cstr(ctx.mem.r32(block.addr + 4)) == "topaz.font"
    assert ctx.mem.r8(block.addr + 23) == 0xCC
    ctx.alloc.free_memory(block)


def ilbm(compressed=False):
    header = struct.pack(
        ">HHhhBBBBHBBhh", 16, 1, 0, 0, 1, 0, int(compressed), 0, 0, 1, 1, 16, 1
    )
    body = b"\x01\xaa\x55" if compressed else b"\xaa\x55"
    chunks = b"BMHD" + struct.pack(">I", len(header)) + header
    chunks += (
        b"BODY"
        + struct.pack(">I", len(body))
        + body
        + (b"\0" if len(body) & 1 else b"")
    )
    return b"FORM" + struct.pack(">I", len(chunks) + 4) + b"ILBM" + chunks


@pytest.mark.parametrize("compressed", [False, True])
def datatype_ilbm_test(compressed):
    _header, planes, mask, _cmap, _mode = decode_ilbm(ilbm(compressed))
    assert planes == [b"\xaa\x55"] and mask is None
    with pytest.raises(ValueError):
        decode_ilbm(ilbm(compressed)[:-1])


def diskfont_hunk_test():
    from pathlib import Path

    import amitools.vamos.lib.fonts.convert_topaz as source
    from amitools.vamos.lib.diskfont import read_contents, read_disk_font

    font, _style, _flags = read_disk_font(
        Path(source.__file__).with_name("TopazDoubleSans-16.hunk")
    )
    assert (font.width, font.height, font.baseline) == (8, 16, 13)
    assert len(font.strike.locations) == 225
    index = b"\x0f\x00\x00\x01" + b"topaz/16".ljust(256, b"\0") + b"\x00\x10\x00\x42"
    assert read_contents(index) == [("topaz/16", 16, 0, 0x42)]
    with pytest.raises(ValueError):
        read_contents(index[:-1])


@pytest.mark.parametrize("suffix", ["mui", "mcc", "mcp"])
def class_library_names_test(suffix):
    import argparse

    from amitools.fd import get_base_name, get_fd_name
    from amitools.vamos.cfg import LibsParser
    from amitools.vamos.libmgr.cfg import LibCfg, LibMgrCfg

    name = "sample." + suffix
    assert get_fd_name(name) == "sample_lib.fd"
    assert get_base_name(name) == "_SampleBase"
    assert read_lib_fd(name) is None
    config = LibCfg(create_mode="amiga")
    manager = LibMgrCfg()
    manager.add_lib_cfg(name, config)
    assert manager.get_cfg("LIBS:MUI/" + name) is config
    parser = LibsParser()
    ap = argparse.ArgumentParser()
    parser.setup_args(ap)
    parser.parse_args(ap.parse_args(["-O", name + "=mode:amiga"]))
    assert parser.get_cfg_dict().libs[name].mode == "amiga"


def asl_copies_initial_strings_test(os_ctx):
    ctx = os_ctx
    lib = AslLibrary()
    lib.setup_lib(ctx, 0)
    text = ctx.alloc.alloc_cstr("Original")
    tags = ctx.alloc.alloc_memory(16)
    ctx.mem.w32(tags.addr, TB + 8)
    ctx.mem.w32(tags.addr + 4, text.addr)
    req = lib.AllocAslRequest(ctx, 0, tags.addr)
    ctx.mem.w_cstr(text.addr, "Changed")
    ctx.alloc.free_cstr(text)
    ctx.alloc.free_memory(tags)

    def cancel(title, fields):
        assert fields[1] == ("File", "Original")

    lib.backend = cancel
    assert lib.AslRequest(ctx, req, 0) == 0
    lib.FreeAslRequest(ctx, req)


def library_allocation_failure_test(os_ctx):
    ctx = os_ctx
    asl, iff, icons = AslLibrary(), IFFParseLibrary(), IconLibrary()
    for lib in (asl, iff, icons):
        lib.setup_lib(ctx, 0)
    filler = ctx.alloc.alloc_memory(ctx.alloc.get_free_bytes())
    assert asl.AllocAslRequest(ctx, 0, 0) == 0
    assert iff.AllocIFF(ctx) == 0
    assert icons.NewDiskObject(ctx, 3) == 0
    for lib in (asl, iff, icons):
        lib.finish_lib(ctx)
    ctx.alloc.free_memory(filler)


def asl_png_cancels_without_sdl_test(os_ctx, tmp_path, monkeypatch):
    import builtins
    from amitools.vamos.display.png import PNGDisplay

    original = builtins.__import__

    def no_sdl(name, *args, **kwargs):
        if name == "sdl2" or name.startswith("sdl2."):
            raise AssertionError("offline requester imported SDL")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sdl)
    os_ctx.display = PNGDisplay(tmp_path)
    lib = AslLibrary()
    lib.setup_lib(os_ctx, 0)
    req = lib.AllocAslRequest(os_ctx, 0, 0)
    assert lib.AslRequest(os_ctx, req, 0) == 0
    lib.FreeAslRequest(os_ctx, req)
    assert not os_ctx.display.windows
