from __future__ import print_function

import unittest
import subprocess
import os

VAMOS_BIN="../vamos"
VAMOS_ARGS=['-c', 'test.vamosrc']
PROG_BIN_DIR="bin"
PROG_FLAVORS=('vc', 'gcc', 'agcc', 'sc')

class VamosTestOptions:
  vamos_args = []
  show_output = False
  generate_data = False

class VamosTestCase(unittest.TestCase):

  flavor = 'vc'
  programs = []
  opts = VamosTestOptions()

  def make_progs(self, prog_names):
    # call make with all program paths to ensure they are built
    args = ['make']
    for p in prog_names:
      args.append(os.path.join(PROG_BIN_DIR, p + '_' + self.flavor))
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
       - variant = a postfix string to append to data file

       returns:
       - returncode of process
       - stdout as line array
    """
    # run vamos with prog
    args = [VAMOS_BIN] + VAMOS_ARGS
    if len(self.opts.vamos_args) > 0:
      args = args + self.opts.vamos_args
    prog_name = "curdir:bin/" + prog_args[0] + '_' + self.flavor
    args.append(prog_name)
    if len(prog_args) > 1:
      args = args + prog_args[1:]

    # stdin given?
    if 'stdin' in kw_args:
      stdin = kw_args['stdin']
    else:
      stdin = None

    # run and get stdout/stderr
    print("running:"," ".join(args))
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate(stdin)

    # process stdout
    stdout = stdout.splitlines()

    # show?
    if self.opts.show_output:
      for line in stdout:
        print(line)

    # generate data?
    if self.opts.generate_data:
      dat_path = self._get_data_path(prog_args[0], kw_args)
      print("wrote output to '%s'" % dat_path)
      f = open(dat_path, "w")
      for line in stdout:
        f.write(line + "\n")
      f.close()

    # show stderr
    if len(stderr) > 0:
      print(stderr)

    return (p.returncode, stdout)

  def run_prog_checked(self, *prog_args, **kw_args):
    """like run_prog() but check return value and assume its 0"""
    retcode, stdout = self.run_prog(*prog_args, **kw_args)
    if retcode != 0:
      raise subprocess.CalledProcessError(retcode)
    return stdout

  def _compare(self, got, ok):
    for i in xrange(len(ok)):
      self.assertEquals(got[i], ok[i])

  def run_prog_check_data(self, *prog_args, **kw_args):
    """like run_prog_checked() but also verify the stdout
       and compare with the corresponding data file of the suite"""
    stdout = self.run_prog_checked(*prog_args, **kw_args)
    # compare stdout with data
    dat_path = self._get_data_path(prog_args[0], kw_args)
    f = open(dat_path, "r")
    ok_stdout = []
    for l in f:
      ok_stdout.append(l.strip())
    f.close()
    self._compare(stdout, ok_stdout)

  def setUp(self):
    # ensure that all required programs are built
    if len(self.programs) > 0:
      self.make_progs(self.programs)
