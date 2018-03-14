import os
import re
from .FuncTable import FuncTable
from .FuncDef import FuncDef
from amitools.util.DataDir import get_data_sub_dir

def get_fd_name(lib_name):
  """return the name associated for a given library/device name"""
  if lib_name.endswith(".device"):
    fd_name = lib_name.replace(".device", "_lib.fd")
  elif lib_name.endswith(".library"):
    fd_name = lib_name.replace(".library", "_lib.fd")
  else:
    raise ValueError("can't find fd name for '%s'" % lib_name)
  return fd_name

def is_device(lib_name):
  """return true if given name is associated with a device"""
  return lib_name.endswith(".device")

def read_lib_fd(lib_name, fd_dir=None, add_std_calls=True):
  # get default path if none is given
  if fd_dir is None:
    fd_dir = get_data_sub_dir("fd")
  # get fd path
  fd_name = get_fd_name(lib_name)
  fd_path = os.path.join(fd_dir, fd_name)
  # try to read fd
  fd = read_fd(fd_path)
  fd.is_device = is_device(lib_name)
  if add_std_calls:
    fd.add_std_calls()
  return fd

def read_fd(fname):
  func_pat = "([A-Za-z][_A-Za-z00-9]+)\((.*)\)\((.*)\)"
  func_table = None
  bias = 0
  private = True
  # parse file
  f = open(fname, "r")
  for line in f:
    l = line.strip()
    if len(l) > 1 and l[0] != '*':
        # a command
        if l[0] == '#' and l[1] == '#':
          cmdline = l[2:]
          cmda = cmdline.split(" ")
          cmd = cmda[0]
          if cmd == "base":
            base = cmda[1]
            func_table = FuncTable(base)
          elif cmd == "bias":
            bias = int(cmda[1])
          elif cmd == "private":
            private = True
          elif cmd == "public":
            private = False
          elif cmd == "end":
            break
          else:
            print "Invalid command:",cmda
            return None
        # a function
        else:
          m = re.match(func_pat, l)
          if m == None:
            raise IOError("Invalid FD Format")
          else:
            name = m.group(1)
            # create a function definition
            func_def = FuncDef(name, bias, private)
            if func_table != None:
              func_table.add_func(func_def)
            # check args
            args = m.group(2)
            regs = m.group(3)
            arg = args.replace(',','/').split('/')
            reg = regs.replace(',','/').split('/')
            if len(arg) != len(reg):
              # hack for double reg args found in mathieeedoub* libs
              if len(arg) * 2 == len(reg):
                arg_hi = map(lambda x: x + "_hi", arg)
                arg_lo = map(lambda x: x + "_lo", arg)
                arg = [x for pair in zip(arg_hi, arg_lo) for x in pair]
              else:
                raise IOError("Reg and Arg name mismatch in FD File")
            if arg[0] != '':
              num_args = len(arg)
              for i in range(num_args):
                func_def.add_arg(arg[i],reg[i])
          bias += 6
  f.close()
  return func_table

def write_fd(fname, fd, add_private):
  fo = open(fname, "w")
  fo.write("##base %s\n" % (fd.get_base_name()))
  last_bias = 0
  last_mode = None
  funcs = fd.get_funcs()
  for f in funcs:
    if not f.is_private() or add_private:
      # check new mode
      if f.is_private():
        new_mode = "private"
      else:
        new_mode = "public"
      if last_mode != new_mode:
        fo.write("##%s\n" % new_mode)
        last_mode = new_mode
      # check new bias
      new_bias = f.get_bias()
      if last_bias + 6 != new_bias:
        fo.write("##bias %d\n" % new_bias)
      last_bias = new_bias
      # build func
      line = f.get_name()
      args = f.get_args()
      if args == None:
        line += "()()"
      else:
        line += "(" + ",".join(map(lambda x : x[0], args)) + ")"
        line += "(" + "/".join(map(lambda x : x[1], args)) + ")"
      fo.write("%s\n" % line)
  fo.write("##end\n")
  fo.close()


