#!/usr/bin/env python2.7
# xdftool
# swiss army knife for adf and hdf amiga disk images

from __future__ import absolute_import
from __future__ import print_function

import sys
import argparse
import os.path

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.FSError import *
from amitools.fs.Imager import Imager
from amitools.fs.Repacker import Repacker
from amitools.fs.block.BootBlock import BootBlock
from amitools.fs.block.RootBlock import RootBlock
from amitools.util.CommandQueue import CommandQueue
from amitools.util.HexDump import *
from amitools.util.DisAsm import DisAsm
import amitools.util.KeyValue as KeyValue
from amitools.fs.rdb.RDisk import RDisk
from amitools.fs.FSString import FSString
import amitools.fs.DosType as DosType

# system encoding
def make_fsstr(s):
  # fetch default encoding (if available)
  encoding = sys.stdin.encoding
  if encoding is None:
    # assume win default encoding
    if os.platform == "win32":
      encoding = "cp1252"
    else:
      encoding = "utf-8"
  u = s.decode(encoding)
  return FSString(u)

# ----- commands -----
class Command:
  def __init__(self, args, opts, edit=False):
    self.args = args
    self.opts = opts
    self.edit = edit
    self.exit_code = 0

    self.volume = None
    self.blkdev = None

  def run(self, blkdev, vol):
    # optional init blkdev function
    if hasattr(self, "init_blkdev"):
      if blkdev == None:
        self.blkdev = self.init_blkdev(self.args.image_file)
        if self.blkdev == None:
          return 5
        blkdev = self.blkdev

    # optional init volume function
    if hasattr(self, "init_vol"):
      # close old
      if vol != None:
        vol.close()
      # create new volume
      self.volume = self.init_vol(blkdev)
      if self.volume == None:
        return 6
      vol = self.volume

    # common handler
    if hasattr(self, 'handle_blkdev'):
      return self.handle_blkdev(blkdev)
    elif hasattr(self, 'handle_vol'):
      return self.handle_vol(vol)
    else:
      return 0

  def has_init_blkdev(self):
    return hasattr(self, 'init_blkdev')

  def need_volume(self):
    return hasattr(self, 'handle_vol') and not hasattr(self, 'init_vol')

# ----- command handler -----
class FSCommandQueue(CommandQueue):
  def __init__(self, args, cmd_list, sep, cmd_map):
    CommandQueue.__init__(self, cmd_list, sep, cmd_map)
    self.args = args
    self.blkdev = None
    self.volume = None

  def run(self):
    self.img = self.args.image_file
    try:
      # main command loop
      exit_code = CommandQueue.run(self)
    except FSError as e:
      cmd = "'%s'" % " ".join(self.cmd_line)
      print(cmd, "FSError:", e)
      exit_code = 3
    except IOError as e:
      cmd = "'%s'" % " ".join(self.cmd_line)
      print(cmd, "IOError:", e)
      exit_code = 4
    finally:
      # close volume
      if self.volume != None:
        self.volume.close()
        if self.args.verbose:
          print("closing volume:", self.img)
      # close blkdev
      if self.blkdev != None:
        self.blkdev.close()
        if self.args.verbose:
          print("closing image:",self.img)
    return exit_code

  def create_cmd(self, cclass, name, opts):
    return cclass(self.args, opts)

  def _open_volume(self):
    # setup volume
    if self.volume == None:
      self.volume = ADFSVolume(self.blkdev)
      if self.args.verbose:
        print("opening volume:", self.img)
      self.volume.open()

  def run_first(self, cmd_line, cmd):
    self.cmd_line = cmd_line

    # check if first command is an init command
    if not cmd.has_init_blkdev():
      # auto add 'open' command
      pre_cmd = OpenCmd(self.args, [])
      if self.args.verbose:
        print("auto open command:", self.cmd_line)
      exit_code = pre_cmd.run(self.blkdev, self.volume)
      if self.args.verbose:
        print("auto open exit_code:", exit_code)
      if exit_code != 0:
        return exit_code
      self.blkdev = pre_cmd.blkdev
      # setup volume (if necessary)
      if cmd.need_volume():
        self._open_volume()

    # run first command
    if self.args.verbose:
      print("command:", self.cmd_line)
    if cmd.edit and self.args.read_only:
      raise IOError("Edit commands not allowed in read-only mode")

    # check code of command after __init__ parsing
    if cmd.exit_code != 0:
      return cmd.exit_code

    # perform command
    exit_code = cmd.run(self.blkdev, self.volume)
    if cmd.blkdev != None:
      self.blkdev = cmd.blkdev
    if cmd.volume != None:
      self.volume = cmd.volume

    # final exit code
    if self.args.verbose:
      print("exit_code:", exit_code)
    return exit_code

  def run_next(self, cmd_line, cmd):
    self.cmd_line = cmd_line
    if self.args.verbose:
      print("command:", self.cmd_line)
    # verify command
    if cmd.edit and self.args.read_only:
      raise IOError("Edit commands not allowed in read-only mode")
    # make sure volume is set up
    if self.volume == None and cmd.need_volume():
      self._open_volume()
    # run command
    exit_code = cmd.run(self.blkdev, self.volume)
    if cmd.blkdev != None:
      self.blkdev = cmd.blkdev
    if cmd.volume != None:
      self.volume = cmd.volume
    if self.args.verbose:
      print("exit_code:", exit_code)
    return exit_code

