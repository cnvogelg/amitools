import pytest
import collections
import os

from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs import DosType


# tag a parameter for full testing
def tag_full(value):
    return pytest.param(value, marks=pytest.mark.full)


ADF_LIST = (
    tag_full("amiga-os-100-workbench.adf"),
    tag_full("amiga-os-110-workbench.adf"),
    tag_full("amiga-os-120-workbench.adf"),
    tag_full("amiga-os-134-extras.adf"),
    tag_full("amiga-os-134-workbench.adf"),
    tag_full("amiga-os-200-workbench.adf"),
    tag_full("amiga-os-204-workbench.adf"),
    tag_full("amiga-os-210-workbench.adf"),
    tag_full("amiga-os-300-workbench.adf"),
    "amiga-os-310-extras.adf",
    "amiga-os-310-fonts.adf",
    "amiga-os-310-install.adf",
    "amiga-os-310-locale.adf",
    "amiga-os-310-storage.adf",
    "amiga-os-310-workbench.adf",
    "aros-20130502-boot.adf",
)

DOS_FORMATS = (
    "DOS0",
    "DOS1",
    tag_full("DOS2"),
    tag_full("DOS3"),
    tag_full("DOS4"),
    tag_full("DOS5"),
    tag_full("DOS6"),
    tag_full("DOS7"),
)

DISK_SIZES = ("880K", "1M", tag_full("10M"))

XDFSpec = collections.namedtuple(
    "XDFSpec", ["file_name", "size", "vol_name", "dos_format"]
)

DATA_bytes = bytes([x for x in range(256)])
DATA_10k = bytes([x % 256 for x in range(10 * 1024)])
DATA_100k = bytes([x % 256 for x in range(100 * 1024)])

TEST_DATA = {
    "empty": b"",
    "hello": b"hello, world!",
    "byterange": DATA_bytes,
    "10k": DATA_10k,
    "100k": DATA_100k,
}
TEST_DATA_FULL = ["100k"]
TEST_DATA_KEYS = [tag_full(a) if a in TEST_DATA_FULL else a for a in TEST_DATA]

DataFile = collections.namedtuple("DataFile", ["file_path", "file_name", "data"])

TEST_TREES = {
    "simple": {"foo": {}, "bar": b"Hello, world!"},
    "deep": {
        "foo": {"bar": {"baz": {"hello": b"Hello, world!"}}},
    },
    "data": {"bytes": DATA_bytes, "10k": DATA_10k, "100k": DATA_100k},
    "latin": {"H\u00e4ll\u00f6": DATA_bytes, "D\u00dcR": {}},
}
TEST_TREES_FULL = ["100k"]
TEST_TREES_KEYS = [tag_full(a) if a in TEST_TREES_FULL else a for a in TEST_TREES]

VOLUME_NAMES = ["Foo", "F\u00e4\u00f6"]


@pytest.fixture(params=ADF_LIST)
def adf_file(request, toolrun):
    rom = "disks/" + request.param
    toolrun.skip_if_data_file_not_available(rom)
    return rom


@pytest.fixture(params=DOS_FORMATS)
def dos_format(request):
    return request.param


@pytest.fixture(params=VOLUME_NAMES)
def vol_name(request):
    return request.param


@pytest.fixture(params=DISK_SIZES)
def xdfs(request, tmpdir, vol_name, dos_format):
    """return (xdf_file, xdf_size_spec, vol_name) for various disks"""
    size = request.param
    if size == "880K":
        file_name = tmpdir / "disk.adf"
        size = ""
    else:
        file_name = tmpdir / "disk-" + size + ".hdf"
        size = "size=" + size
    return XDFSpec(str(file_name), size, vol_name, dos_format)


@pytest.fixture
def xdftool(toolrun):
    def run(xdf_file, *cmds, raw_output=False):
        args = []
        for cmd in cmds:
            if type(cmd) in (tuple, list):
                # command args are given in tuple
                for c in cmd:
                    if c:
                        args.append(c)
            else:
                # single command
                args.append(cmd)
            # plus separates commands
            args.append("+")
        return toolrun.run_checked(
            "xdftool", xdf_file, *args[:-1], raw_output=raw_output
        )

    return run


