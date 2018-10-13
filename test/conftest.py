# pytest fixture for vamos tests

import pytest
import os
from helper import *


my_dir = os.path.dirname(__file__)
os.chdir(my_dir)

# ----- pytest integration -----

def pytest_addoption(parser):
  parser.addoption("--flavor", "-F", action="store", default=None,
                   help="select an Amiga compiler flavor to test")
  parser.addoption("--use-debug-bins", "-D", action="store_true",
                   default=False,
                   help="run the debug versions of the Amiga binaries")
  parser.addoption("--dump-output", "-O", action="store_true", default=False,
                   help="write all vamos output to 'vamos.log'")
  parser.addoption("--gen-data", "-G", action="store_true", default=False,
                   help="generate data files by using the output of "
                   "the test program")
  parser.addoption("--vamos-options", "-V", action="store", default=None,
                   help="add options to vamos run. separate options by plus:"
                   " e.g. -V-t+-T")
  parser.addoption("--vamos-executable", "-E", default=None,
                   help="replace the vamos executable (default: ../bin/vamos)")
  parser.addoption("--auto-build", default=False, action="store_true",
                   help="automatically rebuild binaries if source is newer")


def pytest_runtest_setup(item):
  flv = item.config.getoption("--flavor")
  if flv is not None:
    kw = item.keywords
    if flv not in kw:
      pytest.skip("disabled flavor")


@pytest.fixture(scope="module",
                params=['gcc', 'gcc-res', 'gcc-dbg', 'gcc-res-dbg'])
def buildlibnix(request):
  auto_build = request.config.getoption("--auto-build")
  return BinBuilder(request.param, auto_build=auto_build)


@pytest.fixture(scope="module",
                params=['sc', 'sc-res', 'sc-dbg', 'sc-res-dbg'])
def buildlibsc(request):
  auto_build = request.config.getoption("--auto-build")
  return BinBuilder(request.param, auto_build=auto_build)


@pytest.fixture(scope="module",
                params=['vc', 'gcc', 'agcc', 'sc'])
def vamos(request):
  """Run vamos with test programs"""
  dbg = request.config.getoption("--use-debug-bins")
  dump = request.config.getoption("--dump-output")
  gen = request.config.getoption("--gen-data")
  vopts = request.config.getoption("--vamos-options")
  vamos_bin = request.config.getoption("--vamos-executable")
  auto_build = request.config.getoption("--auto-build")
  if vopts is not None:
    vopts = vopts.split('+')
  return VamosTestRunner(request.param,
                         use_debug_bins=dbg,
                         dump_output=dump,
                         generate_data=gen,
                         vopts=vopts,
                         vamos_bin=vamos_bin,
                         auto_build=auto_build)


@pytest.fixture(scope="module")
def vrun(request):
  vopts = request.config.getoption("--vamos-options")
  vamos_bin = request.config.getoption("--vamos-executable")
  if vopts is not None:
    vopts = vopts.split('+')
  return VamosRunner(vopts=vopts, vamos_bin=vamos_bin)


@pytest.fixture(scope="module")
def toolrun():
  return ToolRunner()


@pytest.fixture(scope="module",
                params=['mach', 'mach-label', 'mock', 'mock-label'])
def mem_alloc(request):
  from amitools.vamos.machine import Machine, MockMemory
  from amitools.vamos.mem import MemoryAlloc
  from amitools.vamos.label import LabelManager
  n = request.param
  if n == 'mach':
    m = Machine(use_labels=False)
    mem = m.get_mem()
    return mem, MemoryAlloc(mem)
  elif n == 'mach-label':
    m = Machine()
    mem = m.get_mem()
    return mem, MemoryAlloc(mem, label_mgr=m.get_label_mgr())
  elif n == 'mock':
    mem = MockMemory(fill=23)
    return mem, MemoryAlloc(mem)
  else:
    mem = MockMemory(fill=23)
    lm = LabelManager()
    return mem, MemoryAlloc(mem, label_mgr=lm)
