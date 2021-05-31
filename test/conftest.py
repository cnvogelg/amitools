# pytest fixture for vamos tests


import pytest
import os
from helper import *


VAMOS_BIN = "../bin/vamos"
VAMOS_ARGS = ["-c", "test.vamosrc"]

my_dir = os.path.dirname(__file__)
os.chdir(my_dir)

# ----- pytest integration -----


def pytest_addoption(parser):
    parser.addoption(
        "--flavor",
        "-F",
        action="store",
        default=None,
        help="select an Amiga compiler flavor to test",
    )
    parser.addoption(
        "--use-debug-bins",
        "-D",
        action="store_true",
        default=False,
        help="run the debug versions of the Amiga binaries",
    )
    parser.addoption(
        "--dump-file",
        "-O",
        action="store_true",
        default=False,
        help="write all vamos output to 'vamos.log'",
    )
    parser.addoption(
        "--dump-console",
        "-C",
        action="store_true",
        default=False,
        help="write all vamos output to stdout",
    )
    parser.addoption(
        "--gen-data",
        "-G",
        action="store_true",
        default=False,
        help="generate data files by using the output of " "the test program",
    )
    parser.addoption(
        "--vamos-args",
        "-A",
        action="append",
        default=None,
        help="add options to vamos run, e.g. -A-t",
    )
    parser.addoption(
        "--vamos-bin",
        "-E",
        default=None,
        help="replace the vamos executable (default: ../bin/vamos)",
    )
    parser.addoption(
        "--auto-build",
        default=False,
        action="store_true",
        help="automatically rebuild binaries if source is newer",
    )
    parser.addoption(
        "--profile",
        "-P",
        action="store_true",
        default=False,
        help="create a profile file",
    )
    parser.addoption(
        "--profile-file",
        action="store",
        default="vamos-prof.json",
        help="set the profile file name",
    )
    parser.addoption(
        "--full-suite",
        action="store_true",
        default=False,
        help="run full test suite and include all tests",
    )
    parser.addoption(
        "--run-subproc",
        action="store_true",
        default=False,
        help="run vamos binaries via subprocess and not directly inside pytest",
    )


def pytest_configure(config):
    # change vamos binary
    global VAMOS_BIN
    vamos_bin = config.getoption("vamos_bin")
    if vamos_bin:
        VAMOS_BIN = vamos_bin
    # change vamos options
    global VAMOS_ARGS
    vamos_args = config.getoption("vamos_args")
    if vamos_args:
        VAMOS_ARGS += vamos_args
    # enable profiling
    if config.getoption("profile"):
        file = config.getoption("profile_file")
        file = os.path.abspath(file)
        print("creating profile: %s" % file)
        # clear profile file if existing
        if os.path.exists(file):
            os.remove(file)
        # add options to vamos
        prof_opts = [
            "--profile-libs",
            "all",
            "--profile-file",
            file,
            "--profile-file-append",
            "--profile",
        ]
        VAMOS_ARGS += prof_opts
    # show settings
    print("vamos:", VAMOS_BIN, " ".join(VAMOS_ARGS))


def pytest_unconfigure(config):
    pass


def pytest_collection_modifyitems(config, items):
    if config.getoption("--full-suite"):
        return
    skip_full = pytest.mark.skip(reason="skip full")
    for item in items:
        if item.get_closest_marker("full"):
            item.add_marker(skip_full)


def pytest_runtest_setup(item):
    flv = item.config.getoption("--flavor")
    if flv is not None:
        kw = item.keywords
        if flv not in kw:
            pytest.skip("disabled flavor")


@pytest.fixture(scope="module", params=["gcc", "gcc-res", "gcc-dbg", "gcc-res-dbg"])
def buildlibnix(request):
    auto_build = request.config.getoption("--auto-build")
    return BinBuilder(request.param, auto_build=auto_build)


@pytest.fixture(scope="module", params=["sc", "sc-res", "sc-dbg", "sc-res-dbg"])
def buildlibsc(request):
    auto_build = request.config.getoption("--auto-build")
    return BinBuilder(request.param, auto_build=auto_build)


@pytest.fixture(scope="module", params=["vc", "gcc", "agcc", "sc"])
def vamos(request):
    """Run vamos with test programs"""
    dbg = request.config.getoption("--use-debug-bins")
    dump_file = request.config.getoption("--dump-file")
    dump_console = request.config.getoption("--dump-console")
    gen = request.config.getoption("--gen-data")
    auto_build = request.config.getoption("--auto-build")
    run_subproc = request.config.getoption("--run-subproc")
    flavor = request.param
    return VamosTestRunner(
        flavor,
        use_debug_bins=dbg,
        dump_file=dump_file,
        dump_console=dump_console,
        generate_data=gen,
        vamos_bin=VAMOS_BIN,
        vamos_args=VAMOS_ARGS,
        auto_build=auto_build,
        run_subproc=run_subproc,
    )


@pytest.fixture(scope="module")
def vrun(request):
    run_subproc = request.config.getoption("--run-subproc")
    return VamosRunner(
        vamos_bin=VAMOS_BIN, vamos_args=VAMOS_ARGS, run_subproc=run_subproc
    )


@pytest.fixture(scope="module")
def toolrun(request):
    run_subproc = request.config.getoption("--run-subproc")
    return ToolRunner(run_subproc=run_subproc)


@pytest.fixture(scope="module", params=["mach", "mach-label", "mock", "mock-label"])
def mem_alloc(request):
    from amitools.vamos.machine import Machine, MockMemory
    from amitools.vamos.mem import MemoryAlloc
    from amitools.vamos.label import LabelManager

    n = request.param
    if n == "mach":
        m = Machine(use_labels=False)
        mem = m.get_mem()
        return mem, MemoryAlloc(mem)
    elif n == "mach-label":
        m = Machine()
        mem = m.get_mem()
        return mem, MemoryAlloc(mem, label_mgr=m.get_label_mgr())
    elif n == "mock":
        mem = MockMemory(fill=23)
        return mem, MemoryAlloc(mem)
    else:
        mem = MockMemory(fill=23)
        lm = LabelManager()
        return mem, MemoryAlloc(mem, label_mgr=lm)