@pytest.fixture
def xdf_img(xdftool, xdfs):
    """create formatted image"""
    xdftool(
        xdfs.file_name,
        ("create", xdfs.size),
        ("format", xdfs.vol_name, xdfs.dos_format),
    )
    return xdfs


class XDFFileTree:
    def __init__(self, xdftool, xdf_img, name, tree, tmpdir):
        self.name = name
        self.xdftool = xdftool
        self.xdf_img = xdf_img
        self.img_file = xdf_img.file_name
        self.vol_name = xdf_img.vol_name
        self.tree = tree
        self.tmpdir = tmpdir

    def _create_node_cmds(self, node, path, cmds):
        path_name = "/".join(path)
        real_path = os.path.join(self.tmpdir, path_name)
        if isinstance(node, dict):
            cmds.append(("makedir", path_name))
            os.mkdir(real_path)
            for name in node:
                self._create_node_cmds(node[name], path + [name], cmds)
        else:
            with open(real_path, "wb") as fh:
                fh.write(node)
            cmds.append(("write", real_path, path_name))

    def create(self):
        """create tree in xdftool"""
        cmds = []
        for node in self.tree:
            self._create_node_cmds(self.tree[node], [node], cmds)
        self.xdftool(self.img_file, *cmds)

    def _check_node(self, node, path):
        path_name = "/".join(path)
        # list entry
        output = self.xdftool(self.img_file, ("list", path_name))
        # split
        _, size, *_ = output[0].split()
        if isinstance(node, dict):
            assert size == "DIR"
            for name in node:
                self._check_node(node[name], path + [name])
        else:
            data = self.xdftool(self.img_file, ("type", path_name), raw_output=True)
            assert data == node

    def check(self):
        """compare data in image with file sys"""
        for node in self.tree:
            self._check_node(self.tree[node], [node])

    def _delete_node_cmds(self, node, path, cmds):
        path_name = "/".join(path)
        if isinstance(node, dict):
            for name in node:
                self._delete_node_cmds(node[name], path + [name], cmds)
        cmds.append(("delete", path_name))

    def delete(self):
        cmds = []
        for node in self.tree:
            self._delete_node_cmds(self.tree[node], [node], cmds)
        self.xdftool(self.img_file, *cmds)

    def get_file_tree(self):
        return FileTree(self.name, self.tree, self.tmpdir)


class FileTree:
    def __init__(self, name, tree, tmpdir):
        self.name = name
        self.tree = tree
        self.tmpdir = tmpdir

    def _create_node(self, node, path):
        path_name = "/".join(path)
        real_path = os.path.join(self.tmpdir, path_name)
        if isinstance(node, dict):
            os.mkdir(real_path)
            for name in node:
                self._create_node(node[name], path + [name])
        else:
            with open(real_path, "wb") as fh:
                fh.write(node)

    def create(self):
        """only write files to file system"""
        for node in self.tree:
            self._create_node(self.tree[node], [node])

    def _check_node(self, node, path):
        path_name = "/".join(path)
        real_path = os.path.join(self.tmpdir, path_name)
        if isinstance(node, dict):
            assert os.path.isdir(real_path)
            for name in node:
                self._check_node(node[name], path + [name])
        else:
            with open(real_path, "rb") as fh:
                data = fh.read()
                assert data == node

    def check(self):
        """compare data on file sys with the tree"""
        for node in self.tree:
            self._check_node(self.tree[node], [node])

    def _delete_node(self, node, path):
        path_name = "/".join(path)
        real_path = os.path.join(self.tmpdir, path_name)
        if isinstance(node, dict):
            for name in node:
                self._delete_node(node[name], path + [name])
            os.rmdir(real_path)
        else:
            os.remove(real_path)

    def delete(self):
        for node in self.tree:
            self._delete_node(self.tree[node], [node])

    def get_xdf_file_tree(self, img_file, xdftool):
        return XDFFileTree(xdftool, img_file, self.name, self.tree, self.tmpdir)


@pytest.fixture(params=TEST_TREES_KEYS)
def xdf_file_tree(request, xdf_img, xdftool, tmpdir):
    test_tree = request.param
    tree = TEST_TREES[test_tree]
    my_dir = tmpdir.mkdir(test_tree)
    return XDFFileTree(xdftool, xdf_img, test_tree, tree, str(my_dir))


