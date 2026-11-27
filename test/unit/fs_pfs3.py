"""PFS3 volumes: on-disk structures, reading, writing and the tools.

test/disks/pfs3-handler.rdb.gz is an RDB image with a PFS3 partition that
pfs3aio 19.2 formatted and filled, run through AmiFUSE: files, a directory of
several blocks, hard links to files and to a directory, a soft link, a
rollover file that wrapped around, and a deleted file in the deldir. Its file
contents are pattern() data."""

import gzip
import hashlib
import os
import shutil
import struct

import pytest

from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.fsck.FsckResult import Severity
from amitools.fs.FSError import (
    DELETE_NOT_ALLOWED,
    FILE_NOT_FOUND,
    FSError,
    INVALID_COMMENT,
    INVALID_FILE_NAME,
    INVALID_PARENT_DIRECTORY,
    LINK_NOT_ALLOWED,
    NAME_ALREADY_EXISTS,
    NO_FREE_BLOCKS,
    UNSUPPORTED_OPERATION,
    VOLUME_READ_ONLY,
)
from amitools.fs.FSString import FSString
from amitools.fs.Imager import Imager
from amitools.fs.MetaDB import MetaDB
from amitools.fs.MetaInfo import MetaInfo
from amitools.fs.RootMetaInfo import RootMetaInfo
from amitools.fs.TimeStamp import TimeStamp
from amitools.fs.VolumeFactory import create_volume, open_volume
from amitools.fs.pfs3 import is_pfs3_blkdev
from amitools.fs.pfs3.Const import (
    ANODE_EMPTY_BLOCKNR,
    ANODE_ROOTDIR,
    ID_PFS1,
    ID_PFS2,
    MAXNUMRESERVED,
    MODE_STORED_GEOM,
    MODE_SUPERINDEX,
    PP_FREEANODECHAIN,
    ROOTBLOCK,
    ST_FILE,
    ST_LINKDIR,
    ST_LINKFILE,
    ST_ROLLOVERFILE,
    ST_SOFTLINK,
    ST_USERDIR,
)
from amitools.fs.pfs3.DirEntry import DirEntry, entry_base_size, name_upper
from amitools.fs.pfs3.Disk import PFS3Disk
from amitools.fs.pfs3.PFS3Volume import PFS3Volume
import amitools.fs.DosType as DosType
from amitools.tools.rdbtool import main as rdbtool_main
from amitools.tools.xdftool import main as xdftool_main

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "disks", "pfs3-handler.rdb.gz")

F = FSString

LAYOUTS = {
    "plain": {},
    "supermode": {"supermode": True},
    "res2k": {"resblksize": 2048},
    "res4k": {"resblksize": 4096},
}


def pattern(tag, n):
    out = bytearray()
    i = 0
    while len(out) < n:
        out += hashlib.sha1(b"%d-%d" % (tag, i)).digest()
        i += 1
    return bytes(out[:n])


def assert_clean(vol):
    result = vol.check()
    issues = [str(i) for i in result.issues if i.severity.value >= Severity.WARN.value]
    assert issues == []


def new_volume(tmp_path, size="8M", name="Test", **opts):
    path = str(tmp_path / "pfs3.hdf")
    blkdev = BlkDevFactory().create(path, options={"size": size})
    vol = PFS3Volume(blkdev)
    vol.create(F(name), **opts)
    return path, blkdev, vol


def reopen(path, blkdev=None, **opts):
    if blkdev is not None:
        blkdev.close()
    blkdev = BlkDevFactory().open(path, options=opts or None)
    return blkdev, open_volume(blkdev)


