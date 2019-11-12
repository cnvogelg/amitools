import pytest
import collections
import os

ADF_LIST = (
    "amiga-os-100-workbench.adf",
    "amiga-os-110-workbench.adf",
    "amiga-os-120-workbench.adf",
    "amiga-os-134-extras.adf",
    "amiga-os-134-workbench.adf",
    "amiga-os-200-workbench.adf",
    "amiga-os-204-workbench.adf",
    "amiga-os-210-workbench.adf",
    "amiga-os-300-workbench.adf",
    "amiga-os-310-extras.adf",
    "amiga-os-310-fonts.adf",
    "amiga-os-310-install.adf",
    "amiga-os-310-locale.adf",
    "amiga-os-310-storage.adf",
    "amiga-os-310-workbench.adf",
    "aros-20130502-boot.adf"
)

DOS_FORMATS = (
    "DOS0",
    "DOS1",
    "DOS2",
    "DOS3",
    "DOS4",
    "DOS5",
    "DOS6",
    "DOS7"
)

DISK_SIZES = (
    "880K",
    "1M",
    "10M"
)

XDFSpec = collections.namedtuple('XDFSpec', ['file_name', 'size'])

DATA_bytes = bytes([x for x in range(256)])
DATA_10k = bytes([x % 256 for x in range(10 * 1024)])
DATA_100k = bytes([x % 256 for x in range(100 * 1024)])

TEST_DATA = {
    "empty": b"",
    "hello": b"hello, world!",
    "byterange": DATA_bytes,
    "10k": DATA_10k,
    "100k": DATA_100k
}

DataFile = collections.namedtuple('DataFile', 
                                  ['file_path', 'file_name', 'data'])

TEST_TREES = {
    "simple": {
        "foo": {},
        "bar": b"Hello, world!"
    },
    "deep": {
        "foo": {
            "bar": {
                "baz": {
                    "hello": b"Hello, world!"
                }
            }
        },
    },
    "data": {
        "bytes": DATA_bytes,
        "10k": DATA_10k,
        "100k": DATA_100k
    }
}

XDFData = collections.namedtuple('XDFData',
                                 ['spec', 'build', 'check', 'delete'])


@pytest.fixture(params=ADF_LIST)
def adf_file(request, toolrun):
    rom = "disks/" + request.param
    toolrun.skip_if_data_file_not_available(rom)
    return rom


@pytest.fixture(params=DOS_FORMATS)
def dos_format(request):
    return request.param


@pytest.fixture(params=DISK_SIZES)
def xdfs(request, tmpdir):
    """return (xdf_file, xdf_size_spec) for various disks"""
    size = request.param
    if size == "880K":
        file_name = tmpdir / "disk.adf"
        size = ""
    else:
        file_name = tmpdir / "disk-" + size + ".hdf"
        size = "size=" + size
    return XDFSpec(str(file_name), size)


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
            args.append('+')
        return toolrun.run_checked("xdftool", xdf_file, *args[:-1],
                                   raw_output=raw_output)
    return run


@pytest.fixture
def xdf_img(xdftool, xdfs, dos_format):
    """create formatted image"""
    xdftool(xdfs.file_name,
            ("create", xdfs.size),
            ("format", "Foo", dos_format))
    return xdfs


@pytest.fixture(params=TEST_TREES.keys())
def xdf_img_data(request, xdf_img, xdftool, tmpdir):
    test_tree = request.param
    tree = TEST_TREES[test_tree]

    def build_node(node, path, cmds):
        path_name = "/".join(path)
        if isinstance(node, dict):
            cmds.append(("makedir", path_name))
            for name in node:
                build_node(node[name], path + [name], cmds)
        else:
            tmp_file = os.path.join(str(tmpdir), "_".join(path))
            with open(tmp_file, "wb") as fh:
                fh.write(node)
            cmds.append(("write", tmp_file, path_name))

    def build_func():
        cmds = []
        for node in tree:
            build_node(tree[node], [node], cmds)
        xdftool(xdf_img.file_name, *cmds)

    def check_node(node, path):
        path_name = "/".join(path)
        # list entry
        output = xdftool(xdf_img.file_name,
                         ("list", path_name))
        # split
        file_name, size, *_ = output[0].split()
        if isinstance(node, dict):
            assert size == "DIR"
            for name in node:
                check_node(node[name], path + [name])
        else:
            data = xdftool(xdf_img.file_name,
                           ("type", path_name),
                           raw_output=True)
            assert data == node

    def check_func():
        for node in tree:
            check_node(tree[node], [node])

    def delete_node(node, path, cmds):
        path_name = "/".join(path)
        if isinstance(node, dict):
            for name in node:
                delete_node(node[name], path + [name], cmds)
        cmds.append(("delete", path_name))

    def delete_func():
        cmds = []
        for node in tree:
            delete_node(tree[node], [node], cmds)
        xdftool(xdf_img.file_name, *cmds)

    return XDFData(xdf_img, build_func, check_func, delete_func)


@pytest.fixture(params=TEST_DATA.keys())
def test_files(request, tmpdir):
    test_file = request.param
    data = TEST_DATA[test_file]
    test_path = tmpdir / test_file
    with open(str(test_path), "wb") as fh:
        fh.write(data)
    return DataFile(str(test_path), test_file, data)


def xdftool_list_test(xdftool, adf_file):
    """list contents of various disks"""
    xdftool(adf_file, "list")


def xdftool_create_test(xdftool, xdfs):
    """create an empty disk image"""
    xdftool(xdfs.file_name, ("create", xdfs.size))


def xdftool_format_test(xdftool, dos_format, xdfs):
    """format disk image"""
    xdftool(xdfs.file_name,
            ("create", xdfs.size),
            ("format", "Foo", dos_format))
    xdftool(xdfs.file_name, "list")


def xdftool_write_read_test(xdftool, xdf_img, test_files):
    """write a file and read it back"""
    # write file
    xdftool(xdf_img.file_name,
            ("write", test_files.file_path))
    # read file back
    read_file = test_files.file_path + "-read"
    xdftool(xdf_img.file_name,
            ("read", test_files.file_name, read_file))
    # compare
    with open(read_file, "rb") as fh:
        read_data = fh.read()
        assert read_data == test_files.data
    # type file
    output = xdftool(xdf_img.file_name,
                     ("type", test_files.file_name),
                     raw_output=True)
    assert output == test_files.data


def xdftool_write_delete_test(xdftool, xdf_img, test_files):
    """write a file and delete it"""
    # write file
    xdftool(xdf_img.file_name,
            ("write", test_files.file_path))
    # delete it
    xdftool(xdf_img.file_name,
            ("delete", test_files.file_name))


def xdftool_makedir_test(xdftool, xdf_img):
    # create dir
    xdftool(xdf_img.file_name,
            ("makedir", "bla"))
    # delete it
    xdftool(xdf_img.file_name,
            ("delete", "bla"))


def xdftool_create_tree_test(xdftool, xdf_img_data):
    """create various file/dir trees"""
    # build tree
    xdf_img_data.build()
    # check created tree
    xdf_img_data.check()
    # delete tree
    xdf_img_data.delete()