@pytest.fixture(params=TEST_TREES_KEYS)
def file_tree(request, tmpdir):
    test_tree = request.param
    tree = TEST_TREES[test_tree]
    my_dir = tmpdir.mkdir(test_tree)
    return FileTree(test_tree, tree, str(my_dir))


@pytest.fixture(params=TEST_DATA_KEYS)
def test_files(request, tmpdir):
    test_file = request.param
    data = TEST_DATA[test_file]
    test_path = tmpdir / test_file
    with open(str(test_path), "wb") as fh:
        fh.write(data)
    return DataFile(str(test_path), test_file, data)


# ----- rdbtool helper -----


@pytest.fixture
def rdbtool(toolrun):
    def run(rdb_file, *cmds, raw_output=False):
        args = []
        for cmd in cmds:
            if type(cmd) in (tuple, list):
                # command args are given in tuple
                for c in cmd:
                    if c:
                        args.append(c)
            else:
                # single command
                args.append(cmd)
            # plus separates commands
            args.append("+")
        return toolrun.run_checked(
            "rdbtool", rdb_file, *args[:-1], raw_output=raw_output
        )

    return run


# list of (partions, rdbtool commands)
TEST_RDB_FILES = [
    (("DH0",), (("create", "size=10M"), ("init",), ("fill",))),
    (
        ("DH0", "DH1"),
        (("create", "size=10M"), ("init",), ("add", "size=50%"), ("fill",)),
    ),
]


@pytest.fixture(params=TEST_RDB_FILES)
def rdb_files(request, rdbtool, tmpdir):
    num_part, rdbtool_cmds = request.param
    rdb_file = str(tmpdir / "test.rdb")
    rdbtool(rdb_file, *rdbtool_cmds)
    return num_part, rdb_file


# ----- tests -----


def xdftool_list_test(xdftool, adf_file):
    """list contents of various disks"""
    xdftool(adf_file, "list")


def xdftool_create_test(xdftool, xdfs):
    """create an empty disk image"""
    xdftool(xdfs.file_name, ("create", xdfs.size))


def xdftool_format_test(xdftool, xdfs):
    """format disk image"""
    xdftool(
        xdfs.file_name,
        ("create", xdfs.size),
        ("format", xdfs.vol_name, xdfs.dos_format),
    )
    xdftool(xdfs.file_name, "list")


def xdftool_format_adf_test(xdftool, dos_format, tmpdir, vol_name):
    """format disk image without create first"""
    file_name = str(tmpdir / "test.adf")
    xdftool(file_name, ("format", vol_name, dos_format))
    xdftool(file_name, "list")


def xdftool_relabel_adf_test(xdftool, dos_format, tmpdir, vol_name):
    """format disk image without create first"""
    file_name = str(tmpdir / "test.adf")
    xdftool(file_name, ("format", vol_name, dos_format))
    xdftool(file_name, "list")
    xdftool(file_name, ("relabel", "FooBar"))
    xdftool(file_name, "list")


def xdftool_write_read_test(xdftool, xdf_img, test_files):
    """write a file and read it back"""
    # write file
    xdftool(xdf_img.file_name, ("write", test_files.file_path))
    # read file back
    read_file = test_files.file_path + "-read"
    xdftool(xdf_img.file_name, ("read", test_files.file_name, read_file))
    # compare
    with open(read_file, "rb") as fh:
        read_data = fh.read()
        assert read_data == test_files.data
    # type file
    output = xdftool(xdf_img.file_name, ("type", test_files.file_name), raw_output=True)
    assert output == test_files.data


def xdftool_write_delete_test(xdftool, xdf_img, test_files):
    """write a file and delete it"""
    # write file
    xdftool(xdf_img.file_name, ("write", test_files.file_path))
    # delete it
    xdftool(xdf_img.file_name, ("delete", test_files.file_name))


def xdftool_write_delete_wipe_test(xdftool, xdf_img, test_files):
    """write a file and delete it with wipe option"""
    # write file
    xdftool(xdf_img.file_name, ("write", test_files.file_path))
    # delete it
    xdftool(xdf_img.file_name, ("delete", test_files.file_name, "wipe"))