def fixture_image(tmp_path):
    path = str(tmp_path / "fixture.rdb")
    with gzip.open(FIXTURE, "rb") as fin, open(path, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    return path


def tree(vol):
    """{path: (type, sha1 of data or soft link target, comment, uid, gid)} of
    all entries"""
    out = {}

    def walk(d, p):
        for n in d.get_entries():
            q = p + "/" + n.name.get_unicode_name()
            if n.is_file():
                data = hashlib.sha1(n.get_file_data()).hexdigest()
            elif n.entry.type == ST_SOFTLINK:
                data = n.get_target().get_unicode()
            else:
                data = None
            e = n.entry
            out[q] = (e.type, data, e.comment, e.uid, e.gid)
            if n.is_dir():
                walk(n, q)

    walk(vol.root_dir, "")
    return out


# ----- dos types -----


def pfs3_dos_type_test():
    for s in ("pfs", "pfs3", "PFS3"):
        assert DosType.parse_dos_type_str(s) == DosType.PFS3
    assert DosType.parse_dos_type_str("PFS1") == DosType.PFS1
    assert DosType.parse_dos_type_str("pfs2") == DosType.PFS2
    for s in ("pds3", "PDS3"):
        assert DosType.parse_dos_type_str(s) == DosType.PDS3
    assert DosType.get_dos_type_str(DosType.PFS1) == "PFS1:pfs3"
    assert DosType.get_dos_type_str(DosType.PDS3) == "PDS3:pfs3"
    assert DosType.get_dos_type_str(DosType.DOS3) == "DOS3:ffs+intl"
    assert DosType.is_pfs(DosType.PFS3)
    assert DosType.is_pfs(DosType.PDS3)
    assert not DosType.is_pfs(DosType.DOS1)


# ----- directory entries -----


def pfs3_direntry_size_test():
    # 19 + n + c rounded up to even, and a flags word
    e = DirEntry(name=b"abc", comment=b"")
    assert len(e.build()) == entry_base_size(3, 0) + 2 == 22 + 2
    e = DirEntry(name=b"ab", comment=b"", has_extra=False)
    assert len(e.build()) == 22
    assert e.build()[0] == 22


def pfs3_direntry_extra_order_test():
    """stored words are packed before the flags word in reverse order"""
    e = DirEntry(name=b"x", link=0x00010002, uid=7, prot=0xAB000000, fsizex=3)
    data = e.build()
    size = len(data)
    flags = struct.unpack_from(">H", data, size - 2)[0]
    assert flags == 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0400
    # reading backwards from the flags word gives ascending indices
    words = struct.unpack_from(">5H", data, size - 12)
    assert words == (3, 0xAB00, 7, 2, 1)
    p, n = DirEntry.parse(data + b"\0", 0, len(data) + 1, True)
    assert n == size
    assert (p.link, p.uid, p.prot, p.fsizex) == (0x00010002, 7, 0xAB000000, 3)


def pfs3_direntry_roundtrip_test():
    e = DirEntry(
        type=ST_ROLLOVERFILE,
        anode=0x10005,
        fsize=4096,
        date=(1000, 2, 3),
        name=b"\xe4bc",
        comment=b"c" * 79,
        uid=1,
        gid=2,
        virtualsize=4095,
        rollpointer=17,
    )
    e.set_protect32(0x12345678)
    data = e.build()
    p, n = DirEntry.parse(data + b"\0", 0, len(data) + 1, True)
    assert n == len(data)
    for k in ("type", "anode", "fsize", "date", "name", "comment", "uid", "gid"):
        assert getattr(p, k) == getattr(e, k)
    assert p.get_protect32() == 0x12345678 & 0xFFFFFF00 | 0x78
    assert (p.virtualsize, p.rollpointer) == (4095, 17)
    assert p.build() == data


def pfs3_name_upper_test():
    assert name_upper(b"abc\xe4\xf7\xff\xfe") == b"ABC\xc4\xf7\xff\xde"


# ----- format -----


def pfs3_num_reserved_test():
    """the reference formatter's heuristic"""
    assert PFS3Disk._calc_num_reserved(77792, 1024) == 2592
    assert PFS3Disk._calc_num_reserved(1760, 1024) == 64
    for s, r in ((1 << 26, 1024), (1 << 30, 2048), (1 << 32, 4096)):
        n = PFS3Disk._calc_num_reserved(s, r)
        assert n % 32 == 0 and 32 <= n <= MAXNUMRESERVED


@pytest.mark.parametrize("layout", LAYOUTS)
def pfs3_format_test(tmp_path, layout):
    path, blkdev, vol = new_volume(tmp_path, **LAYOUTS[layout])
    d = vol.disk
    assert is_pfs3_blkdev(blkdev)
    assert blkdev.read_block(0)[:4] == b"PFS\x01"
    want = 0x077F | MODE_STORED_GEOM
    if layout != "plain":
        want |= MODE_SUPERINDEX
    assert d.options == want
    assert d.disktype == (ID_PFS1 if layout in ("plain", "supermode") else ID_PFS2)
    # in use: the root block cluster, the extension, the bitmap and its
    # index, (a super block,) an index and an anode block, the root
    # directory and two deldir blocks
    nroot = d.rblkcluster // d.rescluster
    num_mi = (d.no_bmb + d.ipb - 1) // d.ipb
    used = nroot + 1 + num_mi + d.no_bmb + (1 if d.supermode else 0) + 2 + 1 + 2
    assert d._r32(0x3C) == d.numreserved - used
    assert d.get_ext().blocknr == ROOTBLOCK + d.rblkcluster
    assert d.get_blocks_free() == d.numblocks - d.lastreserved - 1
    assert d.get_always_free() == d.get_blocks_free() // 20
    assert d.get_deldir_size() == 2
    assert d.get_anode(ANODE_ROOTDIR)[0] == 1
    for nr in range(ANODE_ROOTDIR):
        assert d.get_anode(nr) == (0, ANODE_EMPTY_BLOCKNR, 0)
    assert_clean(vol)
    blkdev, vol = reopen(path, blkdev)
    assert isinstance(vol, PFS3Volume)
    assert vol.get_volume_name() == F("Test")
    assert vol.root_dir.get_entries() == []
    assert_clean(vol)
    blkdev.close()


def pfs3_format_meta_info_test(tmp_path):
    ts = TimeStamp()
    ts.parse("01.02.2003 04:05:06")
    path = str(tmp_path / "pfs3.hdf")
    blkdev = BlkDevFactory().create(path, options={"size": "4M"})
    mi = RootMetaInfo(create_ts=ts, disk_ts=ts, mod_ts=ts)
    vol = create_volume(blkdev, F("Meta"), meta_info=mi, dos_type=DosType.PFS3)
    blkdev, vol = reopen(path, blkdev)
    mi = vol.get_meta_info()
    for got in (mi.get_create_ts(), mi.get_disk_ts(), mi.get_mod_ts()):
        assert str(got) == str(ts)
    blkdev.close()


def pfs3_format_rejects_test(tmp_path):
    path = str(tmp_path / "pfs3.hdf")
    blkdev = BlkDevFactory().create(path, options={"size": "4M"})
    vol = PFS3Volume(blkdev)
    with pytest.raises(FSError):
        vol.create(F("x" * 31))
    with pytest.raises(FSError):
        vol.create(F("a:b"))
    with pytest.raises(FSError):
        vol.create(F("Boot"), boot_code=b"\0" * 16)
    blkdev.close()


# ----- files and directories -----


@pytest.mark.parametrize("layout", LAYOUTS)
def pfs3_write_read_test(tmp_path, layout):
    path, blkdev, vol = new_volume(tmp_path, **LAYOUTS[layout])
    B = vol.disk.B
    files = {}
    vol.create_dir(F("dir"))
    for i, size in enumerate((0, 1, B - 1, B, B + 1, 5000, 70000)):
        for p in ("f%d" % i, "dir/f%d" % i):
            files[p] = pattern(len(files), size)
            vol.write_file(files[p], F(p))
    assert_clean(vol)
    blkdev, vol = reopen(path, blkdev)
    for p, data in files.items():
        assert vol.read_file(F(p)) == data
    assert vol.get_path_name(F("DIR/F6")).get_size() == 70000
    assert_clean(vol)
    blkdev.close()


def pfs3_many_entries_test(tmp_path):
    """entries over several dir blocks and anodes over several anode blocks;
    dir blocks that become empty leave the chain"""
    path, blkdev, vol = new_volume(tmp_path)
    vol.create_dir(F("d"))
    for i in range(300):
        vol.write_file(pattern(i, i), F("d/a_rather_long_file_name_%03d" % i))
    d = vol.disk
    anode = vol.get_path_name(F("d")).anode
    assert len(d.get_chain(anode)) > 10
    assert d.get_max_anode_seqnr() >= 3
    assert_clean(vol)
    for i in range(299):
        vol.delete(F("d/a_rather_long_file_name_%03d" % i))
    assert_clean(vol)
    left = len(d.get_chain(anode))
    assert left <= 2
    blkdev, vol = reopen(path, blkdev)
    assert vol.read_file(F("d/a_rather_long_file_name_299")) == pattern(299, 299)
    assert len(vol.get_path_name(F("d")).get_entries()) == 1
    blkdev.close()


def pfs3_names_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path)
    vol.write_file(b"x", F("Häll"))
    with pytest.raises(FSError) as e:
        vol.write_file(b"x", F("HÄLL"))
    assert e.value.code == NAME_ALREADY_EXISTS
    with pytest.raises(FSError) as e:
        vol.write_file(b"x", F("n" * 32))
    assert e.value.code == INVALID_FILE_NAME
    vol.write_file(b"x", F("n" * 31))
    # the deldir name is taken in the root only
    with pytest.raises(FSError):
        vol.create_dir(F(".deldir"))
    vol.create_dir(F("sub"))
    vol.create_dir(F("sub/.DELDIR"))
    assert vol.read_file(F("häll")) == b"x"
    assert_clean(vol)
    blkdev.close()


