#!/usr/bin/env python2.7
# rdbtool
# swiss army knife for rdb disk images or devices

import sys
import argparse
import os.path

from amitools.util.CommandQueue import CommandQueue
from amitools.fs.FSError import FSError
from amitools.fs.rdb.RDisk import RDisk
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.DosType import *
from amitools.fs.block.rdb.PartitionBlock import PartitionBlock, PartitionDosEnv
from amitools.fs.block.rdb.FSHeaderBlock import FSHeaderDeviceNode
import amitools.util.KeyValue as KeyValue
import amitools.util.ByteSize as ByteSize
import amitools.util.VerTag as VerTag

# ----- commands -----
class Command:
  def __init__(self, args, opts, edit=False):
    self.args = args
    self.opts = opts
    self.edit = edit
    self.exit_code = 0
    self.blkdev = None
    self.rdisk = None

  def run(self, blkdev, rdisk):
    # optional init blkdev function
    if hasattr(self, "init_blkdev"):
      if blkdev == None:
        self.blkdev = self.init_blkdev(self.args.image_file)
        if self.blkdev == None:
          return 5
        blkdev = self.blkdev

    # optional init rdisk function
    if hasattr(self, "init_rdisk"):
      # close old
      if rdisk != None:
        rdisk.close()
      # create new rdisk
      self.rdisk = self.init_rdisk(blkdev)
      if self.rdisk == None:
        return 6
      rdisk= self.rdisk

    # common handler
    if hasattr(self, 'handle_blkdev'):
      return self.handle_blkdev(blkdev)
    elif hasattr(self, 'handle_rdisk'):
      return self.handle_rdisk(rdisk)
    else:
      return 0

  def has_init_blkdev(self):
    return hasattr(self, 'init_blkdev')

  def need_rdisk(self):
    return hasattr(self, 'handle_rdisk') and not hasattr(self, 'init_rdisk')

class FSCommandQueue(CommandQueue):
  def __init__(self, args, cmd_list, sep, cmd_map):
    CommandQueue.__init__(self, cmd_list, sep, cmd_map)
    self.args = args
    self.blkdev = None
    self.rdisk = None

  def run(self):
    self.img = self.args.image_file
    try:
      # main command loop
      exit_code = CommandQueue.run(self)
    except FSError as e:
      cmd = "'%s'" % " ".join(self.cmd_line)
      print cmd,"FSError:",str(e)
      exit_code = 3
    except IOError as e:
      cmd = "'%s'" % " ".join(self.cmd_line)
      print cmd,"IOError:",str(e)
      exit_code = 4
    finally:
      # close rdisk
      if self.rdisk != None:
        self.rdisk.close()
        if self.args.verbose:
          print "closing rdisk:",self.img
      # close blkdev
      if self.blkdev != None:
        self.blkdev.close()
        if self.args.verbose:
          print "closing image:",self.img
    return exit_code

  def create_cmd(self, cclass, name, opts):
    return cclass(self.args, opts)

  def _open_rdisk(self):
    if self.rdisk == None:
      self.rdisk = RDisk(self.blkdev)
      if self.args.verbose:
        print "opening rdisk:",self.img
      return self.rdisk.open()
    else:
      return True

  def run_first(self, cmd_line, cmd):
    self.cmd_line = cmd_line

    # check if first command is an init command
    if not cmd.has_init_blkdev():
      # auto add 'open' command
      pre_cmd = OpenCommand(self.args, [])
      if self.args.verbose:
        print "auto open command:",self.cmd_line
      exit_code = pre_cmd.run(self.blkdev, self.rdisk)
      if self.args.verbose:
        print "auto open exit_code:",exit_code
      if exit_code != 0:
        return exit_code
      self.blkdev = pre_cmd.blkdev
      # setup rdisk (if necessary)
      if cmd.need_rdisk():
        if not self._open_rdisk():
          raise IOError("No RDB Disk?")

    # run first command
    if self.args.verbose:
      print "command:",self.cmd_line
    if cmd.edit and self.args.read_only:
      raise IOError("Edit commands not allowed in read-only mode")

    # check code of command after __init__ parsing
    if cmd.exit_code != 0:
      return cmd.exit_code

    # perform command
    exit_code = cmd.run(self.blkdev, self.rdisk)
    if cmd.blkdev != None:
      self.blkdev = cmd.blkdev
    if cmd.rdisk != None:
      self.rdisk = cmd.rdisk

    # final exit code
    if self.args.verbose:
      print "exit_code:",exit_code
    return exit_code

  def run_next(self, cmd_line, cmd):
    self.cmd_line = cmd_line
    if self.args.verbose:
      print "command:",self.cmd_line
    # verify command
    if cmd.edit and self.args.read_only:
      raise IOError("Edit commands not allowed in read-only mode")
    # make sure rdisk is set up
    if self.rdisk == None and cmd.need_rdisk():
      if not self._open_rdisk():
        raise IOError("No RDB Disk?")
    # run command
    exit_code = cmd.run(self.blkdev, self.rdisk)
    if cmd.blkdev != None:
      self.blkdev = cmd.blkdev
    if cmd.rdisk != None:
      self.rdisk = cmd.rdisk
    if self.args.verbose:
      print "exit_code:",exit_code
    return exit_code

