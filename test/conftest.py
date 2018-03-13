# pytest fixture for vamos tests

import pytest
import subprocess
import os

VAMOS_BIN="../bin/vamos"
VAMOS_ARGS=['-c', 'test.vamosrc']
PROG_BIN_DIR="bin"

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

  def make_prog(self, prog_name):
    self.make_progs([prog_name])

  def make_progs(self, prog_names):
    # call make with all program paths to ensure they are built
    args = ['make']
    for p in prog_names:
      path = os.path.join(PROG_BIN_DIR, p + '_' + self.flavor)
      if self.use_debug_bins:
        path = path + "_dbg"
      args.append(path)
    _ = subprocess.check_call(args, stdout=subprocess.PIPE)

  def _get_data_path(self, prog_name, kw_args):
    dat_path = ["data/" + prog_name]
    if 'variant' in kw_args:
      dat_path.append("_")
      dat_path.append(kw_args['variant'])
    dat_path.append(".txt")
    return "".join(dat_path)

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
    prog_name = "curdir:bin/" + prog_args[0] + '_' + self.flavor
    if self.use_debug_bins:
      prog_name = prog_name + "_dbg"
    args.append(prog_name)
    if len(prog_args) > 1:
      args = args + list(prog_args[1:])

    # run and get stdout/stderr
    print("running:"," ".join(args))
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
      raise subprocess.CalledProcessError(retcode)
    return stdout, stderr

  def _compare(self, got, ok):
    for i in xrange(len(ok)):
      assert (got[i] == ok[i])
    assert (len(got)==len(ok)), "stdout line count differs"

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
    assert stderr == []

# ----- pytest integration -----

def pytest_addoption(parser):
    parser.addoption("--flavor", "-F", action="store", default=None,
        help="select an Amiga compiler flavor to test")
    parser.addoption("--use-debug-bins", "-D", action="store_true", default=False,
        help="run the debug versions of the Amiga binaries")
    parser.addoption("--dump-output", "-O", action="store_true", default=False,
        help="write all vamos output to 'vamos.log'")
    parser.addoption("--gen-data", "-G", action="store_true", default=False,
        help="generate data files by using the output of the test program")
    parser.addoption("--vamos-options", "-V", action="store", default=None,
        help="add options to vamos run. separate options by plus: e.g. -V-t+-T")
    parser.addoption("--vamos-executable", "-E", default=VAMOS_BIN,
        help="replace the vamos executable (default: ../bin/vamos)")

def pytest_runtest_setup(item):
  flv = item.config.getoption("--flavor")
  if flv is not None:
    kw = item.keywords
    if flv not in kw:
      pytest.skip("disabled flavor")

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