def pfs3_long_names_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path, fnsize=107)
    name = "x" * 106
    vol.write_file(b"long", F(name))
    with pytest.raises(FSError):
        vol.write_file(b"long", F(name + "y"))
    blkdev, vol = reopen(path, blkdev)
    assert vol.disk.get_fnsize() == 107
    assert vol.read_file(F(name)) == b"long"
    blkdev.close()


def pfs3_meta_info_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path)
    vol.write_file(b"data", F("f"))
    node = vol.get_path_name(F("f"))
    node.change_comment(F("a comment"))
    node.change_protect_by_string("rwd")
    assert node.change_mod_ts_by_string("24.12.2020 18:00:00")
    with pytest.raises(FSError) as e:
        node.change_comment(F("c" * 80))
    assert e.value.code == INVALID_COMMENT
    # a comment that makes the entry move to another block
    node.change_comment(F("c" * 79))
    blkdev, vol = reopen(path, blkdev)
    mi = vol.get_path_name(F("f")).get_meta_info()
    assert mi.get_comment() == F("c" * 79)
    assert mi.get_protect() == 0x02
    assert str(mi.get_mod_ts()).startswith("24.12.2020 18:00:00")
    assert vol.read_file(F("f")) == b"data"
    assert_clean(vol)
    blkdev.close()


def pfs3_create_meta_info_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path)
    ts = TimeStamp()
    ts.parse("01.01.2000 12:00:00")
    mi = MetaInfo(protect=0x12340055, mod_ts=ts, comment=F("note"))
    vol.root_dir.create_file(F("f"), b"x", mi, False)
    vol.root_dir.create_dir(F("d"), mi, False)
    blkdev, vol = reopen(path, blkdev)
    for p in ("f", "d"):
        got = vol.get_path_name(F(p)).get_meta_info()
        assert got.get_protect() == 0x12340055
        assert got.get_comment() == F("note")
        assert str(got.get_mod_ts()) == str(ts)
    blkdev.close()


def pfs3_delete_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path)
    free = vol.get_free_blocks()
    vol.create_dir(F("d"))
    vol.create_dir(F("d/e"))
    vol.write_file(pattern(1, 9000), F("d/e/f"))
    vol.write_file(pattern(2, 9000), F("g"))
    with pytest.raises(FSError) as e:
        vol.delete(F("d"))
    assert e.value.code == DELETE_NOT_ALLOWED
    with pytest.raises(FSError):
        vol.delete(F(""))
    vol.delete(F("d"), all=True)
    blocks = [
        bn for nr, cs, bn, nx in vol.disk.get_chain(vol.get_path_name(F("g")).anode)
    ]
    vol.delete(F("g"), wipe=True)
    assert vol.get_free_blocks() == free
    assert vol.disk.read_blocks(blocks[0], 1) == bytes(vol.disk.B)
    assert_clean(vol)
    vol.write_file(b"x", F("h"))
    vol.delete(F(""), all=True)
    assert vol.root_dir.get_entries() == []
    assert vol.get_free_blocks() == free
    assert_clean(vol)
    blkdev.close()


def pfs3_full_volume_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path, size="1M")
    avail = vol.disk.get_alloc_available()
    with pytest.raises(FSError) as e:
        vol.write_file(bytes((avail + 1) * vol.disk.B), F("big"))
    assert e.value.code == NO_FREE_BLOCKS
    assert_clean(vol)
    vol.write_file(bytes(avail * vol.disk.B), F("big"))
    assert vol.disk.get_alloc_available() == 0
    assert_clean(vol)
    blkdev.close()


