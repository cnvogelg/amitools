from __future__ import print_function

from amitools.vamos.lib.lexec.ExecStruct import *
from amitools.vamos.lib.dos.CSource import CSource
from amitools.vamos.lib.dos.Item import ItemParser

def item_parser1_test():
  csrc = CSource('hello world\n')
  ip = ItemParser(csrc)
  maxbuf = 256
  assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "hello")
  assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "world")
  assert ip.read_item(maxbuf) == (ItemParser.ITEM_NOTHING, None)

def item_parser2_test():
  csrc = CSource('"hello space" "world*n"\n')
  ip = ItemParser(csrc)
  maxbuf = 256
  assert ip.read_item(maxbuf) == (ItemParser.ITEM_QUOTED, "hello space")
  assert ip.read_item(maxbuf) == (ItemParser.ITEM_QUOTED, "world\n")
  assert ip.read_item(maxbuf) == (ItemParser.ITEM_NOTHING, None)

def check_item_eol(in_str, itype, item, eol):
  csrc = CSource(in_str + '\n')
  ip = ItemParser(csrc)
  maxbuf = 256
  assert ip.read_item(maxbuf) == (itype, item)
  assert ip.read_eol() == eol
  assert ip.read_item(maxbuf) == (ItemParser.ITEM_NOTHING, None)

def item_parser3_test():
  check_item_eol('a', ItemParser.ITEM_UNQUOTED, 'a', '')
  check_item_eol('a  b', ItemParser.ITEM_UNQUOTED, 'a', '  b')
  check_item_eol('a  b  ', ItemParser.ITEM_UNQUOTED, 'a', '  b')
  check_item_eol('"a"  b', ItemParser.ITEM_QUOTED, 'a', '  b')
  check_item_eol('"a"  b  ', ItemParser.ITEM_QUOTED, 'a', '  b  ')
