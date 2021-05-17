from .astruct import AmigaStruct


class TypeDumper:
    def __init__(self, print_func=print):
        self._print_func = print_func

    def _reset(self, base_addr=0):
        self._indent = 0
        self._num = 0
        self._base_addr = 0
        self._offset = 0

    def dump(self, type_cls, base_addr=0):
        self._reset(base_addr)
        if issubclass(type_cls, AmigaStruct):
            self._dump_struct(type_cls)
        else:
            self._print_type_line(type_cls.__name__)

    def dump_fields(self, *field_defs, base_addr=0):
        self._reset(base_addr)
        # first print enclosing structure
        field_def = field_defs[0]
        struct = field_def.struct
        self._print_begin_struct(struct.sdef.get_type_name())
        self._indent += 1
        self._dump_fields(field_defs, 0)
        self._indent -= 1
        self._print_end_struct(struct.get_byte_size())

    def _dump_fields(self, field_defs, pos):
        field_def = field_defs[pos]
        field_type = field_def.type
        struct = field_def.struct
        self._offset += field_def.offset
        self._base_addr += field_def.offset
        if issubclass(field_type, AmigaStruct):
            self._print_begin_struct(field_type.sdef.get_type_name(), field_def.name)
            if pos < len(field_defs) - 1:
                self._indent += 1
                self._dump_fields(field_defs, pos + 1)
                self._indent -= 1
            self._print_end_struct(struct.get_byte_size())
        else:
            self._print_field(field_def)

    def _dump_struct(self, type_cls, struct_field_def=None):
        type_name = type_cls.sdef.get_type_name()
        byte_size = type_cls.get_byte_size()
        field_name = struct_field_def.name if struct_field_def else None
        self._print_begin_struct(type_name, field_name)
        self._indent += 1

        for field_def in type_cls.sdef.get_field_defs():
            field_type = field_def.type
            if issubclass(field_type, AmigaStruct):
                self._dump_struct(field_type, field_def)
            else:
                self._print_field(field_def)
                self._num += 1
                self._offset += field_def.size
                self._base_addr += field_def.size

        self._indent -= 1
        self._print_end_struct(byte_size)

    def _get_prefix(self, extra=None):
        istr = " " * self._indent
        if not extra:
            extra = " " * 5
        return "     @%04d %s %s" % (self._base_addr, extra, istr)

    def _print_type_line(self, type_name):
        self._print_func("%s  %s" % (self._get_prefix(), type_name))

    def _print_begin_struct(self, type_name, field_name=None):
        if field_name:
            self._print_func(
                "%s  %s %s {" % (self._get_prefix(), type_name, field_name)
            )
        else:
            self._print_func("%s  %s {" % (self._get_prefix(), type_name))

    def _print_end_struct(self, total):
        extra = "=%04d" % total
        self._print_func("%s  }" % (self._get_prefix(extra)))

    def _print_field(self, field_def):
        istr = " " * self._indent
        self._print_func(
            "#%04d %04d @%04d/%04x +%04d %s  %-20s %-20s"
            % (
                field_def.index,
                self._num,
                self._offset,
                self._offset,
                field_def.type.get_byte_size(),
                istr,
                field_def.type.get_signature(),
                field_def.name,
            )
        )
