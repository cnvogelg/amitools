import io

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.dos.DosFileOpener import DosFileOpener
from amitools.vamos.loader import SegmentLoader
from amitools.vamos.machine.regs import REG_D1
from helper import HostFileOpener
from amitools.binfmt.hunk.Hunk import (
    HUNK_BREAK,
    HUNK_CODE,
    HUNK_END,
    HUNK_HEADER,
    HUNK_OVERLAY,
)
from amitools.binfmt.hunk.HunkBlockFile import (
    HunkBreakBlock,
    HunkBlockFile,
    HunkEndBlock,
    HunkHeaderBlock,
    HunkOverlayBlock,
    HunkSegmentBlock,
)
from amitools.binfmt.hunk.HunkLoadSegFile import HunkLoadSegFile
from amitools.binfmt.hunk.HunkReader import HunkReader
from amitools.binfmt.hunk.HunkShow import HunkShow


def make_overlay_file(standard_manager=True):
    header = HunkHeaderBlock()
    header.setup([10])
    overlay_header_one = HunkHeaderBlock()
    overlay_header_one.setup([1])
    overlay_header_two = HunkHeaderBlock()
    overlay_header_two.setup([1])

    manager = bytearray(40)
    manager[4:8] = b"\x00\x00\xab\xcd"
    if standard_manager:
        manager[24:28] = b"\x00\x00\x5b\xa0"
        manager[28:32] = b"\x07\x4f\x76\x65"
        manager[32:36] = b"\x72\x6c\x61\x79"

    blocks = HunkBlockFile(
        [
            header,
            HunkSegmentBlock(HUNK_CODE, bytes(manager), 10),
            HunkEndBlock(),
            HunkOverlayBlock(),
            overlay_header_one,
            HunkSegmentBlock(HUNK_CODE, b"one!", 1),
            HunkEndBlock(),
            HunkBreakBlock(),
            overlay_header_two,
            HunkSegmentBlock(HUNK_CODE, b"two!", 1),
            HunkEndBlock(),
        ]
    )
    overlay_table = [2, 0, 0x234, 0, 0, 1, 2, 157, 158, 0x24]
    blocks.blocks[3].data = b"".join(
        value.to_bytes(4, "big") for value in overlay_table
    )
    stream = io.BytesIO()
    blocks.write(stream, isLoadSeg=True)
    return stream.getvalue()


def hunk_overlay_block_round_trip_test():
    data = b"\x00\x00\x00\x00"
    block = HunkOverlayBlock()
    block.data = data
    stream = io.BytesIO()
    HunkBlockFile([block]).write(stream)
    assert stream.getvalue() == HUNK_OVERLAY.to_bytes(4, "big") + b"\x00" * 8

    parsed = HunkBlockFile()
    parsed.read(io.BytesIO(stream.getvalue()), isLoadSeg=True)
    assert parsed.get_blocks()[0].blk_id == HUNK_OVERLAY
    assert parsed.get_blocks()[0].data == data


def hunk_loadseg_overlay_round_trip_test():
    data = make_overlay_file()
    block_file = HunkBlockFile()
    block_file.read(io.BytesIO(data), isLoadSeg=True)

    loadseg = HunkLoadSegFile()
    loadseg.parse_block_file(block_file)
    assert len(loadseg.segments) == 1
    assert len(loadseg.overlay_headers) == 2
    assert [
        [segment.seg_blk.data for segment in group]
        for group in loadseg.overlay_segments
    ] == [[b"one!"], [b"two!"]]

    output = io.BytesIO()
    loadseg.create_block_file().write(output, isLoadSeg=True)
    assert output.getvalue() == data


def hunk_reader_builds_overlay_segments_test():
    reader = HunkReader()
    assert reader.read_file_obj("overlay", io.BytesIO(make_overlay_file())) == 0
    headers = [hunk for hunk in reader.hunks if hunk["type"] == HUNK_HEADER]
    headers[1]["first_hunk"] = 157
    headers[1]["last_hunk"] = 157
    headers[2]["first_hunk"] = 169
    headers[2]["last_hunk"] = 169
    assert reader.build_segments()
    assert reader.overlay["type"] == HUNK_OVERLAY
    assert [header["type"] for header in reader.overlay_headers] == [
        HUNK_HEADER,
        HUNK_HEADER,
    ]
    assert [
        [segment[0]["data"] for segment in group] for group in reader.overlay_segments
    ] == [[b"one!"], [b"two!"]]
    assert [group[0][0]["hunk_no"] for group in reader.overlay_segments] == [157, 169]
    assert [group[0][0]["alloc_size"] for group in reader.overlay_segments] == [4, 4]
    assert reader.hunks[-1]["type"] == HUNK_END
    assert reader.hunks[7]["type"] == HUNK_BREAK