def pfs3_volume_meta_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path)
    vol.relabel(F("Other"))
    assert vol.change_create_ts_by_string("01.01.2001 00:00:00")
    assert vol.change_mod_ts_by_string("02.01.2001 00:00:00")
    assert vol.change_disk_ts_by_string("03.01.2001 00:00:00")
    with pytest.raises(FSError):
        vol.relabel(F("x" * 31))
    blkdev, vol = reopen(path, blkdev)
    mi = vol.get_meta_info()
    assert vol.get_volume_name() == F("Other")
    assert str(mi.get_create_ts()).startswith("01.01.2001")
    assert str(mi.get_mod_ts()).startswith("02.01.2001")
    assert str(mi.get_disk_ts()).startswith("03.01.2001")
    assert_clean(vol)
    blkdev.close()


# ----- failures -----


class InjectedError(IOError):
    pass


OPERATIONS = {
    "create": lambda v: v.write_file(pattern(9, 20000), F("new")),
    "mkdir": lambda v: v.create_dir(F("d/sub")),
    "delete": lambda v: v.delete(F("f05")),
    "delete_all": lambda v: v.delete(F("d"), all=True),
    "comment": lambda v: v.get_path_name(F("f03")).change_comment(F("c" * 60)),
    "rename": lambda v: v.rename(F("f03"), F("f03_now_with_a_longer_name")),
    "move": lambda v: v.rename(F("f04"), F("d/f04_with_a_long_name_too")),
    "move_dir": lambda v: v.rename(F("d"), F("e/d")),
    "soft_link": lambda v: v.create_soft_link(F("d/sl"), F("f05")),
    "hard_link": lambda v: v.create_hard_link(F("d/hl"), F("f06")),
    "chown": lambda v: v.get_path_name(F("f07")).change_owner(1000, 100),
}


@pytest.mark.parametrize("op", OPERATIONS)
def pfs3_failed_write_test(tmp_path, op):
    """a write that fails leaves the volume as it was, on disk and in
    memory, at every write of an operation"""
    base, blkdev, vol = new_volume(tmp_path, size="4M")
    for i in range(10):
        vol.write_file(pattern(i, i * 700), F("f%02d" % i))
    vol.create_dir(F("d"))
    for i in range(30):
        vol.write_file(pattern(i, i * 50), F("d/a_longer_name_%02d" % i))
    vol.create_dir(F("e"))
    before = tree(vol)
    blkdev.close()
    path = str(tmp_path / "work.hdf")
    n = 0
    while True:
        n += 1
        shutil.copy(base, path)
        blkdev, vol = reopen(path)
        io = vol.disk.io
        orig = io._write_secs
        count = [0]

        def write(sec, data, num):
            count[0] += 1
            if count[0] == n:
                raise InjectedError("injected")
            return orig(sec, data, num)

        io._write_secs = write
        try:
            OPERATIONS[op](vol)
            failed = False
        except InjectedError:
            failed = True
        io._write_secs = orig
        if failed:
            assert tree(vol) == before
        # the volume is still usable
        vol.write_file(b"after", F("after"))
        blkdev, vol = reopen(path, blkdev)
        result = vol.check()
        assert result.is_clean
        got = tree(vol)
        del got["/after"]
        if failed:
            assert got == before
        else:
            assert got != before
            break
        blkdev.close()
    blkdev.close()
    assert n > 2


def pfs3_read_only_test(tmp_path):
    """an interrupted operation that only the handler can finish, and
    unknown flags, make the volume read-only"""
    path, blkdev, vol = new_volume(tmp_path)
    vol.write_file(b"x", F("f"))
    ext = vol.disk.get_ext().blocknr
    blkdev.close()
    with open(path, "r+b") as fh:
        fh.seek(ext * 512 + 0x1C)
        fh.write(struct.pack(">I", PP_FREEANODECHAIN))
    blkdev, vol = reopen(path)
    assert vol.read_file(F("f")) == b"x"
    with pytest.raises(FSError) as e:
        vol.write_file(b"y", F("g"))
    assert e.value.code == VOLUME_READ_ONLY
    blkdev.close()


# ----- volumes of the PFS3 handler -----


def fixture_volume(tmp_path):
    path = fixture_image(tmp_path)
    blkdev = BlkDevFactory().open(path)
    return path, blkdev, open_volume(blkdev)


def pfs3_handler_fixture_read_test(tmp_path):
    path, blkdev, vol = fixture_volume(tmp_path)
    assert isinstance(vol, PFS3Volume)
    assert vol.get_volume_name() == F("Fixture")
    assert_clean(vol)

    def get(p):
        return vol.get_path_name(F(p))

    # files and hard links to them read as the file
    for p in ("file", "hl_file"):
        assert get(p).get_file_data() == pattern(1, 1000)
    for p in ("dir/inner", "dir/hl_inner"):
        assert get(p).get_file_data() == pattern(2, 3000)
    assert get("dir/sub/deep").get_file_data() == pattern(3, 513)
    assert get("empty").get_file_data() == b""
    assert get("hl_file").is_link() and get("hl_file").is_file()
    meta = get("file").get_meta_info()
    assert meta.get_comment() == F("a comment")
    assert meta.get_protect() == 0x55
    # a directory of several blocks
    d = get("dir")
    assert len(vol.disk.get_chain(d.anode)) == 3
    names = [e.name.get_unicode_name() for e in d.get_entries()]
    assert len(names) == 60 + 3
    for i in range(60):
        assert get("dir/entry_with_a_long_name_%02d" % i).get_file_data() == pattern(
            100 + i, i
        )
    # links that are no file
    assert get("sl_inner").get_target() == F("dir/inner")
    assert not get("sl_inner").is_file() and not get("sl_inner").is_dir()
    hl_sub = get("hl_sub")
    assert not hl_sub.is_dir()
    target = hl_sub.get_target_dir()
    assert [e.name.get_unicode_name() for e in target.get_entries()] == ["deep"]
    assert vol.read_file(F("hl_sub/deep")) == pattern(3, 513)
    # a rollover file that wrapped around keeps the last fsize - 1 bytes
    roll = get("roll")
    assert roll.entry.fsize == 2048 and roll.entry.rollpointer != 0
    assert roll.get_file_data() == (pattern(9, 1500) + pattern(10, 1500))[-2047:]
    # the deleted file
    slots = [s for s in vol.disk.deldir_slots() if s[3]]
    assert [(s[6], s[4]) for s in slots] == [(b"deleted", 700)]
    assert vol.disk.deldir_slot_valid(slots[0][3])
    blkdev.close()


