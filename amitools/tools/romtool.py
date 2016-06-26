#!/usr/bin/env python2.7
# romtool
#
# work with Amiga ROM files aka Kickstarts

from __future__ import print_function

import sys
import argparse
import os
import logging

from amitools.util.Logging import *
from amitools.util.HexDump import *
from amitools.rom.RomSplitter import *
from amitools.rom.RomBuilder import *
from amitools.rom.KickRom import *
from amitools.binfmt.hunk.BinFmtHunk import BinFmtHunk
from amitools.binfmt.BinFmt import BinFmt

desc="""romtool allows you to dissect, inspect, or create Amiga ROM files"""


def do_list_cmd(args):
  rs = RomSplitter()
  rs.list_roms(print, args.query, show_entries=args.entries)
  return 0


def do_query_cmd(args):
  ri = args.rom_image
  rs = RomSplitter()
  if not rs.find_rom(ri):
    print(ri, "not found in split database!")
    return 100
  else:
    rs.print_rom(print)
    if args.query is None:
      e = rs.get_all_entries()
    else:
      e = rs.query_entries(args.query)
    rs.print_entries(print,e)
    return 0


def do_split_cmd(args):
  ri = args.rom_image
  rs = RomSplitter()
  rom = rs.find_rom(ri)
  if rom is None:
    logging.error(ri, "not found in split database!")
    return 100
  else:
    rs.print_rom(logging.info)
    entries = rs.get_all_entries()
    # setup output dir
    out_path = os.path.join(args.output_dir, rom.short_name)
    # make dirs
    if not os.path.isdir(out_path):
      logging.info("creating directory '%s'", out_path)
      os.makedirs(out_path)
    # create index file
    if not args.no_index:
      idx_path = os.path.join(out_path, "index.txt")
      with open(idx_path, "w") as fh:
        logging.info("writing index to '%s'", idx_path)
        for e in entries:
          fh.write(e.name + "\n")
    # extract entries
    bfh = BinFmtHunk()
    for e in entries:
      rs.print_entry(logging.info, e)
      bin_img = rs.extract_bin_img(e)
      out_file = os.path.join(out_path, e.name)
      logging.info("writing file '%s'", out_file)
      bfh.save_image(out_file, bin_img)
    return 0


def do_build_cmd(args):
  rom_addr = int(args.rom_addr, 16)
  rb = RomBuilder(args.rom_size, rom_addr, args.fill_byte)
  # build file list
  files = []
  for mod in args.modules:
    # is an index file?
    if mod.endswith('.txt'):
      base_path = os.path.dirname(mod)
      with open(mod, "r") as fh:
        for line in fh:
          name = line.strip()
          if len(name) > 0:
            f = os.path.join(base_path, name)
            files.append(f)
    else:
      files.append(mod)
  # load modules
  bf = BinFmt()
  for f in files:
    if not bf.is_image(f):
      logging.error("Can't load module '%s'", f)
      return 2
    name = os.path.basename(f)
    off = rb.get_current_offset()
    logging.info("@%08x: loading '%s'", off, f)
    bin_img = bf.load_image(f)
    e = rb.add_bin_img(name, bin_img)
    if e is None:
      logging.error("@%08x: can't add module '%s'", off, f)
      return 3
  # build rom
  rom_data = rb.build_rom()
  # save rom
  rom_image = args.rom_image
  logging.info("saving ROM to '%s'", rom_image)
  with open(rom_image, "wb") as fh:
    fh.write(rom_data)
  return 0


def do_diff_cmd(args):
  # load ROMs
  img_a = args.image_a
  logging.info("loading ROM A from '%s'", img_a)
  rom_a = KickRom.Loader.load(img_a)
  img_b = args.image_b
  logging.info("loading ROM B from '%s'", img_b)
  rom_b = KickRom.Loader.load(img_b)
  # check sizes
  size_a = len(rom_a)
  size_b = len(rom_b)
  if not args.force and size_a != size_b:
    logging.error("ROM differ in size (%08x != %08x). Aborting", size_a, size_b)
    return 2
  # do diff
  base_addr = 0
  if args.rom_addr:
    base_addr = int(args.rom_addr, 16)
  elif args.show_address:
    kh = KickRom.Helper(rom_a)
    if kh.is_kick_rom():
      base_addr = kh.get_base_addr()
    else:
      logging.error("Not a KickROM! Can't detect base address.")
      return 3
  print_hex_diff(rom_a, rom_b, num=args.columns, show_same=args.same,
                 base_addr=base_addr)