def xdftool_makedir_test(xdftool, xdf_img):
    # create dir
    xdftool(xdf_img.file_name, ("makedir", "bla"))
    # delete it
    xdftool(xdf_img.file_name, ("delete", "bla"))


def xdftool_create_tree_test(xdftool, xdf_file_tree):
    """create various file/dir trees"""
    file_tree = xdf_file_tree.get_file_tree()
    # build tree
    xdf_file_tree.create()
    # check file system consistency
    file_tree.check()
    # check created tree
    xdf_file_tree.check()
    # delete tree
    xdf_file_tree.delete()
    # delete on file system
    file_tree.delete()


def xdftool_pack_test(xdftool, xdf_file_tree):
    # create test files in fs
    file_tree = xdf_file_tree.get_file_tree()
    file_tree.create()
    # pack tree
    xdftool(xdf_file_tree.img_file, ("pack", file_tree.tmpdir))
    # check image contents
    xdf_file_tree.check()


def xdftool_unpack_test(xdftool, xdf_file_tree):
    # create test files in xdf
    xdf_file_tree.create()
    # clean test files
    file_tree = xdf_file_tree.get_file_tree()
    file_tree.delete()
    # unpack tree from xdf to fs
    xdftool(xdf_file_tree.img_file, ("unpack", file_tree.tmpdir))
    # check fs contents
    file_tree.tmpdir = os.path.join(file_tree.tmpdir, xdf_file_tree.vol_name)
    file_tree.check()


def xdftool_pack_unpack_test(xdftool, xdf_file_tree):
    # create test files in fs
    file_tree = xdf_file_tree.get_file_tree()
    file_tree.create()
    # pack tree
    xdftool(xdf_file_tree.img_file, ("pack", file_tree.tmpdir))
    # check image contents
    xdf_file_tree.check()
    # delete files in fs
    file_tree.delete()
    # unpack tree from xdf to fs
    xdftool(xdf_file_tree.img_file, ("unpack", file_tree.tmpdir))
    # check fs contents
    file_tree.tmpdir = os.path.join(file_tree.tmpdir, file_tree.name)
    file_tree.check()


# rdb partition tests


def xdftool_rdb_open_part_by_name_test(xdftool, rdb_files):
    part_list, rdb_file = rdb_files
    for part in part_list:
        xdftool(rdb_file, ("open", "part=" + part))


def xdftool_rdb_open_part_by_num_test(xdftool, rdb_files):
    part_list, rdb_file = rdb_files
    for part in range(len(part_list)):
        xdftool(rdb_file, ("open", "part=" + str(part)))


def xdftool_rdb_open_format_test(xdftool, rdb_files):
    part_list, rdb_file = rdb_files
    for part in part_list:
        name = "foo_" + part
        xdftool(rdb_file, ("open", "part=" + part), ("format", name), ("list",))
    # list again
    for part in part_list:
        xdftool(rdb_file, ("open", "part=" + part), ("list",))


# ----- FileListBlock interleave tests -----


def _open_file_node(img_file, ami_path):
    """open image read-only and return (blkdev, volume, file node, ppb)."""
    factory = BlkDevFactory()
    blkdev = factory.open(img_file, read_only=True)
    vol = ADFSVolume(blkdev)
    vol.open()
    from amitools.fs.FSString import FSString

    node = vol.get_path_name(FSString(ami_path))
    assert node is not None and node.is_file()
    ppb = blkdev.block_longs - 56
    return blkdev, vol, node, ppb


def _assert_interleaved(node, ppb, max_gap=8):
    """each FLB must sit right next to the data chunk it describes.

    read order is hdr, data[0:ppb], ext0, data[ppb:2*ppb], ext1, ...
    so ext[i] must be adjacent to data[ppb+i*ppb] (first block of its
    chunk). the old clustered layout puts all ext blocks up front with
    gaps of 90+ blocks, the interleaved layout has gaps of 1 (up to a
    few blocks when straddling root/bitmap holes). also the header must
    be adjacent to the first data block.
    """
    data = node.data_blk_nums
    ext = node.ext_blk_nums
    assert len(data) == node.num_data_blks
    assert len(ext) == node.num_ext_blks
    if not data:
        return
    hdr = node.block.blk_num
    assert abs(data[0] - hdr) <= max_gap
    for i, ex in enumerate(ext):
        idx = ppb + i * ppb
        assert idx < len(data)
        assert abs(data[idx] - ex) <= max_gap


