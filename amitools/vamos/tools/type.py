
import sys

from .tool import Tool
from amitools.vamos.astructs import AmigaStruct
from amitools.vamos.cfgcore import parse_scalar


class TypeTool(Tool):
  def __init__(self):
    Tool.__init__(self, "type", "inspect internal vamos types")

  def add_args(self, arg_parser):
    sub = arg_parser.add_subparsers(dest='type_cmd')
    # list
    parser = sub.add_parser('list',
                            help='list all types')
    # query
    parser = sub.add_parser('dump',
                            help='dump a single type')
    parser.add_argument('type_name',
                        help="name of type")
    # lookup
    parser = sub.add_parser('lookup',
                            help='lookup field in type')
    parser.add_argument('type_name',
                        help="name of type")
    parser.add_argument('type_field_path',
                        help="field_path, e.g. foo.bar")
    # offset
    parser = sub.add_parser('offset',
                            help='find field by offset')
    parser.add_argument('type_name',
                        help="name of type")
    parser.add_argument('type_offset',
                        help='offset of field')

  def run(self, args):
    type_cmd = args.type_cmd
    # list
    if type_cmd == 'list':
      type_names = AmigaStruct.get_all_struct_names()
      for tn in sorted(type_names):
        print(tn)
      return 0
    # dump
    elif type_cmd == 'dump':
      name = args.type_name
      s = AmigaStruct.find_struct(name)
      if s is None:
        print("type '%s' not found!" % name, file=sys.stderr)
        return 1
      else:
        s.dump_type()
        return 0
    # lookup
    elif type_cmd == 'lookup':
      name = args.type_name
      s = AmigaStruct.find_struct(name)
      if s is None:
        print("type '%s' not found!" % name, file=sys.stderr)
        return 1
      else:
        field_path = args.type_field_path
        try:
          fields = s.get_fields_by_path(field_path)
          return self._dump_fields(field_path, fields)
        except KeyError as e:
          print("Field not found:", e, file=sys.stderr)
          return 1
    # offset
    elif type_cmd == 'offset':
      name = args.type_name
      s = AmigaStruct.find_struct(name)
      if s is None:
        print("type '%s' not found!" % name, file=sys.stderr)
        return 1
      else:
        offset = parse_scalar(int, args.type_offset)
        fields = s.get_fields_by_offset(offset)
        return self._dump_fields("@%04x" % offset, fields)

  def _dump_fields(self, where, fields):
    if len(fields) == 0:
      print("no fields found: %s" % where, file=sys.stderr)
      return 1
    else:
      off = 0
      for f in fields:
        total = off + f.offset
        print("@%04x +%04x = %04x (size=%04x)  %s" %
              (off, f.offset, total, f.size, f.name))
        off += f.offset
      return 0
