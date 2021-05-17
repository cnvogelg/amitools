from .astruct import AmigaStruct
from .pointer import BCPLPointerType


class AccessStruct(object):

    _size_to_width = [None, 0, 1, None, 2]

    def __init__(self, mem, struct_def, struct_addr):
        self.mem = mem
        self.struct = struct_def(mem, struct_addr)

    def w_s(self, name, val):
        field, field_def = self._get_field_for_name(name)
        # BPTR auto conversion
        if issubclass(field_def.type, BCPLPointerType):
            field.set_ref_addr(val)
        else:
            field.set(val)

    def r_s(self, name):
        field, field_def = self._get_field_for_name(name)
        # BPTR auto conversion
        if issubclass(field_def.type, BCPLPointerType):
            val = field.get_ref_addr()
        else:
            val = field.get()
        return val

    def s_get_addr(self, name):
        field, _ = self._get_field_for_name(name)
        return field.get_addr()

    def get_size(self):
        return self.struct.get_byte_size()

    def _get_field_for_name(self, name):
        struct = self.struct
        field_def = None
        field = None
        # walk along fields in name "bla.foo.bar"
        for field_name in name.split("."):
            assert struct is not None
            field_def = struct.sdef.find_field_def_by_name(field_name)
            if not field_def:
                raise KeyError(self, name)
            field = struct.sfields.get_field_by_index(field_def.index)
            # find potential next struct
            if isinstance(field, AmigaStruct):
                struct = field
            else:
                struct = None
        return field, field_def