def _write_sized_file(xdftool, img_file, tmpdir, name, num_blocks):
    """write a file occupying num_blocks data blocks; return its bytes."""
    factory = BlkDevFactory()
    blkdev = factory.open(img_file, read_only=True)
    vol = ADFSVolume(blkdev)
    vol.open()
    if vol.is_ffs:
        payload = blkdev.block_bytes
    else:
        payload = blkdev.block_bytes - 24
    blkdev.close()
    size = num_blocks * payload
    data = bytes([x % 256 for x in range(size)])
    src = os.path.join(str(tmpdir), name)
    with open(src, "wb") as fh:
        fh.write(data)
    xdftool(img_file, ("write", src, name))
    return data


def xdftool_file_ext_interleave_test(xdftool, xdf_img, tmpdir):
    """FLBs of a multi-ext file must be interleaved with data (DOS0-7)."""
    img = xdf_img.file_name
    # determine ppb/payload of this image so the file needs 2 ext blocks
    # on any block size (512..4096) and any fs (OFS payload is bs-24)
    factory = BlkDevFactory()
    blkdev = factory.open(img, read_only=True)
    ppb = blkdev.block_longs - 56
    blkdev.close()
    data = _write_sized_file(xdftool, img, tmpdir, "big", 2 * ppb + 10)
    # data must round-trip
    out = xdftool(img, ("type", "big"), raw_output=True)
    assert out == data
    # layout must be interleaved
    blkdev, vol, node, ppb = _open_file_node(img, "big")
    try:
        assert node.num_ext_blks == 2
        _assert_interleaved(node, ppb)
    finally:
        blkdev.close()


def xdftool_file_ext_interleave_boundary_test(xdftool, xdf_img, tmpdir):
    """exact header-capacity boundaries: ppb blocks need no FLB."""
    img = xdf_img.file_name
    factory = BlkDevFactory()
    blkdev = factory.open(img, read_only=True)
    ppb = blkdev.block_longs - 56
    blkdev.close()
    # exactly fits the header: no ext block
    data0 = _write_sized_file(xdftool, img, tmpdir, "edge0", ppb)
    blkdev, vol, node0, ppb = _open_file_node(img, "edge0")
    try:
        assert node0.num_ext_blks == 0
        _assert_interleaved(node0, ppb)
    finally:
        blkdev.close()
    out0 = xdftool(img, ("type", "edge0"), raw_output=True)
    assert out0 == data0
    # one block more: exactly one ext block, adjacent to its chunk
    data1 = _write_sized_file(xdftool, img, tmpdir, "edge1", ppb + 1)
    blkdev, vol, node1, ppb = _open_file_node(img, "edge1")
    try:
        assert node1.num_ext_blks == 1
        _assert_interleaved(node1, ppb)
    finally:
        blkdev.close()
    out1 = xdftool(img, ("type", "edge1"), raw_output=True)
    assert out1 == data1


# ----- defrag tests -----


def _data_gaps(data):
    """forward data jumps > 4 (ext interruptions are 2, holes are 3)."""
    return sum(1 for i in range(len(data) - 1) if data[i + 1] - data[i] > 4)


