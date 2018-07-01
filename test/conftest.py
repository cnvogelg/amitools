# pytest fixture for vamos tests

from __future__ import print_function
import pytest
import subprocess
import os
import hashlib

VAMOS_BIN = "../bin/vamos"
VAMOS_ARGS = ['-c', 'test.vamosrc']
PROG_BIN_DIR = "bin"
PROG_SRC_DIR = "src"
LIB_BIN_DIR = "bin/libs"
LIB_SRC_DIR = "src/libs"


class BinBuilder:
  def __init__(self, flavor, debug=False):
    if flavor == 'none':
      flavor = None
    self.flavor = flavor
    self.debug = debug

  def make_prog(self, prog_name):
    return self.make_progs([prog_name])[0]

  def make_progs(self, prog_names):
    bins = {}
    for p in prog_names:
      bin_path = os.path.join(PROG_BIN_DIR, p + '_' + self.flavor)
      if self.debug:
        bin_path = bin_path + "_dbg"
      src_path = os.path.join(PROG_SRC_DIR, p + '.c')
      bins[bin_path] = src_path
    return self._build_bins(bins)

  def make_lib(self, lib_name):
    return self.make_libs([lib_name])[0]

  def make_libs(self, lib_names):
    bins = {}
    for name in lib_names:
      lib_name = name
      lib_bin_dir = LIB_BIN_DIR
      if self.flavor is not None:
        lib_bin_dir += "-" + self.flavor
      lib_name += ".library"
      bin_path = os.path.join(lib_bin_dir, lib_name)
      src_path = os.path.join(LIB_SRC_DIR, name + '.c')
      bins[bin_path] = src_path
    return self._build_bins(bins)

  def _build_bins(self, bin_paths):
    # check sources
    all_bins = []
    rebuild_bins = []
    for binp in bin_paths:
      all_bins.append(binp)
      srcp = bin_paths[binp]
      if not os.path.exists(srcp):
        raise ValueError("source does not exist: '%s'" % srcp)
      # if bin already exits check if its never
      if os.path.exists(binp):
        srct = os.path.getmtime(srcp)
        bint = os.path.getmtime(binp)
        if bint <= srct:
          rebuild_bins.append(binp)
      else:
        rebuild_bins.append(binp)
    # call make to rebuild bins
    if len(rebuild_bins) > 0:
      print("BinBuilder: making", " ".join(rebuild_bins))
      args = ['make']
      args += rebuild_bins
      subprocess.check_call(args, stdout=subprocess.PIPE)
    return all_bins


class VamosTestRunner:
  def __init__(self, flavor, vamos_bin,
               vopts=None,
               use_debug_bins=False,
               dump_output=False,
               generate_data=False):
    self.flavor = flavor
    self.vamos_bin = vamos_bin
    self.vopts = vopts
    self.use_debug_bins = use_debug_bins
    self.dump_output = dump_output
    self.generate_data = generate_data
    self.bin_builder = BinBuilder(flavor, use_debug_bins)

  def _get_data_path(self, prog_name, kw_args):
    dat_path = ["data/" + prog_name]
    if 'variant' in kw_args:
      dat_path.append("_")
      dat_path.append(kw_args['variant'])
    dat_path.append(".txt")
    return "".join(dat_path)

  def make_prog(self, prog_name):
    self.bin_builder.make_prog(prog_name)

  def get_prog_bin_name(self, prog_name):
    bin_name = "curdir:bin/" + prog_name + '_' + self.flavor
    if self.use_debug_bins:
      bin_name += "_dbg"
    return bin_name

  def run_prog(self, *prog_args, **kw_args):
    """run an AmigaOS binary with vamos

       kw_args:
       - stdin = string for stdin
       - no_ts = no timestamps
       - variant = a postfix string to append to data file

       returns:
       - returncode of process
       - stdout as line array
       - stderr as line array
    """

    # ensure that prog exists
    self.make_prog(prog_args[0])

    # stdin given?
    if 'stdin' in kw_args:
      stdin = kw_args['stdin']
    else:
      stdin = None

    # timestamps?
    if 'no_ts' in kw_args:
      no_ts = kw_args['no_ts']
    else:
      no_ts = True

    # run vamos with prog
    args = [self.vamos_bin] + VAMOS_ARGS
    if no_ts:
      args.append('--no-ts')
    if self.vopts is not None:
      args = args + self.vopts
    if 'vargs' in kw_args:
      args = args + kw_args['vargs']

    # built binaries have special prog names
    prog_name = self.get_prog_bin_name(prog_args[0])
    args.append(prog_name)
    if len(prog_args) > 1:
      args = args + list(prog_args[1:])

    # run and get stdout/stderr
    print("running:", " ".join(args))
    if stdin:
      stdin_flag = subprocess.PIPE
    else:
      stdin_flag = None
    p = subprocess.Popen(args, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=stdin_flag)
    (stdout, stderr) = p.communicate(stdin)

    # process stdout
    stdout = stdout.splitlines()
    stderr = stderr.splitlines()

    # show?
    if self.dump_output:
      fh = open("vamos.log", "w+")
      fh.write(" ".join(args)+"\n")
      for line in stdout:
        fh.write(line)
        fh.write("\n")
      fh.close()

    # generate data?
    if self.generate_data:
      dat_path = self._get_data_path(prog_args[0], kw_args)
      print("wrote output to '%s'" % dat_path)
      f = open(dat_path, "w")
      for line in stdout:
        f.write(line + "\n")
      f.close()

    return (p.returncode, stdout, stderr)

  def run_prog_checked(self, *prog_args, **kw_args):
    """like run_prog() but check return value and assume its 0"""
    retcode, stdout, stderr = self.run_prog(*prog_args, **kw_args)
    if retcode != 0:
      cmd = " ".join(prog_args)
      raise subprocess.CalledProcessError(retcode, cmd)
    return stdout, stderr

  def _compare(self, got, ok):
    for i in xrange(len(ok)):
      assert (got[i] == ok[i])
    assert (len(got) == len(ok)), "stdout line count differs"

  def run_prog_check_data(self, *prog_args, **kw_args):
    """like run_prog_checked() but also verify the stdout
       and compare with the corresponding data file of the suite"""
    stdout, stderr = self.run_prog_checked(*prog_args, **kw_args)
    # compare stdout with data
    dat_path = self._get_data_path(prog_args[0], kw_args)
    f = open(dat_path, "r")
    ok_stdout = []
    for l in f:
      ok_stdout.append(l.strip())
    f.close()
    self._compare(stdout, ok_stdout)
    # asser stderr to be empty
    if self.vopts is None:
      assert stderr == []