def pfs3_handler_fixture_unpack_test(tmp_path):
    path, blkdev, vol = fixture_volume(tmp_path)
    out = str(tmp_path / "out")
    Imager(meta_mode=Imager.META_MODE_DB).unpack(vol, out)
    with open(os.path.join(out, "hl_file"), "rb") as fh:
        assert fh.read() == pattern(1, 1000)
    # links that are no file are not copied
    assert not os.path.exists(os.path.join(out, "sl_inner"))
    assert not os.path.exists(os.path.join(out, "hl_sub"))
    with open(out + ".xdfmeta") as fh:
        assert fh.readline().startswith("Fixture:PFS1,")
    blkdev.close()


def pfs3_handler_fixture_change_test(tmp_path):
    """delete links and objects that have links: the first link takes the
    place of a deleted object"""
    path, blkdev, vol = fixture_volume(tmp_path)

    def get(p):
        return vol.get_path_name(F(p))

    vol.delete(F("hl_file"))
    assert get("file").entry.link == 0
    assert_clean(vol)
    # the directory and its link: hl_sub becomes the directory
    vol.delete(F("dir/sub"), all=True)
    assert_clean(vol)
    assert get("hl_sub").is_dir() and get("hl_sub").entry.type == ST_USERDIR
    assert get("hl_sub").get_entries() == []
    # the object and its link in the same directory
    vol.delete(F("dir/inner"))
    assert get("dir/hl_inner").entry.type == ST_FILE
    assert get("dir/hl_inner").get_file_data() == pattern(2, 3000)
    assert_clean(vol)
    vol.delete(F("sl_inner"))
    vol.delete(F("roll"))
    vol.write_file(pattern(5, 4000), F("hl_sub/new"))
    assert_clean(vol)
    blkdev, vol = reopen(path, blkdev)
    assert vol.read_file(F("hl_sub/new")) == pattern(5, 4000)
    assert vol.read_file(F("dir/hl_inner")) == pattern(2, 3000)
    assert vol.disk.dir_parent(get("hl_sub").anode) == ANODE_ROOTDIR
    assert_clean(vol)
    blkdev.close()


def pfs3_handler_fixture_delete_all_test(tmp_path):
    path, blkdev, vol = fixture_volume(tmp_path)
    free = vol.get_free_blocks()
    vol.delete(F("dir"), all=True)
    assert_clean(vol)
    names = sorted(e.name.get_unicode_name() for e in vol.root_dir.get_entries())
    assert "dir" not in names and "hl_sub" in names
    vol.delete(F(""), all=True)
    assert vol.root_dir.get_entries() == []
    assert vol.get_free_blocks() > free
    assert_clean(vol)
    blkdev.close()


def pfs3_deldir_reuse_test(tmp_path):
    """once a block of a deleted file is taken, its anodes are freed"""
    path, blkdev, vol = fixture_volume(tmp_path)
    d = vol.disk
    slot = [s for s in d.deldir_slots() if s[3]][0]
    i = 0
    while d.deldir_slot_valid(slot[3]):
        if d.get_alloc_available() < 8:
            pytest.fail("deleted file's blocks not reused")
        vol.write_file(pattern(i, 8 * d.B), F("fill%03d" % i))
        i += 1
    assert [s[3] for s in d.deldir_slots() if s[0] == slot[0]] == [0]
    assert_clean(vol)
    blkdev.close()


def pfs3_defrag_refuses_links_test(tmp_path, capsys):
    path = fixture_image(tmp_path)
    assert xdftool_main([path, "defrag"]) == 3
    blkdev, vol = reopen(path)
    assert vol.read_file(F("hl_file")) == pattern(1, 1000)
    assert_clean(vol)
    blkdev.close()


# ----- tools -----


def pfs3_xdftool_test(tmp_path, capsys):
    img = str(tmp_path / "x.hdf")
    data = tmp_path / "data.bin"
    data.write_bytes(pattern(1, 12345))
    assert xdftool_main([img, "create", "size=4M", "+", "format", "Work", "pfs3"]) == 0
    assert (
        xdftool_main(
            [
                img,
                "write",
                str(data),
                "+",
                "makedir",
                "d",
                "+",
                "write",
                str(data),
                "d/x",
            ]
        )
        == 0
    )
    assert (
        xdftool_main([img, "comment", "data.bin", "hi", "+", "protect", "d/x", "rwd"])
        == 0
    )
    capsys.readouterr()
    assert xdftool_main([img, "list"]) == 0
    out = capsys.readouterr().out
    assert "PFS1:pfs3" in out and "data.bin" in out and "hi" in out
    assert xdftool_main([img, "read", "d/x", str(tmp_path / "out.bin")]) == 0
    assert (tmp_path / "out.bin").read_bytes() == pattern(1, 12345)
    assert xdftool_main([img, "fsck"]) == 0
    assert "clean" in capsys.readouterr().out
    for cmd in (
        ["info"],
        ["bitmap", "info"],
        ["root", "show"],
        ["block", "decode", "2"],
    ):
        assert xdftool_main([img] + cmd) == 0
    assert xdftool_main([img, "boot", "install"]) == 1
    assert xdftool_main([img, "delete", "d", "all"]) == 0
    assert xdftool_main([img, "defrag", "+", "fsck"]) == 0


