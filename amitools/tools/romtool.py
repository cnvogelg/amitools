#!/usr/bin/env python2.7
# romtool
#
# work with Amiga ROM files aka Kickstarts

from __future__ import print_function

import sys
import argparse
import os.path
import logging

from amitools.util.Logging import *
from amitools.util.DataDir import *
from amitools.rom.KickRom import *
from amitools.rom.RemusFile import *


desc="""romtool allows you to dissect, inspect, or create Amiga ROM files"""


def load_rom(rom_image, rom_key_file):
  logging.info("loading ROM image from '%s'", rom_image)
  try:
    return KickRomLoader.load(rom_image, rom_key_file)
  except IOError as e:
    logging.error("Error loading ROM image '%s': %s", rom_image, e)
    return None


def show_remus_rom(rom):
  print("@%08x  +%08x  sum=%08x  off=%08x  %s" % \
        (rom.base_addr, rom.size, rom.chk_sum, rom.sum_off, rom.name))
  print()
  for e in rom.entries:
    print("@%08x  +%08x  relocs=#%5d  %s" % \
          (e.offset, e.size, len(e.relocs), e.name))


def load_remus_file_set():
  remus_set = RemusFileSet()
  try:
    data_dir = ensure_data_sub_dir("splitdata")
    remus_set.load(data_dir)
    return remus_set
  except IOError as e:
    logging.error("Error loading Remus file set: %s", e)
    return None


def do_query_cmd(args):
  # first load ROM
  rom_img = load_rom(args.rom_image, args.rom_key)
  if rom_img is None:
    return 1
  logging.debug("got ROM: %r", rom_img)
  # load Remus split data
  remus_file_set = load_remus_file_set()
  if remus_file_set is None:
    return 2
  # find ROM
  rom = remus_file_set.find_rom(rom_img)
  if rom is not None:
    show_remus_rom(rom)
    return 0
  else:
    print("ROM not found in split data.")
    return 100


def do_split_cmd(args):
  # first load ROM
  rom_img = load_rom(args.rom_image, args.rom_key)
  if rom_img is None:
    return 1
  logging.debug("got ROM: %r", rom_img)
  # load Remus split data
  remus_file_set = load_remus_file_set()
  if remus_file_set is None:
    return 2
  return 0


def setup_query_parser(parser):
  parser.add_argument('rom_image', help='rom image file to be split')
  parser.set_defaults(cmd=do_query_cmd)


def setup_split_parser(parser):
  parser.add_argument('rom_image', help='rom image file to be split')
  parser.add_argument('output_dir', help='store modules in this base dir', nargs='?')
  parser.set_defaults(cmd=do_split_cmd)


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
  # query
  query_parser = sub_parsers.add_parser('query', help='query if ROM is in split data')
  setup_query_parser(query_parser)
  # split
  split_parser = sub_parsers.add_parser('split', help='split a ROM into modules')
  setup_split_parser(split_parser)

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
  return args.cmd(args)


# ----- entry point -----
if __name__ == '__main__':
  sys.exit(main())