class VamosRunner:

  def __init__(self, vamos_bin, vopts):
    self.vamos_bin = vamos_bin
    self.vopts = vopts

  def run_prog(self, *prog_args, **kw_args):
    # stdin given?
    if 'stdin' in kw_args:
      stdin = kw_args['stdin']
    else:
      stdin = None

    # timestamps?
    if 'no_ts' in kw_args:
      no_ts = kw_args['no_ts']
    else:
      no_ts = True

    # run vamos with prog
    args = [self.vamos_bin] + VAMOS_ARGS
    if no_ts:
      args.append('--no-ts')
    if 'vargs' in kw_args:
      args = args + kw_args['vargs']

    args = args + list(prog_args)

    # run and get stdout/stderr
    print("running:", " ".join(args))
    print("stdin:", stdin)
    if stdin:
      stdin_flag = subprocess.PIPE
    else:
      stdin_flag = None
    p = subprocess.Popen(args, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=stdin_flag)
    (stdout, stderr) = p.communicate(stdin)

    # process stdout
    stdout = stdout.splitlines()
    stderr = stderr.splitlines()
    return (p.returncode, stdout, stderr)

  def _get_sha1(self, file_name):
    h = hashlib.sha1()
    with open(file_name, "rb") as fh:
      data = fh.read()
      h.update(data)
      return h.hexdigest()

  def skip_if_prog_not_available(self, file_name, sha1_sum=None):
    if not os.path.exists(file_name):
      pytest.skip("prog not found: " + file_name)
    if sha1_sum:
      file_sum = self._get_sha1(file_name)
      print(file_sum, file_name)
      if file_sum != sha1_sum:
        raise RuntimeError("prog wrong hash: got=%s want=%s" %
                           (file_sum, sha1_sum))


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
  parser.addoption("--vamos-executable", "-E", default=VAMOS_BIN,
                   help="replace the vamos executable (default: ../bin/vamos)")


def pytest_runtest_setup(item):
  flv = item.config.getoption("--flavor")
  if flv is not None:
    kw = item.keywords
    if flv not in kw:
      pytest.skip("disabled flavor")


@pytest.fixture(scope="module",
                params=['gcc', 'gcc-res', 'gcc-dbg', 'gcc-res-dbg'])
def buildlibnix(request):
  return BinBuilder(request.param)


@pytest.fixture(scope="module",
                params=['sc', 'sc-res', 'sc-dbg', 'sc-res-dbg'])
def buildlibsc(request):
  return BinBuilder(request.param)


@pytest.fixture(scope="module",
                params=['vc', 'gcc', 'agcc', 'sc'])
def vamos(request):
  """Run vamos with test programs"""
  dbg = request.config.getoption("--use-debug-bins")
  dump = request.config.getoption("--dump-output")
  gen = request.config.getoption("--gen-data")
  vopts = request.config.getoption("--vamos-options")
  vamos_bin = request.config.getoption("--vamos-executable")
  if vopts is not None:
    vopts = vopts.split('+')
  return VamosTestRunner(request.param,
                         use_debug_bins=dbg,
                         dump_output=dump,
                         generate_data=gen,
                         vopts=vopts,
                         vamos_bin=vamos_bin)


@pytest.fixture(scope="module")
def vrun(request):
  vopts = request.config.getoption("--vamos-options")
  vamos_bin = request.config.getoption("--vamos-executable")
  if vopts is not None:
    vopts = vopts.split('+')
  return VamosRunner(vopts=vopts, vamos_bin=vamos_bin)


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
