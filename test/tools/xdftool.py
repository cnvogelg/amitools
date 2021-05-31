import pytest
import collections
import os


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
            # plus seperates commands
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
            # plus seperates commands
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
