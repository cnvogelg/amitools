from .astruct import AmigaStruct
from .pointer import BCPLPointerType


class AccessStruct(object):
    _size_to_width = [None, 0, 1, None, 2]
    _field_path_cache = {}

    def __init__(self, mem, struct_def, struct_addr):
        self.mem = mem
        self._struct_def = struct_def
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

    @classmethod
    def _get_cached_field_path(cls, struct_def, name):
        cache = cls._field_path_cache.setdefault(struct_def, {})
        path = cache.get(name)
        if path is not None:
            return path
        sdef = struct_def.sdef
        idx_path = []
        field_def = None
        for field_name in name.split("."):
            field_def = sdef.find_field_def_by_name(field_name)
            if not field_def:
                raise KeyError(struct_def, name)
            idx_path.append(field_def.index)
            field_type = field_def.type.get_alias_type()
            if issubclass(field_type, AmigaStruct):
                sdef = field_type.sdef
            else:
                sdef = None
        path = (tuple(idx_path), field_def)
        cache[name] = path
        return path

    def _get_field_for_name(self, name):
        struct = self.struct
        field = None
        idx_path, field_def = self._get_cached_field_path(self._struct_def, name)
        for idx in idx_path:
            assert struct is not None
            field = struct.sfields.get_field_by_index(idx)
            if isinstance(field, AmigaStruct):
                struct = field
            else:
                struct = None
        return field, field_def