# ----- Init: Open/Create -----

class OpenCmd(Command):
  def init_blkdev(self, image_file):
    opts = KeyValue.parse_key_value_strings(self.opts)
    f = BlkDevFactory()
    return f.open(image_file, options=opts, read_only=self.args.read_only)

class CreateCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)

  def init_blkdev(self, image_file):
    opts = KeyValue.parse_key_value_strings(self.opts)
    f = BlkDevFactory()
    return f.create(image_file, options=opts, force=self.args.force)

class FormatCmd(Command):
  def init_blkdev(self, image_file):
    opts = KeyValue.parse_key_value_strings(self.opts[1:])
    f = BlkDevFactory()
    return f.create(image_file, options=opts, force=self.args.force)

  def init_vol(self, blkdev):
    vol = ADFSVolume(blkdev)
    n = len(self.opts)
    if n < 1 or n > 2:
      print("Usage: format <volume_name> [dos_type]")
      return None
    else:
      if n > 1:
        dos_str = self.opts[1]
        dos_type = DosType.parse_dos_type_str(dos_str)
        if dos_type is None:
          print("ERROR invalid dos_tpye:", dos_str)
          return None
      else:
        dos_type = None
      vol_name = make_fsstr(self.opts[0])
      vol.create(vol_name, dos_type=dos_type)
      return vol

# ----- Pack/Unpack -----

class PackCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
    self.imager = Imager()
    n = len(self.opts)
    if n == 0:
      print("Usage: pack <in_path> [dos_type] [out_size]")
      self.exit_code = 1
    else:
      self.in_path = self.opts[0]
      blkdev_opts = None
      dos_type = None
      if n > 1:
        # is a dostype given?
        dos_str = opts[1]
        dos_type = DosType.parse_dos_type_str(dos_str)
        if dos_type is not None:
          begin = 2
        else:
          begin = 1
        # take remainder as blkdev opts
        blkdev_opts = KeyValue.parse_key_value_strings(opts[begin:])
      self.blkdev_opts = blkdev_opts
      self.dos_type = dos_type
      self.imager.pack_begin(self.in_path)

  def init_blkdev(self, image_file):
    return self.imager.pack_create_blkdev(self.in_path, image_file, force=self.args.force, options=self.blkdev_opts)

  def init_vol(self, blkdev):
    return self.imager.pack_create_volume(self.in_path, blkdev, dos_type=self.dos_type)

  def handle_vol(self, volume):
    self.imager.pack_root(self.in_path, volume)
    self.imager.pack_end(self.in_path, volume)
    if self.args.verbose:
      print("Packed %d bytes" % (self.imager.get_total_bytes()))
    return 0

class UnpackCmd(Command):
  def handle_vol(self, vol):
    n = len(self.opts)
    if n == 0:
      print("Usage: unpack <out_path>")
      return 1
    else:
      out_path = self.opts[0]
      img = Imager()
      img.unpack(vol, out_path)
      if self.args.verbose:
        print("Unpacked %d bytes" % (img.get_total_bytes()))
      return 0

class RepackCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
    n = len(self.opts)
    if n == 0:
      print("Usage: repack <src_path> [in_size]")
      self.exit_code = 1
    in_img = self.opts[0]
    in_opts = KeyValue.parse_key_value_strings(self.opts[1:])
    self.repacker = Repacker(in_img, in_opts)
    if not self.repacker.create_in():
      self.exit_code = 2

  def init_blkdev(self, image_file):
    return self.repacker.create_out_blkdev(image_file)

  def init_vol(self, blkdev):
    return self.repacker.create_out_volume(blkdev)

  def handle_vol(self, vol):
    self.repacker.repack()
    return 0

# ----- Query Image -----