# ----- Commands -------------------------------------------------------------

# --- Open RDISK device/image ---

class OpenCommand(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts)
  def init_blkdev(self, file_name):
    # make sure image file exists
    if not os.path.exists(file_name):
      raise IOError("Image File not found: '%s'" % file_name)
    # open existing raw block device
    blkdev = RawBlockDevice(file_name, self.args.read_only)
    blkdev.open()
    # try to guess geometry
    geo = DiskGeometry()
    num_blocks = blkdev.num_blocks
    block_bytes = blkdev.block_bytes
    opts = KeyValue.parse_key_value_strings(self.opts)
    if geo.detect(num_blocks * block_bytes, opts) == None:
      raise IOError("Can't detect geometry of disk: '%s'" % file_name)
    blkdev.geo = geo
    return blkdev

# --- Create new RDISK device/image ---

class CreateCommand(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def init_blkdev(self, file_name):
    # do not overwrite an existing image file
    if os.path.exists(file_name) and not self.args.force:
      raise IOError("Image File already exists: '%s'" % file_name)
    # make sure size is given
    if len(self.opts) < 1:
      print "Usage: create ( size=<n> | chs=<c,h,s> )"
      return None
    # determine disk geometry
    opts = KeyValue.parse_key_value_strings(self.opts)
    geo = DiskGeometry()
    if geo.setup(opts) == None:
      raise IOError("Can't set geometry of disk: '%s'" % file_name)
    else:
      # create new empty image file for geometry
      blkdev = RawBlockDevice(file_name)
      blkdev.create(geo.get_num_blocks())
      blkdev.geo = geo
      return blkdev

# --- Init existing disk image ---

class InitCommand(OpenCommand):
  def init_rdisk(self, blkdev):
    opts = KeyValue.parse_key_value_strings(self.opts)
    # number of cylinders for RDB
    if opts.has_key('rdb_cyls'):
      rdb_cyls = int(opts['rdb_cyls'])
    else:
      rdb_cyls = 1
    rdisk = RDisk(blkdev)
    rdisk.create(blkdev.geo, rdb_cyls=rdb_cyls)
    return rdisk

# --- Info about rdisk ----

class InfoCommand(Command):
  def handle_rdisk(self, rdisk):
    lines = rdisk.get_info()
    for l in lines:
      print l
    return 0

# --- Show rdisk structures ---

class ShowCommand(Command):
  def handle_rdisk(self, rdisk):
    show_hex = "hex" in self.opts
    rdisk.dump(show_hex)
    return 0

# --- Show allocation map ---

class MapCommand(Command):
  def handle_rdisk(self, rdisk):
    bm = rdisk.get_block_map()
    num = 0
    off = 0
    for i in bm:
      if num == 0:
        print "%06d: " % off,
      print i,
      off += 1
      num += 1
      if num == 16:
        num = 0
        print
    return 0

# --- Free Partition Ranges

class FreeCommand(Command):
  def handle_rdisk(self, rdisk):
    ranges = rdisk.get_free_cyl_ranges()
    for r in ranges:
      print r
    return 0

# --- Add a partition ---

class PartEditCommand(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)

  def parse_opts(self, rdisk):
    self.popts = KeyValue.parse_key_value_strings(self.opts)
    self.rdisk = rdisk

  def get_dos_type(self, empty=False):
    if self.popts.has_key('fs'):
      fs_str = self.popts['fs']
    elif self.popts.has_key('dostype'):
      fs_str = self.popts['dostype']
    elif not empty:
      fs_str = self.args.dostype
    else:
      return None
    return parse_dos_type_str(str(fs_str))

  def get_drv_name(self, empty=False):
    if self.popts.has_key('name'):
      drv_name = self.popts['name']
    elif empty:
      drv_name = None
    else:
      drv_name = "%s%d" % (self.args.drive_prefix, self.rdisk.get_num_partitions())
    return drv_name

  def get_bootable(self, empty=False):
    if self.popts.has_key('bootable'):
      return bool(self.popts['bootable'])
    elif not empty:
      return False
    else:
      return None

  def get_boot_pri(self, empty=False):
    if self.popts.has_key('pri'):
      return self.popts['pri']
    elif not empty:
      return 0
    else:
      return None

  def get_automount(self, empty=False):
    if self.popts.has_key('automount'):
      return bool(self.popts['automount'])
    elif not empty:
      return True
    else:
      return None

  def get_flags(self, empty=False, old_flags=0):
    flags = 0
    bootable = self.get_bootable(empty=empty)
    if bootable is not None:
      if bootable:
        flags |= PartitionBlock.FLAG_BOOTABLE
    else:
      flags |= (old_flags) & PartitionBlock.FLAG_BOOTABLE
    automount = self.get_automount(empty=empty)
    if automount is not None:
      if not automount:
        flags |= PartitionBlock.FLAG_NO_AUTOMOUNT
    else:
      flags |= (old_flags) & PartitionBlock.FLAG_NO_AUTOMOUNT
    return flags

  def get_more_dos_env(self):
    more_dos_env = []
    valid_keys = PartitionDosEnv.valid_keys
    for key in self.popts:
      if key in valid_keys:
        more_dos_env.append((key, self.popts[key]))
    if len(more_dos_env) > 0:
      return more_dos_env
    else:
      return None

  def get_more_dos_env_info(self):
    valid_keys = PartitionDosEnv.valid_keys
    info = map(lambda x : "[%s=<n>]" % x, valid_keys)
    return " ".join(info)

  def get_cyl_range(self):
    start = None
    if self.popts.has_key('start'):
      start = int(self.popts['start'])
    # range with start=<n> end=<n>
    if self.popts.has_key('end'):
      end = int(self.popts['end'])
      if start == None or end <= start:
        return None
      else:
        return (start, end)
    # expect a size
    elif self.popts.has_key('size'):
      size = self.popts['size']
      cyls = None
      if type(size) == int:
        cyls = size
      # size in bytes
      elif size[-1] in ('b','B'):
        bytes = ByteSize.parse_byte_size_str(size[:-1])
        if bytes == None:
          return None
        cyls = bytes / self.rdisk.get_cylinder_bytes()
      # size in percent
      elif size[-1] == '%':
        prc = float(size[:-1])
        cyls = int(prc * self.rdisk.get_logical_cylinders() / 100.0)
      # size in cylinders
      else:
        cyls = ByteSize.parse_byte_size_str(size)

      # check cyls
      if cyls == None or cyls < 1:
        return None
      # find a range if no start is given
      if start == None:
        start = self.rdisk.find_free_cyl_range_start(cyls)
        if start == None:
          return None
      return (start, start + cyls - 1)
    # nothing specified -> get next free range
    else:
      ranges = self.rdisk.get_free_cyl_ranges()
      if ranges == None:
        return None
      return ranges[0]

class AddCommand(PartEditCommand):
  def handle_rdisk(self, rdisk):
    self.parse_opts(rdisk)
    lo_hi = self.get_cyl_range()
    if lo_hi == None:
      print "ERROR: invalid partition range given!"
      return 1
    dostype = self.get_dos_type()
    if dostype == None:
      print "ERROR: invalid dos type!"
      return 1
    drv_name = self.get_drv_name()
    if drv_name == None:
      print "ERROR: invalid drive name!"
    flags = self.get_flags()
    boot_pri = self.get_boot_pri()
    more_dos_env = self.get_more_dos_env()
    print "creating: '%s' %s %s" % (drv_name, lo_hi, num_to_tag_str(dostype))
    # add partition
    if rdisk.add_partition(drv_name, lo_hi, dos_type=dostype, flags=flags, boot_pri=boot_pri, more_dos_env=more_dos_env):
      return 0
    else:
      print "ERROR: creating partition: '%s': %s" % (drv_name, lo_hi)
      return 1

class ChangeCommand(PartEditCommand):
  def handle_rdisk(self, rdisk):
    if len(self.opts) < 1:
      print "Usage: change <id> [name=<s>] [dostype=<n|tag>] [automount=<b>] [bootable=<b>] [pri=<n>] " + self.get_more_dos_env_info()
      return 1
    else:
      p = rdisk.find_partition_by_string(self.opts[0])
      if p != None:
        self.parse_opts(rdisk)
        dostype = self.get_dos_type(empty=True)
        drv_name = self.get_drv_name(empty=True)
        flags = self.get_flags(empty=True, old_flags=p.get_flags())
        boot_pri = self.get_boot_pri(empty=True)
        more_dos_env = self.get_more_dos_env()
        # change partition
        if rdisk.change_partition(p.num, drv_name=drv_name, dos_type=dostype, flags=flags, boot_pri=boot_pri, more_dos_env=more_dos_env):
          return 0
        else:
          print "ERROR: changing partition: '%s'" % (drv_name)
          return 1
      else:
        print "Can't find partition: '%s'" % self.opts[0]
        return 1

# --- Fill empty space with partitions ---

class FillCommand(PartEditCommand):
  def handle_rdisk(self, rdisk):
    self.parse_opts(rdisk)
    ranges = rdisk.get_free_cyl_ranges()
    # nothing to do
    if ranges == None:
      return 0
    for lo_hi in ranges:
      drv_name = self.get_drv_name()
      if drv_name == None:
        print "ERROR: invalid drive name!"
      dostype = self.get_dos_type()
      if dostype == None:
        print "ERROR: invalid dostype given!"
        return 1
      print "creating: '%s' %s %s" % (drv_name, lo_hi, num_to_tag_str(dostype))
      # add partition
      if not rdisk.add_partition(drv_name, lo_hi, dos_type=dostype):
        print "ERROR: creating partition: '%s': %s" % (drv_name, lo_hi)
        return 1
    return 0

# --- Delete partition command ---

class DeleteCommand(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)

  def handle_rdisk(self, rdisk):
    if len(self.opts) < 1:
      print "Usage: delete <id>"
      return 1
    else:
      p = rdisk.find_partition_by_string(self.opts[0])
      if p != None:
        if not rdisk.delete_partition(p.num):
          print "ERROR: deleting partition: '%s'" % self.opts[0]
          return 1
        else:
          return 0
      else:
        print "Can't find partition: '%s'" % self.opts[0]
        return 1

# --- Filesystem Commands ---

class FSGetCommand(Command):
  def handle_rdisk(self, rdisk):
    if len(self.opts) < 2:
      print "Usage: fsget <id> <file_name>"
      return 1
    else:
      num = int(self.opts[0])
      fs = rdisk.get_filesystem(num)
      if fs == None:
        print "fsget: invalid filesystem index",num
        return 1
      else:
        file_name = self.opts[1]
        data = fs.get_data()
        f = open(file_name,"wb")
        f.write(data)
        f.close()
        return 0

class FSAddCommand(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)

  def parse_opts(self):
    self.popts = KeyValue.parse_key_value_strings(self.opts)

  def get_dos_type(self):
    if self.popts.has_key('fs'):
      fs_str = self.popts['fs']
    elif self.popts.has_key('dostype'):
      fs_str = self.popts['dostype']
    else:
      fs_str = self.args.dostype
    return parse_dos_type_str(str(fs_str))

  def handle_rdisk(self, rdisk):
    self.parse_opts()
    valid_flags = FSHeaderDeviceNode.valid_flags
    if len(self.opts) < 1:
      flag_info = map(lambda x : "[%s=<n>]" % x, valid_flags)
      flag_info = " ".join(flag_info)
      print "Usage: fsadd <file_name> [dostype=<n|tag>] [version=<n.m>] " + flag_info
      return 1
    else:
      # parse options
      opts = KeyValue.parse_key_value_strings(self.opts)
      # read file data
      file_name = self.opts[0]
      f = open(file_name,"rb")
      data = f.read()
      f.close()
      # get version from binary
      tag = VerTag.find(data)
      ver = None
      if tag != None:
        ver = VerTag.get_version(tag)
      if ver == None:
        ver = (0,0)
      # overwrite version from options
      if opts.has_key('version'):
        vstr = opts['version']
        pos = vstr.find('.')
        if pos != -1:
          ver = (int(vstr[:pos]),int(vstr[pos+1:]))
      # valid fs flags
      dev_flags = []
      for key in opts:
        if key in valid_flags:
          dev_flags.append((key,opts[key]))
      # add fs
      version = ver[0] << 16 | ver[1]
      # get dostype
      dostype = self.get_dos_type()
      if rdisk.add_filesystem(data, dos_type=dostype, version=version, dev_flags=dev_flags):
        return 0
      else:
        print "ERROR adding filesystem! (no space in RDB left)"
        return 1

class FSDeleteCommand(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)

  def handle_rdisk(self, rdisk):
    if len(self.opts) < 1:
      print "Usage: fsdelete <fid>"
      return 1
    else:
      fs = rdisk.find_filesystem_by_string(self.opts[0])
      if fs != None:
        if not rdisk.delete_filesystem(fs.num):
          print "ERROR deleting filesystem: '%s'" % self.opts[0]
          return 1
        else:
          return 0
      else:
        print "ERROR finding filesystem: '%s'" % self.opts[0]
        return 1

class FSFlagsCommand(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)

  def handle_rdisk(self, rdisk):
    if len(self.opts) < 2:
      print "Usage: fsflags <fid> [ clear | key=<val> ... ]"
      return 1
    else:
      fs = rdisk.find_filesystem_by_string(self.opts[0])
      if fs != None:
        opts = KeyValue.parse_key_value_strings(self.opts[1:])
        valid_flags = fs.get_valid_flag_names()
        flags = []
        clear = False
        for o in opts:
          if o in valid_flags:
            flags.append((o,opts[o]))
          elif o == 'clear':
            clear = True
        fs.set_flags(flags, clear)
        return 0
      else:
        print "ERROR finding filesystem: '%s'" % self.opts[0]
        return 1

# ----- main -----
def main():
  # call scanner and process all files with selected command
  cmd_map = {
  "open" : OpenCommand,
  "create" : CreateCommand,
  "init" : InitCommand,
  "info" : InfoCommand,
  "show" : ShowCommand,
  "free" : FreeCommand,
  "add" : AddCommand,
  "fill" : FillCommand,
  "fsget" : FSGetCommand,
  "fsadd" : FSAddCommand,
  "fsdelete" : FSDeleteCommand,
  "fsflags" : FSFlagsCommand,
  "map" : MapCommand,
  "delete" : DeleteCommand,
  "change" : ChangeCommand
  }

  parser = argparse.ArgumentParser()
  parser.add_argument('image_file')
  parser.add_argument('command_list', nargs='+', help="command: "+",".join(cmd_map.keys()))
  parser.add_argument('-v', '--verbose', action='store_true', default=False, help="be more verbos")
  parser.add_argument('-s', '--seperator', default='+', help="set the command separator char sequence")
  parser.add_argument('-r', '--read-only', action='store_true', default=False, help="read-only operation")
  parser.add_argument('-f', '--force', action='store_true', default=False, help="force overwrite existing image")
  parser.add_argument('-p', '--drive-prefix', default='DH', help="set default drive name prefix (DH -> DH0, DH1, ...)")
  parser.add_argument('-t', '--dostype', default='ffs+intl', help="set default dos type")
  args = parser.parse_args()

  cmd_list = args.command_list
  sep = args.seperator
  queue = FSCommandQueue(args, cmd_list, sep, cmd_map)
  code = queue.run()
  return code


if __name__ == '__main__':
  sys.exit(main())