def pfs3_rdb_partition_test(tmp_path, capsys):
    img = str(tmp_path / "disk.rdb")
    args = ["-f", img, "create", "size=12Mi", "+", "init", "+", "add"]
    assert rdbtool_main(args + ["name=DH0", "size=50%", "dostype=pfs3"]) == 0
    assert (
        rdbtool_main([img, "add", "name=DH1", "size=40%", "dostype=PFS3", "bs=1024"])
        == 0
    )
    assert xdftool_main([img, "format", "Zero", "pfs3"]) == 0
    assert xdftool_main([img, "open", "part=1", "+", "format", "One", "pfs3"]) == 0
    for part, name, B, disktype in (
        ("0", "Zero", 512, ID_PFS1),
        ("1", "One", 1024, ID_PFS2),
    ):
        blkdev = BlkDevFactory().open(img, options={"part": part})
        vol = open_volume(blkdev)
        assert vol.get_volume_name() == F(name)
        assert vol.disk.B == B and vol.disk.disktype == disktype
        # partitions do not start at cylinder 0: no stored geometry
        assert not vol.disk.options & MODE_STORED_GEOM or disktype == ID_PFS2
        vol.write_file(pattern(2, 5000), F("f"))
        assert vol.read_file(F("f")) == pattern(2, 5000)
        assert_clean(vol)
        blkdev.close()


def stored_dos_type(vol):
    """the DosType of the DosEnvec stored in the root block extension"""
    data = vol.disk.get_ext().data
    n = struct.unpack_from(">I", data, 0x110)[0]
    return struct.unpack_from(">I", data, 0x110 + 4 * n)[0]


def pfs3_pds3_partition_test(tmp_path):
    """PDS\\3 partitions (direct SCSI variant) hold the same PFS3 format"""
    # the handler's volume on a partition relabelled to PDS\3
    img = fixture_image(tmp_path)
    assert rdbtool_main([img, "change", "0", "dostype=PDS3"]) == 0
    blkdev = BlkDevFactory().open(img, options={"part": "0"})
    vol = open_volume(blkdev)
    assert isinstance(vol, PFS3Volume)
    assert vol.get_path_name(F("file")).get_file_data() == pattern(1, 1000)
    vol.write_file(pattern(3, 2000), F("new"))
    assert_clean(vol)
    blkdev.close()
    # formatting a PDS\3 partition with either dos type keeps PDS\3 in the
    # stored DosEnvec, as the handler would
    for dos_str in ("pfs3", "PDS3"):
        img = str(tmp_path / ("pds3_%s.rdb" % dos_str))
        args = ["-f", img, "create", "size=4Mi", "+", "init", "+", "add"]
        assert rdbtool_main(args + ["name=DH0", "size=100%", "dostype=PDS3"]) == 0
        assert xdftool_main([img, "open", "part=0", "+", "format", "W", dos_str]) == 0
        blkdev = BlkDevFactory().open(img, options={"part": "0"})
        vol = open_volume(blkdev)
        assert isinstance(vol, PFS3Volume) and vol.disk.disktype == ID_PFS1
        assert stored_dos_type(vol) == DosType.PDS3
        assert_clean(vol)
        blkdev.close()
    # a whole image formatted as PDS3 stores that dos type
    img = str(tmp_path / "pds3.hdf")
    assert xdftool_main([img, "create", "size=4M", "+", "format", "W", "pds3"]) == 0
    blkdev, vol = reopen(img)
    assert vol.disk.disktype == ID_PFS1 and stored_dos_type(vol) == DosType.PDS3
    blkdev.close()


def pfs3_pack_unpack_test(tmp_path):
    src = tmp_path / "Vol"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "x").write_bytes(pattern(1, 3000))
    long_name = "a_name_that_is_longer_than_thirty_one_characters"
    (src / long_name).write_bytes(pattern(2, 100))
    img = str(tmp_path / "pack.hdf")
    assert xdftool_main([img, "pack", str(src), "pfs3", "size=4M"]) == 0
    blkdev, vol = reopen(img)
    assert vol.disk.get_fnsize() == len(long_name) + 1
    assert vol.read_file(F(long_name)) == pattern(2, 100)
    blkdev.close()
    out = tmp_path / "out"
    assert xdftool_main([img, "unpack", str(out)]) == 0
    assert (out / "sub" / "x").read_bytes() == pattern(1, 3000)
    assert (out / long_name).read_bytes() == pattern(2, 100)
    # the meta data keeps the dos type: packing it again makes PFS3
    img2 = str(tmp_path / "pack2.hdf")
    assert xdftool_main([img2, "pack", str(out), "size=4M"]) == 0
    blkdev, vol = reopen(img2)
    assert isinstance(vol, PFS3Volume)
    assert vol.read_file(F("sub/x")) == pattern(1, 3000)
    blkdev.close()
    # repack keeps the long names
    img3 = str(tmp_path / "repack.hdf")
    assert xdftool_main([img3, "repack", img]) == 0
    blkdev, vol = reopen(img3)
    assert vol.read_file(F(long_name)) == pattern(2, 100)
    assert_clean(vol)
    blkdev.close()


def pfs3_pack_boot_code_test(tmp_path, capsys):
    """boot code of an unpacked OFS/FFS disk cannot go to a PFS3 volume"""
    src = tmp_path / "Vol"
    src.mkdir()
    (src / "f").write_bytes(b"x")
    (tmp_path / "Vol.bootcode").write_bytes(b"\x4e\x75")
    img = str(tmp_path / "pack.hdf")
    assert xdftool_main([img, "pack", str(src), "pfs3", "size=4M"]) == 3
    assert "no boot code" in capsys.readouterr().out


# ----- renames, links and owners -----


def link_names(vol, path):
    """the names of the hard links of the object at path, in list order"""
    disk = vol.disk
    out = []
    for nr in vol._link_nodes(vol.get_path_name(F(path)).entry.link):
        obj_dir, link_dir, nx = disk.get_anode(nr)
        out.append(disk.find_entry(link_dir, nr)[2].name.decode("latin-1"))
    return out


