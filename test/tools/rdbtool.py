import pytest
import collections


DISK_SIZES = (
    "1M",
    "10M",
    "50M"
)

IMGSpec = collections.namedtuple('IMGSpec', ['file_name', 'size', 'part_list'])

PARTITION_LIST = (
    [("DH0", "size=100%")],
    [("DH0", None)],
    [("DH0", "size=50%"), ("DH1", None)],
    [("DH0", "size=10%"), ("DH1", "size=20%"), ("DH2", None)]
)


@pytest.fixture(params=DISK_SIZES)
def img_file(request, tmpdir):
    """return IMGSpec for various disks"""
    size = request.param
    file_name = tmpdir / "disk-" + size + ".hdf"
    size = "size=" + size
    return IMGSpec(str(file_name), size, None)


@pytest.fixture
def rdbtool(toolrun):
    def run(img_file, *cmds, raw_output=False, return_code=0, opts=[]):
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
        return toolrun.run_checked("rdbtool", *opts, img_file, *args[:-1],
                                   raw_output=raw_output,
                                   return_code=return_code)
    return run


@pytest.fixture(params=PARTITION_LIST)
def partitions(rdbtool, img_file, request):
    rdbtool(img_file.file_name, ("create", img_file.size), ("init",))
    part_list = request.param
    for part in part_list:
        name, size = part
        if size:
            rdbtool(img_file.file_name, ("add", size))
        else:
            rdbtool(img_file.file_name, ("fill"))
    return IMGSpec(img_file.file_name, img_file.size, part_list)


def rdbtool_create_test(rdbtool, img_file):
    rdbtool(img_file.file_name, ("create", img_file.size))


def rdbtool_create_force_test(rdbtool, img_file):
    with open(img_file.file_name, "wb") as fh:
        fh.write(b"a" * 100)
    # image file already exists
    rdbtool(img_file.file_name, ("create", img_file.size), return_code=4)
    # force write
    rdbtool(img_file.file_name, ("create", img_file.size), opts=("-f",))


def rdbtool_init_test(rdbtool, img_file):
    rdbtool(img_file.file_name, ("create", img_file.size), ("init",))


def rdbtool_info_test(rdbtool, partitions):
    rdbtool(partitions.file_name, ("info"))
