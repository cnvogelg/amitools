from __future__ import print_function

import unittest
import subprocess
import os

VAMOS_BIN="../vamos"
VAMOS_ARGS=['-c', 'test.vamosrc']
PROG_BIN_DIR="bin"
PROG_FLAVORS=('vc', 'gcc', 'agcc', 'sc')

class VamosTestCase(unittest.TestCase):

  flavor = 'vc'
  vamos_args = []
  programs = []

  def make_progs(self, prog_names):
    # call make with all program paths to ensure they are built
    args = ['make']
    for p in prog_names:
      args.append(os.path.join(PROG_BIN_DIR, p + '_' + self.flavor))
    _ = subprocess.check_call(args, stdout=subprocess.PIPE)

  def run_prog(self, *prog_args, **kw_args):
    """run an AmigaOS binary with vamos

       kw_args:
       - vamos_args = list of vamos options
       - stdin = string for stdin

       returns:
       - returncode of process
       - stdout as line array
    """
    # run vamos with prog
    args = [VAMOS_BIN] + VAMOS_ARGS
    if len(self.vamos_args) > 0:
      args = args + self.vamos_args
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

    # show stderr
    if len(stderr) > 0:
      print(stderr)

    return (p.returncode, stdout)

  def run_prog_checked(self, *prog_args, **kw_args):
    retcode, stdout = self.run_prog(*prog_args, **kw_args)
    if retcode != 0:
      raise subprocess.CalledProcessError(retcode)
    return stdout

  def setUp(self):
    # ensure that all required programs are built
    if len(self.programs) > 0:
      self.make_progs(self.programs)