def xdftool_defrag_test(xdftool, xdf_img, tmpdir):
    """defrag keeps all data and leaves FLBs interleaved with a summary."""
    img = xdf_img.file_name
    factory = BlkDevFactory()
    blkdev = factory.open(img, read_only=True)
    ppb = blkdev.block_longs - 56
    vol = ADFSVolume(blkdev)
    vol.open()
    dos_before = vol.get_dos_type()
    name_before = vol.get_volume_name().get_unicode()
    blkdev.close()
    data_a = _write_sized_file(xdftool, img, tmpdir, "a", ppb + 10)
    data_b = _write_sized_file(xdftool, img, tmpdir, "b", 10)
    blkdev = factory.open(img, read_only=True)
    vol = ADFSVolume(blkdev)
    vol.open()
    used_before = vol.get_used_blocks()
    blkdev.close()
    # defrag prints a summary with volume name, fs type and stats
    # (volume name itself is not matched: non-ascii names are decoded
    # as latin-1 by the test runner)
    out = xdftool(img, "defrag")
    assert any(line.startswith("defrag '") for line in out)
    assert any(DosType.get_dos_type_str(dos_before) in line for line in out)
    assert any("2 nodes defragmented (2 files, 0 dirs)" in line for line in out)
    # data must round-trip
    assert xdftool(img, ("type", "a"), raw_output=True) == data_a
    assert xdftool(img, ("type", "b"), raw_output=True) == data_b
    # layout must be interleaved and block usage unchanged
    blkdev, vol, node, ppb = _open_file_node(img, "a")
    try:
        _assert_interleaved(node, ppb)
        assert vol.get_used_blocks() == used_before
        assert vol.get_dos_type() == dos_before
        assert vol.get_volume_name().get_unicode() == name_before
    finally:
        blkdev.close()


def xdftool_defrag_fragmented_test(xdftool, xdf_img, tmpdir):
    """defrag removes fragmentation from delete/write cycles."""
    img = xdf_img.file_name
    factory = BlkDevFactory()
    blkdev = factory.open(img, read_only=True)
    ppb = blkdev.block_longs - 56
    blkdev.close()
    d1 = _write_sized_file(xdftool, img, tmpdir, "f1", ppb + 10)
    _write_sized_file(xdftool, img, tmpdir, "f2", ppb + 10)
    d3 = _write_sized_file(xdftool, img, tmpdir, "f3", 10)
    xdftool(img, ("delete", "f2"))
    d_big = _write_sized_file(xdftool, img, tmpdir, "big", 2 * ppb + 10)
    # big file must be split across the freed hole + elsewhere
    blkdev, vol, node, ppb = _open_file_node(img, "big")
    try:
        assert _data_gaps(node.data_blk_nums) >= 1
    finally:
        blkdev.close()
    out = xdftool(img, "defrag")
    assert any("3 nodes defragmented (3 files, 0 dirs)" in line for line in out)
    # all data intact, no big gaps left, FLBs interleaved
    assert xdftool(img, ("type", "f1"), raw_output=True) == d1
    assert xdftool(img, ("type", "f3"), raw_output=True) == d3
    assert xdftool(img, ("type", "big"), raw_output=True) == d_big
    for name in ("f1", "f3", "big"):
        blkdev, vol, node, ppb = _open_file_node(img, name)
        try:
            assert _data_gaps(node.data_blk_nums) == 0
            _assert_interleaved(node, ppb)
        finally:
            blkdev.close()


def xdftool_defrag_invalid_test(toolrun, tmpdir):
    """defrag refuses an image with an invalid filesystem."""
    img = str(tmpdir / "corrupt.adf")
    toolrun.run_checked("xdftool", img, "format", "x", "DOS0")
    ret, _, _ = toolrun.run("xdftool", img, "defrag", "extra")
    assert ret == 1
    with open(img, "r+b") as fh:
        fh.write(b"\x00\x00\x00\x00")
    ret, _, _ = toolrun.run("xdftool", img, "defrag")
    assert ret != 0


def xdftool_defrag_rollback_test(xdftool, toolrun, xdf_img, tmpdir):
    """a failed defrag restore must leave the original image intact."""
    if toolrun.run_subproc:
        pytest.skip("needs in-process tool run")
    from unittest import mock
    from amitools.fs.ADFSDir import ADFSDir
    from amitools.fs.FSError import FSError, NO_FREE_BLOCKS

    img = xdf_img.file_name
    data = _write_sized_file(xdftool, img, tmpdir, "f", 10)
    with open(img, "rb") as fh:
        before = fh.read()

    def boom(self, *a, **k):
        raise FSError(NO_FREE_BLOCKS, node=self)

    with mock.patch.object(ADFSDir, "create_file", boom):
        ret, _, _ = toolrun.run("xdftool", img, "defrag")
        assert ret == 3
    with open(img, "rb") as fh:
        assert fh.read() == before
    assert xdftool(img, ("type", "f"), raw_output=True) == data
