import pytest
import collections


DISK_SIZES = ("1M", "10M", "50M")

IMGSpec = collections.namedtuple(
    "IMGSpec", ["file_name", "size", "fs_block_size", "part_list"]
)

PARTITION_LIST = (
    [("DH0", "size=100%")],
    [("DH0", None)],
    [("DH0", "size=50%"), ("DH1", None)],
    [("DH0", "size=10%"), ("DH1", "size=20%"), ("DH2", None)],
)

FS_BLOCK_SIZES = (512, 4096)


@pytest.fixture(params=FS_BLOCK_SIZES)
def fs_block_size(request):
    """return fs block size"""
    return request.param


@pytest.fixture(params=DISK_SIZES)
def img_file(request, fs_block_size, tmpdir):
    """return IMGSpec for various disks"""
    size = request.param
    file_name = tmpdir / "disk-" + size + "-" + str(fs_block_size) + ".hdf"
    size = "size=" + size
    return IMGSpec(str(file_name), size, fs_block_size, None)


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
            args.append("+")
        cmd = ["rdbtool"] + list(opts) + [img_file] + args[:-1]
        return toolrun.run_checked(*cmd, raw_output=raw_output, return_code=return_code)

    return run


@pytest.fixture(params=PARTITION_LIST)
def partitions(rdbtool, img_file, request):
    rdbtool(img_file.file_name, ("create", img_file.size), ("init",))
    part_list = request.param
    fs_bs = "bs=" + str(img_file.fs_block_size)
    for part in part_list:
        name, size = part
        if size:
            rdbtool(img_file.file_name, ("add", size, fs_bs))
        else:
            rdbtool(img_file.file_name, ("fill", fs_bs))
    return IMGSpec(img_file.file_name, img_file.size, img_file.fs_block_size, part_list)


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


# test file systems


def rdbtool_fsadd_test(rdbtool, img_file):
    rdbtool(img_file.file_name, ("create", img_file.size), ("init", "rdb_cyls=4"))
    rdbtool(img_file.file_name, ("fsadd", "progs/pfs3aio", "dostype=PFS3"))
    rdbtool(img_file.file_name, ("info"))


def rdbtool_fsget_test(rdbtool, img_file, tmpdir):
    rdbtool(img_file.file_name, ("create", img_file.size), ("init", "rdb_cyls=4"))
    rdbtool(img_file.file_name, ("fsadd", "progs/pfs3aio", "dostype=PFS3"))
    # fsget
    tmp_file = str(tmpdir / "filesys")
    rdbtool(img_file.file_name, ("fsget", "0", tmp_file))
    with open("progs/pfs3aio", "rb") as fh:
        src_data = fh.read()
    with open(tmp_file, "rb") as fh:
        tgt_data = fh.read()
    assert src_data == tgt_data


def rdbtool_fsdelete_test(rdbtool, img_file):
    rdbtool(img_file.file_name, ("create", img_file.size), ("init", "rdb_cyls=4"))
    rdbtool(img_file.file_name, ("fsadd", "progs/pfs3aio", "dostype=PFS3"))
    # fsdelete
    rdbtool(img_file.file_name, ("fsdelete", "0"))
    rdbtool(img_file.file_name, ("info"))


def rdbtool_fsflags_test(rdbtool, img_file):
    rdbtool(img_file.file_name, ("create", img_file.size), ("init", "rdb_cyls=4"))
    rdbtool(img_file.file_name, ("fsadd", "progs/pfs3aio", "dostype=PFS3"))
    # fsflags
    rdbtool(img_file.file_name, ("fsflags", "0", "clear"))
    rdbtool(img_file.file_name, ("info"))
    rdbtool(img_file.file_name, ("fsflags", "0", "stack_size=8192"))
    rdbtool(img_file.file_name, ("info"))


# test with partitions


def rdbtool_info_all_test(rdbtool, partitions):
    rdbtool(partitions.file_name, "info")
    rdbtool(partitions.file_name, "open", "info")


def rdbtool_info_part_test(rdbtool, partitions):
    for part in partitions.part_list:
        rdbtool(partitions.file_name, ("info", part[0]))
    for part_no in range(len(partitions.part_list)):
        rdbtool(partitions.file_name, ("info", str(part_no)))


def rdbtool_show_test(rdbtool, partitions):
    rdbtool(partitions.file_name, "show")
    rdbtool(partitions.file_name, "open", "show")


def rdbtool_delete_by_name_test(rdbtool, partitions):
    for part in partitions.part_list:
        rdbtool(partitions.file_name, ("delete", part[0]), "show", "info")


def rdbtool_delete_by_id_test(rdbtool, partitions):
    for part in range(len(partitions.part_list)):
        rdbtool(partitions.file_name, ("delete", "0"), "show", "info")


CHANGE_OPTS = [
    ("max_transfer", "0xdeadbeef"),
    ("mask", "0xcafebabe"),
    ("bootable", "1"),
    ("automount", "0"),
    ("pri", "5"),
    ("num_buffer", "10"),
]


def rdbtool_change_test(rdbtool, partitions):
    for opt, val in CHANGE_OPTS:
        arg = opt + "=" + val
        out = rdbtool(partitions.file_name, ("change", "0", arg), ("info", "0"))
        res = "\n".join(out)
        assert res.find(arg) > 0


def rdbtool_export_import_test(rdbtool, partitions, tmpdir):
    part_file = str(tmpdir / "part.img")
    print(part_file)
    for part in partitions.part_list:
        rdbtool(partitions.file_name, ("export", part[0], part_file))
        rdbtool(partitions.file_name, ("import", part[0], part_file))