def do_dump_cmd(args):
  img = args.image
  logging.info("loading ROM from '%s'", img)
  rom = KickRom.Loader.load(img)
  base_addr = 0
  if args.rom_addr:
    base_addr = int(args.rom_addr, 16)
  elif args.show_address:
    kh = KickRom.Helper(rom)
    if kh.is_kick_rom():
      base_addr = kh.get_base_addr()
    else:
      logging.error("Not a KickROM! Can't detect base address.")
      return 3
  print_hex(rom, num=args.columns, base_addr=base_addr)


def setup_list_parser(parser):
  parser.add_argument('query', default=None, help='query rom name', nargs='?')
  parser.add_argument('-e', '--entries', default=False, action='store_true',
                      help="show entries of ROMs")
  parser.set_defaults(cmd=do_list_cmd)


def setup_query_parser(parser):
  parser.add_argument('rom_image', help='rom image file to be split')
  parser.add_argument('query', default=None, help='query module name', nargs='?')
  parser.set_defaults(cmd=do_query_cmd)


def setup_split_parser(parser):
  parser.add_argument('rom_image', help='rom image file to be split')
  parser.add_argument('output_dir', help='store modules in this base dir')
  parser.add_argument('--no-index', default=False, action='store_true',
                      help="do not create an 'index.txt' in output path")
  parser.set_defaults(cmd=do_split_cmd)


def setup_build_parser(parser):
  parser.add_argument('rom_image', help='rom image file to be built')
  parser.add_argument('modules', default=[], action='append',
                      help='modules or index.txt files to be added')
  parser.add_argument('-s', '--rom-size', default=512, type=int,
                      help="size of ROM in KiB")
  parser.add_argument('-a', '--rom-addr', default="f80000",
                      help="base address of ROM in hex")
  parser.add_argument('--fill-byte', default=255, type=int,
                      help="fill byte for empty ranges")
  parser.set_defaults(cmd=do_build_cmd)


def setup_diff_parser(parser):
  parser.add_argument('image_a', help='rom image a')
  parser.add_argument('image_b', help='rom image b')
  parser.add_argument('-s', '--same', default=False, action='store_true',
                      help="show same lines of ROMs")
  parser.add_argument('-a', '--show-address', default=False, action='store_true',
                      help="show KickROM address (otherwise image offset)")
  parser.add_argument('-b', '--rom-addr', default=None,
                      help="use hex base address for output")
  parser.add_argument('-f', '--force', default=False, action='store_true',
                      help="diff ROMs even if size differs")
  parser.add_argument('-c', '--columns', default=8, type=int,
                      help="number of bytes shown per line")
  parser.set_defaults(cmd=do_diff_cmd)


def setup_dump_parser(parser):
  parser.add_argument('image', help='rom image to be dumped')
  parser.add_argument('-a', '--show-address', default=False, action='store_true',
                      help="show KickROM address (otherwise image offset)")
  parser.add_argument('-b', '--rom-addr', default=None,
                      help="use hex base address for output")
  parser.add_argument('-c', '--columns', default=16, type=int,
                      help="number of bytes shown per line")
  parser.set_defaults(cmd=do_dump_cmd)


def parse_args():
  """parse args and return (args, opts)"""
  parser = argparse.ArgumentParser(description=desc)

  # global options
  parser.add_argument('-k', '--rom-key', default='rom.key',
                      help='the path of a rom.key file if you want to process'
                           ' crypted ROMs')
  add_logging_options(parser)

  # sub parsers
  sub_parsers = parser.add_subparsers(help="sub commands")
  # list
  list_parser = sub_parsers.add_parser('list', help='list ROMs in split data')
  setup_list_parser(list_parser)
  # query
  query_parser = sub_parsers.add_parser('query', help='query if ROM is in split data')
  setup_query_parser(query_parser)
  # split
  split_parser = sub_parsers.add_parser('split', help='split a ROM into modules')
  setup_split_parser(split_parser)
  # build
  build_parser = sub_parsers.add_parser('build', help='build a ROM from modules')
  setup_build_parser(build_parser)
  # diff
  diff_parser = sub_parsers.add_parser('diff', help='show differences in two ROM images')
  setup_diff_parser(diff_parser)
  # dump
  dump_parser = sub_parsers.add_parser('dump', help='dump a ROM image')
  setup_dump_parser(dump_parser)

  # parse
  return parser.parse_args()


# ----- main -----
def main():
  # parse args and init logging
  args = parse_args()
  setup_logging(args)
  # say hello
  logging.info("Welcom to romtool")
  # run command
  try:
    return args.cmd(args)
  except IOError as e:
    logging.error("IO Error: %s", e)
    return 1


# ----- entry point -----
if __name__ == '__main__':
  sys.exit(main())
