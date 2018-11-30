from __future__ import print_function
import sys
import json

from .tool import Tool
from amitools.vamos.libcore import LibProfiler, LibImplScan
from amitools.vamos.cfgcore import ConfigDict


class LibProfilerTool(Tool):
  def __init__(self):
    Tool.__init__(self, "libprof", "library profile utilities")
    self.profiler = None

  def add_args(self, arg_parser):
    sub = arg_parser.add_subparsers(dest='libprof_cmd')
    # dump
    parser = sub.add_parser('dump',
                            help='display library function profile info')
    parser.add_argument('input', help='profile json file')
    # coverage
    parser = sub.add_parser('coverage',
                            help='display library function coverage info')
    parser.add_argument('input', help='profile json file')

  def setup(self, args):
    return True

  def shutdown(self):
    pass

  def run(self, args):
    if not self._load_profile(args):
      return 1
    cmd = args.libprof_cmd
    if cmd == 'dump':
      return self._do_dump()
    if cmd == 'coverage':
      return self._do_coverage()
    else:
      return 1

  def _load_profile(self, args):
    # read file
    try:
      with open(args.input) as fh:
        data = json.load(fh)
        if 'libs' in data:
          data = ConfigDict(data['libs'])
          self.profiler = LibProfiler()
          self.profiler.set_data(data)
          return True
        else:
          print("no 'libs' found in '%s'" % args.input)
          return False
    except IOError as e:
      print("loading '%s' failed: %s" % (args.input, e))
      return False

  def _do_dump(self):
    self.profiler.dump()
    return 0

  def _do_coverage(self):
    print("%-40s total         valid        called" % 'library')
    lib_names = self.profiler.get_all_lib_names()
    for lib_name in lib_names:
      lib_prof = self.profiler.get_profile(lib_name)
      func_names = lib_prof.get_all_func_names()
      num_valid = 0
      num_covered = 0
      num_total = 0
      for func_name in func_names:
        func_prof = lib_prof.get_func_by_name(func_name)
        if func_prof.tag == LibImplScan.TAG_VALID:
          num_valid += 1
          if func_prof.num > 0:
            num_covered += 1
        num_total += 1
      impl_ratio = 100.0 * num_valid / num_total
      if num_valid > 0:
        coverage = 100.0 * num_covered / num_valid
      else:
        coverage = 0.0
      print("%-40s  %4d  %6.2f  "
            "%4d  %6.2f  %4d" % (lib_name, num_total, impl_ratio,
                                 num_valid, coverage, num_covered))
    return 0
