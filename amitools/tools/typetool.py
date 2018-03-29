#!/usr/bin/env python2.7
#
# vamos [optoins] <amiga binary> [args ...]
#
# run an m68k AmigaOS binary
#
# written by Christian Vogelgsang (chris@vogelgsang.org)

import sys

from amitools.vamos.astructs import *

# --- args ---
def main():
  argc = len(sys.argv)
  if argc == 1:
    print """
  Usage:
    typetool <typename>                          # Dump given type
    typetool <typename> <element.path>           # Lookup offset of given element
    typetool <typename> <offset> <byte_width>    # Lookup element at given offset
  """
    return 1

  type_name = sys.argv[1]

  # --- find type ---
  if not AmigaStruct.struct_pool.has_key(type_name):
    print "Can't find type: %s" % type_name
    return 1
  type_def = AmigaStruct.struct_pool[type_name]

  if argc == 2:
    type_def.dump()
  elif argc == 3:
    name = sys.argv[2]
    res = type_def.get_offset_for_name(name)
    print "name=%s -> offset=%d width=%s convert=%s" % (name,res[0],res[1],res[2])
  elif argc == 4:
    offset = int(sys.argv[2])
    width = int(sys.argv[3])
    res = type_def.get_name_for_offset(offset,width)
    print "offset=%d widht=%d -> name=%s delta=%d type_name=%s" % (offset,width,res[0],res[1],res[2])
  return 0


if __name__ == '__main__':
  sys.exit(main())
