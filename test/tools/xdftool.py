import pytest
import collections

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

XDFSpec = collections.namedtuple('xdf_spec', ['file_name', 'size'])


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
    def run(xdf_file, *cmds):
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
        toolrun.run_checked("xdftool", xdf_file, *args[:-1])
    return run


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