def pfs3_rename_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path)
    vol.write_file(pattern(1, 3000), F("f"))
    vol.create_dir(F("a"))
    vol.create_dir(F("a/b"))
    vol.write_file(pattern(2, 700), F("a/b/x"))
    vol.create_dir(F("c"))
    for i in range(40):
        vol.write_file(b"", F("c/a_name_that_is_fairly_long_%02d" % i))
    # in the same directory, then only its case
    vol.rename(F("f"), F("g"))
    vol.rename(F("g"), F("G"))
    assert vol.get_path_name(F("G")).name.get_unicode_name() == "G"
    # into another directory
    vol.rename(F("G"), F("c/moved_file_with_a_long_name"))
    assert vol.get_path_name(F("G")) is None
    assert vol.read_file(F("c/moved_file_with_a_long_name")) == pattern(1, 3000)
    # a directory and its contents: its dir blocks name the new parent
    vol.rename(F("a/b"), F("c/b"))
    c = vol.get_path_name(F("c")).anode
    assert vol.disk.dir_parent(vol.get_path_name(F("c/b")).anode) == c
    assert vol.read_file(F("c/b/x")) == pattern(2, 700)
    assert_clean(vol)
    for old, new, code in (
        ("c/b", "c/b/inside", INVALID_PARENT_DIRECTORY),
        ("c", "c/b/deeper", INVALID_PARENT_DIRECTORY),
        ("a", "c/b", NAME_ALREADY_EXISTS),
        ("c/moved_file_with_a_long_name", "c/b/x", NAME_ALREADY_EXISTS),
        ("c/b/x", "c/b/a_name_longer_than_31_characters", INVALID_FILE_NAME),
        ("missing", "y", FILE_NOT_FOUND),
        ("", "y", DELETE_NOT_ALLOWED),
    ):
        with pytest.raises(FSError) as e:
            vol.rename(F(old), F(new))
        assert e.value.code == code, (old, new)
    blkdev, vol = reopen(path, blkdev)
    assert vol.read_file(F("c/b/x")) == pattern(2, 700)
    assert vol.get_path_name(F("a")).get_entries() == []
    assert_clean(vol)
    blkdev.close()


def pfs3_rename_links_test(tmp_path):
    """the link nodes of a moved object name its new directory, the node of
    a moved link names the link's new directory"""
    path, blkdev, vol = fixture_volume(tmp_path)
    disk = vol.disk

    def get(p):
        return vol.get_path_name(F(p))

    vol.create_dir(F("new"))
    new = get("new").anode
    vol.rename(F("file"), F("new/file"))
    assert disk.get_anode(get("hl_file").entry.anode)[0] == new
    assert get("hl_file").get_file_data() == pattern(1, 1000)
    vol.rename(F("dir/hl_inner"), F("new/hl_inner"))
    assert disk.get_anode(get("new/hl_inner").entry.anode)[1] == new
    assert get("new/hl_inner").get_file_data() == pattern(2, 3000)
    # a directory with a link: the link node and its dir blocks follow
    vol.rename(F("dir/sub"), F("new/sub"))
    assert disk.dir_parent(get("new/sub").anode) == new
    assert disk.get_anode(get("hl_sub").entry.anode)[0] == new
    assert get("hl_sub/deep").get_file_data() == pattern(3, 513)
    assert_clean(vol)
    # deleting a moved object still promotes its first link
    vol.delete(F("new/file"))
    assert get("hl_file").entry.type == ST_FILE
    assert get("hl_file").get_file_data() == pattern(1, 1000)
    assert_clean(vol)
    blkdev.close()


def pfs3_soft_link_test(tmp_path, capsys):
    path, blkdev, vol = new_volume(tmp_path)
    vol.write_file(b"x", F("f"))
    vol.create_dir(F("d"))
    vol.create_soft_link(F("d/rel"), F("/f"))
    vol.create_soft_link(F("abs"), F("Test:f"))
    link = vol.get_path_name(F("abs"))
    assert link.is_link() and not link.is_file() and not link.is_dir()
    assert link.entry.type == ST_SOFTLINK and link.entry.fsize == 6
    assert link.get_target() == F("Test:f")
    assert vol.disk.chain_block_count(link.anode) == 1
    # the target fills at most its block, with the terminator
    B = vol.disk.B
    vol.create_soft_link(F("longest"), F("x" * (B - 1)))
    for name, target, code in (
        ("too_long", "x" * B, INVALID_FILE_NAME),
        ("f", "other", NAME_ALREADY_EXISTS),
    ):
        with pytest.raises(FSError) as e:
            vol.create_soft_link(F(name), F(target))
        assert e.value.code == code
    assert_clean(vol)
    blkdev, vol = reopen(path, blkdev)
    assert vol.get_link_path_name(F("d/rel")).get_target() == F("/f")
    assert vol.get_path_name(F("longest")).get_target() == F("x" * (B - 1))
    assert_clean(vol)
    blkdev.close()
    capsys.readouterr()
    assert xdftool_main([path, "readlink", "d/rel"]) == 0
    assert capsys.readouterr().out.strip() == "/f"