def hunk_show_dumps_standard_overlay_table_test(capsys):
    reader = HunkReader()
    assert reader.read_file_obj("overlay", io.BytesIO(make_overlay_file())) == 0
    assert reader.build_segments()

    HunkShow(reader, brief=True).show_segments()
    output = capsys.readouterr().out
    assert "Overlay: standard manager, table size=40 bytes" in output
    assert "Overlay table: tree size=2, references=1" in output
    assert "terminator" in output
    assert (
        "Reference #0: file offset=00000234, reserved=00000000/00000000, "
        "level=1, ordinate=2, initial hunk=157, symbol hunk=158, "
        "symbol offset=00000024"
    ) in output


def hunk_show_dumps_custom_overlay_table_test(capsys):
    reader = HunkReader()
    assert (
        reader.read_file_obj(
            "overlay", io.BytesIO(make_overlay_file(standard_manager=False))
        )
        == 0
    )
    assert reader.build_segments()

    HunkShow(reader, brief=True).show_segments()
    output = capsys.readouterr().out
    assert "Overlay: custom manager, table size=40 bytes" in output
    assert "Reference records decoded by their 8-longword layout" in output
    assert "initial hunk=157, symbol hunk=158" in output


def dos_loadseg_overlay_test(tmp_path, mem_alloc):
    mem, alloc = mem_alloc
    path = tmp_path / "overlay"
    path.write_bytes(make_overlay_file())
    loader = SegmentLoader(alloc)

    class FileHandle:
        b_addr = 0x1234

        def __init__(self, path):
            self.obj = open(path, "rb")

        def read(self, size=-1):
            return self.obj.read(size)

        def seek(self, pos, whence):
            self.obj.seek(pos, whence)
            return self.obj.tell()

        def tell(self):
            return self.obj.tell()

        def close(self):
            self.obj.close()

    class FileManager:
        def __init__(self):
            self.fh = None

        def open(self, lock, name, mode):
            self.fh = FileHandle(path)
            return self.fh

        def close(self, fh):
            fh.close()

    class CPU:
        def __init__(self):
            self.regs = {REG_D1: 0x100}

        def r_reg(self, reg):
            return self.regs[reg]

    class Memory:
        def __init__(self, mem):
            self.mem = mem

        def r_cstr(self, addr):
            return "overlay"

        def __getattr__(self, name):
            return getattr(self.mem, name)

    class Context:
        pass

    ctx = Context()
    ctx.cpu = CPU()
    ctx.mem = Memory(mem)
    ctx.seg_loader = loader
    dos = DosLibrary.__new__(DosLibrary)
    dos.alloc = alloc
    dos.file_mgr = FileManager()
    dos.seg_lists = {}
    dos.get_current_dir = lambda ctx: None
    loader.set_file_opener(DosFileOpener(dos.file_mgr))

    result = dos.LoadSeg(ctx, ctx.cpu.r_reg(REG_D1))
    assert result < 0
    b_addr = -result
    info = loader.get_info(b_addr)
    manager_addr = info.seglist.get_all_addrs()[0]
    assert mem.r32(manager_addr + 8) == dos.file_mgr.fh.b_addr

    reader = HunkReader()
    assert reader.read_file(str(path)) == 0
    overlay = next(hunk for hunk in reader.hunks if hunk["type"] == HUNK_OVERLAY)
    overlay_file_pos = overlay["hunk_file_offset"] + 8 + len(overlay["ov_data"])
    assert dos.file_mgr.fh.tell() == overlay_file_pos

    overlay_table_addr = mem.r32(manager_addr + 12)
    hunk_table_baddr = mem.r32(manager_addr + 16)
    assert mem.r32(overlay_table_addr) == int.from_bytes(overlay["ov_data"][:4], "big")
    assert mem.r32(hunk_table_baddr << 2) == b_addr

    ctx.cpu.regs[REG_D1] = result & 0xFFFFFFFF
    dos.UnLoadSeg(ctx, ctx.cpu.r_reg(REG_D1))
    assert dos.file_mgr.fh.obj.closed
    assert loader.get_info(b_addr) is None
    assert alloc.is_all_free()


def loader_segload_overlay_test(tmp_path, mem_alloc):
    mem, alloc = mem_alloc
    path = tmp_path / "overlay"
    path.write_bytes(make_overlay_file())
    loader = SegmentLoader(alloc)
    opener = HostFileOpener({"overlay": str(path)})

    # without file opener no overlay setup is done
    with open(path, "rb") as f:
        b_addr = loader.load_seglist(f, name="overlay")
    assert not loader.get_info(b_addr).has_overlay()
    assert loader.unload_seglist(b_addr)

    loader.set_file_opener(opener)
    b_addr = loader.load_ami_seglist("overlay")
    assert b_addr > 0
    info = loader.get_info(b_addr)
    assert info.has_overlay()
    manager_addr = info.seglist.get_all_addrs()[0]
    assert mem.r32(mem.r32(manager_addr + 16) << 2) == b_addr

    assert loader.unload_seglist(b_addr)
    assert opener.opened[-1].stream.closed
    assert loader.shutdown() == 0
    assert alloc.is_all_free()
