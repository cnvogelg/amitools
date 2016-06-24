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
from amitools.rom.RomSplitter import *
from amitools.binfmt.hunk.BinFmtHunk import BinFmtHunk

desc="""romtool allows you to dissect, inspect, or create Amiga ROM files"""


def do_query_cmd(args):
  try:
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
  except IOError as e:
    logging.error("IO Error: %s", e)
    return 1


def do_split_cmd(args):
  try:
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
  except IOError as e:
    logging.error("IO Error: %s", e)
    return 1


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