def pfs3_hard_link_test(tmp_path):
    path, blkdev, vol = new_volume(tmp_path)
    disk = vol.disk

    def get(p):
        return vol.get_path_name(F(p))

    vol.write_file(pattern(1, 2000), F("f"))
    vol.create_dir(F("d"))
    vol.write_file(pattern(2, 100), F("d/x"))
    vol.create_hard_link(F("d/l1"), F("f"))
    vol.create_hard_link(F("l2"), F("f"))
    # a link to a link links to its object
    vol.create_hard_link(F("d/l3"), F("d/l1"))
    # the first link stays first: it takes over when the object goes
    assert link_names(vol, "f") == ["l1", "l3", "l2"]
    d = get("d").anode
    for p, link_dir in (("d/l1", d), ("l2", ANODE_ROOTDIR), ("d/l3", d)):
        e = get(p).entry
        assert e.type == ST_LINKFILE and e.link == get("f").anode
        assert e.fsize == 2000
        assert disk.get_anode(e.anode)[:2] == (ANODE_ROOTDIR, link_dir)
        assert get(p).get_file_data() == pattern(1, 2000)
    # a link to a directory, followed in paths
    vol.create_hard_link(F("dl"), F("d"))
    assert get("dl").entry.type == ST_LINKDIR
    assert vol.read_file(F("dl/x")) == pattern(2, 100)
    assert_clean(vol)
    vol.create_soft_link(F("s"), F("f"))
    for name, target, code in (
        ("r", "", LINK_NOT_ALLOWED),
        ("ls", "s", LINK_NOT_ALLOWED),
        ("l2", "f", NAME_ALREADY_EXISTS),
        ("m", "missing", FILE_NOT_FOUND),
    ):
        with pytest.raises(FSError) as e:
            vol.create_hard_link(F(name), F(target))
        assert e.value.code == code, name
    # the object goes: its first link takes its place
    vol.delete(F("f"))
    assert get("d/l1").entry.type == ST_FILE
    assert link_names(vol, "d/l1") == ["l3", "l2"]
    assert get("l2").get_file_data() == pattern(1, 2000)
    assert_clean(vol)
    blkdev, vol = reopen(path, blkdev)
    assert vol.read_file(F("d/l3")) == pattern(1, 2000)
    assert_clean(vol)
    blkdev.close()


def pfs3_owner_test(tmp_path, capsys):
    path, blkdev, vol = new_volume(tmp_path)
    vol.write_file(b"x", F("f"))
    vol.create_dir(F("d"))
    vol.get_path_name(F("f")).change_owner(1000, 100)
    vol.get_path_name(F("d")).change_owner(0xFFFF, 1)
    with pytest.raises(FSError) as e:
        vol.root_dir.change_owner(1, 1)
    assert e.value.code == UNSUPPORTED_OPERATION
    with pytest.raises(ValueError):
        vol.get_path_name(F("f")).change_owner(0x10000, 0)
    blkdev, vol = reopen(path, blkdev)
    f = vol.get_path_name(F("f"))
    assert (f.entry.uid, f.entry.gid) == (1000, 100)
    mi = f.get_meta_info()
    assert (mi.get_owner_uid(), mi.get_owner_gid()) == (1000, 100)
    assert_clean(vol)
    blkdev.close()
    # list shows owners, and repack keeps them
    capsys.readouterr()
    assert xdftool_main([path, "list"]) == 0
    assert "65535 1" in capsys.readouterr().out
    img2 = str(tmp_path / "repack.hdf")
    assert xdftool_main([img2, "repack", path]) == 0
    blkdev, vol = reopen(img2)
    d = vol.get_path_name(F("d"))
    assert (d.entry.uid, d.entry.gid) == (0xFFFF, 1)
    vol.get_path_name(F("f")).change_owner(0, 0)
    assert vol.get_path_name(F("f")).get_meta_info().get_owner_str() == ""
    assert_clean(vol)
    blkdev.close()


def pfs3_link_commands_test(tmp_path, capsys):
    """xdftool's rename, makelink, readlink and chown on a PFS3 volume"""
    img = str(tmp_path / "u.hdf")
    assert xdftool_main([img, "create", "size=4M", "+", "format", "W", "pfs3"]) == 0
    src = tmp_path / "f"
    src.write_bytes(b"x")
    assert xdftool_main([img, "write", str(src)]) == 0
    for cmd in (
        ["rename", "f", "g"],
        ["makedir", "d"],
        ["makelink", "d/sl", "g"],
        ["makelink", "hl", "g", "hard"],
        ["chown", "g", "1", "2"],
        ["rename", "hl", "d/hl"],
    ):
        assert xdftool_main([img] + cmd) == 0, cmd
    capsys.readouterr()
    assert xdftool_main([img, "readlink", "d/sl"]) == 0
    assert xdftool_main([img, "readlink", "d/hl"]) == 0
    assert capsys.readouterr().out.split() == ["g", "g"]
    assert xdftool_main([img, "readlink", "g"]) == 2
    assert xdftool_main([img, "fsck"]) == 0
    blkdev, vol = reopen(img)
    assert vol.read_file(F("d/hl")) == b"x"
    assert vol.get_path_name(F("g")).entry.uid == 1
    blkdev.close()


def pfs3_metadb_dos_type_test(tmp_path):
    db = MetaDB()
    db.set_volume_name("V")
    db.set_root_meta_info(RootMetaInfo(TimeStamp(), TimeStamp(), TimeStamp()))
    for dos_type in (
        DosType.PFS1,
        DosType.PFS2,
        DosType.PFS3,
        DosType.PDS3,
        DosType.DOS3,
    ):
        db.set_dos_type(dos_type)
        path = str(tmp_path / "v.xdfmeta")
        db.save(path)
        db2 = MetaDB()
        db2.load(path)
        assert db2.get_dos_type() == dos_type


def pfs3_open_volume_ofs_test(tmp_path):
    """open_volume() keeps opening OFS/FFS volumes"""
    img = str(tmp_path / "x.adf")
    assert xdftool_main([img, "create", "+", "format", "Foo", "ffs"]) == 0
    blkdev = BlkDevFactory().open(img)
    assert not is_pfs3_blkdev(blkdev)
    vol = open_volume(blkdev)
    assert not getattr(vol, "is_pfs3", False)
    assert vol.get_volume_name() == F("Foo")
    blkdev.close()