# list: list directory tree
class ListCmd(Command):
  def handle_vol(self, vol):
    n = len(self.opts)
    if n == 0:
      vol.root_dir.list(all=True)
      show_info = True
      show_all = True
      node = vol.get_root_dir()
    else:
      name = make_fsstr(self.opts[0])
      node = vol.get_path_name(name)
      if node != None:
        show_all = "all" in self.opts
        show_detail = "detail" in self.opts
        show_info = "info" in self.opts
        node.list(all=show_all, detail=show_detail)
      else:
        print("ERROR path not found:", node)
        return 2
    if show_info:
      info = node.get_info(show_all)
      for line in info:
        print(line)
    return 0

class TypeCmd(Command):
  def handle_vol(self, vol):
    p = self.opts
    if len(p) == 0:
      print("Usage: type <ami_file>")
      return 1
    else:
      name = make_fsstr(p[0])
      data = vol.read_file(name)
      print(data)
      return 0

class ReadCmd(Command):
  def handle_vol(self, vol):
    p = self.opts
    n = len(p)
    if n == 0 or n > 2:
      print("Usage: read <ami_file|dir> [sys_file]")
      return 1
    # determine output name
    out_name = os.path.basename(p[0])
    if n == 2:
      if os.path.isdir(p[1]):
        out_name = os.path.join(p[1],out_name)
      else:
        out_name = p[1]
    # single file operation
    name = make_fsstr(p[0])
    node = vol.get_path_name(name)
    if node == None:
      print("Node not found:", p[0])
      return 2
    # its a file
    if node.is_file():
      data = node.get_file_data()
      # write data to file
      fh = open(out_name,"wb")
      fh.write(data)
      fh.close()
    # its a dir
    elif node.is_dir():
      img = Imager()
      img.unpack_dir(node, out_name)
    node.flush()
    return 0

class InfoCmd(Command):
  def handle_vol(self, vol):
    info = vol.get_info()
    for line in info:
      print(line)
    return 0

# ----- Edit Image -----

class MakeDirCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def handle_vol(self, vol):
    if len(self.opts) != 1:
      print("Usage: mkdir <dir_path>")
      return 1
    else:
      dir_path = make_fsstr(self.opts[0])
      vol.create_dir(dir_path)
      return 0

class WriteCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def handle_vol(self, vol):
    n = len(self.opts)
    if n == 0 or n > 2:
      print("Usage: write <sys_file|dir> [ami_path]")
      return 1
    # get file_name and ami_path
    sys_file = self.opts[0]
    file_name = os.path.basename(sys_file)
    if n > 1:
        ami_path = self.opts[1]
    else:
        ami_path = os.path.basename(sys_file)
    # check sys path
    if not os.path.exists(sys_file):
      print("File not found:", sys_file)
      return 2

    ami_path = make_fsstr(ami_path)
    file_name = make_fsstr(file_name)
    # handle file
    if os.path.isfile(sys_file):
      fh = open(sys_file,"rb")
      data = fh.read()
      fh.close()
      vol.write_file(data, ami_path, file_name)
    # handle dir
    elif os.path.isdir(sys_file):
      parent_node, dir_name = vol.get_create_path_name(ami_path,file_name)
      if parent_node == None:
        print("Invalid path", ami_path)
        return 2
      node = parent_node.create_dir(dir_name)
      img = Imager()
      img.pack_dir(sys_file, node)

    return 0

class DeleteCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def handle_vol(self, vol):
    n = len(self.opts)
    if n == 0:
      print("Usage: delete <ami_path> [wipe] [all]")
      return 1
    do_wipe = 'wipe' in self.opts
    do_all = 'all' in self.opts
    path = make_fsstr(self.opts[0])
    node = vol.delete(path, wipe=do_wipe, all=do_all)
    return 0

class ProtectCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def handle_vol(self, vol):
    n = len(self.opts)
    if n != 2:
      print("Usage: protect <ami_file> <protect>")
      return 1
    name = make_fsstr(self.opts[0])
    pr_str = self.opts[1]
    node = vol.get_path_name(name)
    if node != None:
      node.change_protect_by_string(pr_str)
      return 0
    else:
      print("Can't find node:", name)
      return 2

class CommentCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def handle_vol(self, vol):
    n = len(self.opts)
    if n != 2:
      print("Usage: comment <ami_file> <comment>")
      return 1
    name = make_fsstr(self.opts[0])
    comment = make_fsstr(self.opts[1])
    node = vol.get_path_name(name)
    if node != None:
      node.change_comment(comment)
      return 0
    else:
      print("Can't find node:", name)
      return 2

class TimeCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def handle_vol(self, vol):
    n = len(self.opts)
    if n != 2:
      print("Usage: time <ami_file> <time>")
      return 1
    name = self.opts[0]
    tstr = self.opts[1]
    node = vol.get_path_name(name)
    if node != None:
      node.change_mod_ts_by_string(tstr)
      return 0
    else:
      print("Can't find node:", name)
      return 2

class RelabelCmd(Command):
  def __init__(self, args, opts):
    Command.__init__(self, args, opts, edit=True)
  def handle_vol(self, vol):
    n = len(self.opts)
    if n != 1:
      print("Usage: relabel <new_name>")
      return 1
    name = self.opts[0]
    node = vol.relabel(name)
    return 0

# ----- Block Tools -----

class BlockCmd(Command):
  def handle_vol(self, vol):
    n = len(self.opts)
    if n == 0:
      print("Usage: block ( boot | root | node <ami_file> [data] | dump <block_no> )")
      return 1
    cmd = self.opts[0]
    if cmd == 'boot':
      vol.boot.dump()
      return 0
    elif cmd == 'root':
      vol.root.dump()
      return 0
    elif cmd == 'node':
      if n == 1:
        print("No node given!")
        return 1
      else:
        name = make_fsstr(self.opts[1])
        node = vol.get_path_name(name)
        if node != None:
          with_data = "data" in self.opts
          node.dump_blocks(with_data)
          return 0
        else:
          print("Can't find node:", name)
          return 2
    elif cmd == 'dump':
      if n == 1:
        print("No block number given!")
        return 1
      else:
        block_no = int(self.opts[1])
        data = vol.blkdev.read_block(block_no)
        print_hex(data)

# ----- Bitmap Tools -----

class BitmapCmd(Command):
  def handle_vol(self, vol):
    n = len(self.opts)
    if n == 0:
      print("Usage: bitmap ( free | used | find [n] | all | maps | root [all] | node <path> [all] [entries]) [brief]")
      return 1
    cmd = self.opts[0]

    # brief mode
    brief = False
    if self.opts[-1] == 'brief':
      brief = True
      self.opts = self.opts[:-1]

    if cmd == 'free':
      vol.bitmap.print_free(brief)
      return 0
    elif cmd == 'used':
      vol.bitmap.print_used(brief)
      return 0
    elif cmd == 'find':
      if n == 2:
        num = int(self.opts[1])
        blk_nums = vol.bitmap.find_n_free(num)
        if blk_nums == None:
          print("No %d free blocks found" % num)
          return 100
        else:
          print("Free %d blocks:" % num, blk_nums)
          return 0
      else:
        blk_num = vol.bitmap.find_free()
        if blk_num == None:
          print("No free block found")
          return 100
        else:
          print("Free block:", blk_num)
          return 0
    elif cmd == 'all':
      bm = vol.bitmap.create_draw_bitmap()
      vol.bitmap.draw_on_bitmap(bm)
      vol.root_dir.draw_on_bitmap(bm, True)
      vol.bitmap.print_draw_bitmap(bm, brief)
      return 0
    elif cmd == 'maps':
      bm = vol.bitmap.create_draw_bitmap()
      vol.bitmap.draw_on_bitmap(bm)
      vol.bitmap.print_draw_bitmap(bm, brief)
      return 0
    elif cmd == 'root':
      show_entries = 'entries' in self.opts
      bm = vol.bitmap.create_draw_bitmap()
      vol.root_dir.draw_on_bitmap(bm, False, show_entries)
      vol.bitmap.print_draw_bitmap(bm, brief)
      return 0
    elif cmd == 'node':
      if n > 1:
        name = make_fsstr(self.opts[1])
        node = vol.get_path_name(name)
        if node != None:
          show_all = 'all' in self.opts
          show_entries = 'entries' in self.opts
          bm = vol.bitmap.create_draw_bitmap()
          node.draw_on_bitmap(bm, show_all, show_entries)
          vol.bitmap.print_draw_bitmap(bm, brief)
          return 0
        else:
          print("Node '%s' not found!" % self.opts[1])
          return 2
      else:
        print("Need node path!")
        return 1
    else:
      print("Unknown bitmap command!")
      return 1

# ----- Root Tools -----

class RootCmd(Command):
  def handle_vol(self, volume):
    n = len(self.opts)
    if n == 0:
      print("Usage: root ( show | create_time <time> | disk_time <time> | time <time> )")
      return 1
    cmd = self.opts[0]
    # root show
    if cmd == 'show':
      volume.root.dump()
      return 0
    # create_time <time>
    elif cmd == 'create_time':
      if n != 2:
        print("create_time <time>")
        return 1
      else:
        volume.change_create_ts_by_string(self.opts[1])
        return 0
    # disk_time <time>
    elif cmd == 'disk_time':
      if n != 2:
        print("disk_time <time>")
        return 1
      else:
        volume.change_disk_ts_by_string(self.opts[1])
        return 0
    # time <time>
    elif cmd == 'time':
      if n != 2:
        print("time <time>")
        return 1
      else:
        volume.change_mod_ts_by_string(self.opts[1])
        return 0
    # boot ?
    else:
      print("Unknown root command!")
      return 1

# ----- Boot Tools -----

class BootCmd(Command):
  def handle_blkdev(self, blkdev):
    n = len(self.opts)
    if n == 0:
      print("Usage: boot ( show [hex] [asm] | read <file> | write <file> | install [boot1x] | clear )")
      return 1
    cmd = self.opts[0]
    # fetch boot blcok
    bb = BootBlock(blkdev, 0)
    bb.read()
    # boot show [hex] [asm]
    if cmd == 'show':
      bb.dump()
      if bb.valid and bb.boot_code != None:
        if 'hex' in self.opts:
          print_hex(bb.boot_code)
        if 'asm' in self.opts:
          dis = DisAsm()
          code = dis.disassemble(bb.boot_code)
          dis.dump(code)
      return 0
    # boot read <file>
    elif cmd == 'read':
      if n > 1:
        if bb.valid:
          if bb.boot_code != None:
            f = open(self.opts[1], "wb")
            f.write(bb.boot_code)
            f.close()
            return 0
          else:
            print("No Boot Code found!")
            return 2
        else:
          print("Invalid Boot Block!")
          return 1
      else:
        print("No file name!")
        return 1
    # boot write <file>
    elif cmd == 'write':
      if n > 1:
        f = open(self.opts[1], "rb")
        data = f.read()
        f.close()
        ok = bb.set_boot_code(data)
        if ok:
          bb.write()
          return 0
        else:
          print("Boot Code invalid!")
          return 2
      else:
        print("No file name!")
        return 1
    # boot install [<name>]
    elif cmd == 'install':
      if n == 1: # default boot code
        name = "boot2x3x"
      else:
        name = self.opts[1]
      # boot code directory
      bc_dir = bb.get_boot_code_dir()
      if bc_dir == None:
        print("No boot code directory found!")
        return 1
      path = os.path.join(bc_dir, name + ".bin")
      if not os.path.exists:
        print("Boot code '%s' not found!" % path)
        return 1
      # read data
      f = open(path,"rb")
      data = f.read()
      f.close()
      ok = bb.set_boot_code(data)
      if ok:
        bb.write()
        return 0
      else:
        print("Boot Code invalid!")
        return 2
    # boot clear
    elif cmd == 'clear':
      bb.set_boot_code(None)
      bb.write()
      return 0
    # boot ?
    else:
      print("Unknown boot command!")
      return 1

# ----- BlkDev Command -----

class BlkDevCmd(Command):
  def handle_blkdev(self, blkdev):
    blkdev.dump()
    return 0

# ----- main -----
def main():
  # call scanner and process all files with selected command
  cmd_map = {
  "open" : OpenCmd,
  "create" : CreateCmd,
  "list" : ListCmd,
  "type" : TypeCmd,
  "read" : ReadCmd,
  "makedir" : MakeDirCmd,
  "write" : WriteCmd,
  "delete" : DeleteCmd,
  "format" : FormatCmd,
  "bitmap" : BitmapCmd,
  "blkdev" : BlkDevCmd,
  "protect" : ProtectCmd,
  "comment" : CommentCmd,
  "time" : TimeCmd,
  "block" : BlockCmd,
  "pack" : PackCmd,
  "unpack" : UnpackCmd,
  "repack" : RepackCmd,
  "boot" : BootCmd,
  "root" : RootCmd,
  "info" : InfoCmd,
  "relabel" : RelabelCmd
  }

  parser = argparse.ArgumentParser()
  parser.add_argument('image_file')
  parser.add_argument('command_list', nargs='+', help="command: "+",".join(cmd_map.keys()))
  parser.add_argument('-v', '--verbose', action='store_true', default=False, help="be more verbos")
  parser.add_argument('-s', '--seperator', default='+', help="set the command separator char sequence")
  parser.add_argument('-r', '--read-only', action='store_true', default=False, help="read-only operation")
  parser.add_argument('-f', '--force', action='store_true', default=False, help="force overwrite existing image")
  args = parser.parse_args()

  cmd_list = args.command_list
  sep = args.seperator
  queue = FSCommandQueue(args, cmd_list, sep, cmd_map)
  code = queue.run()
  return code


if __name__ == '__main__':
  sys.exit(main())
