import re
import collections
from .typebase import TypeBase


class APTR_SELF:
    """Helper Type to identify pointer to structures of my type"""

    pass


class BPTR_SELF:
    """Helper Type to identify pointer to structures of my type"""

    pass


class AmigaStructPool:
    def __init__(self):
        self._pool = {}

    def add_struct(self, cls):
        assert issubclass(cls, AmigaStruct)
        type_name = cls.sdef.get_type_name()
        if not type_name in self._pool:
            self._pool[type_name] = cls

    def find_struct(self, name):
        if name in self._pool:
            return self._pool[name]

    def get_all_structs(self):
        return list(self._pool.values())

    def get_all_struct_names(self):
        return list(self._pool.keys())


# collect all types
AmigaStructTypes = AmigaStructPool()


FieldDefBase = collections.namedtuple(
    "FieldDefBase", ["index", "offset", "type", "name", "size", "struct"]
)


class FieldDef(FieldDefBase):

    _base_offset = 0
    _parent_def = None

    def copy(self):
        return FieldDef(
            self.index, self.offset, self.type, self.name, self.size, self.struct
        )

    def get_base_offset(self):
        return self._base_offset + self.offset

    def get_parent_def(self):
        return self._parent_def

    def get_def_path(self):
        # build array of all parent defs (if any)
        field_def = self
        result = [field_def]
        while True:
            field_def = field_def.get_parent_def()
            if not field_def:
                break
            result.insert(0, field_def)
        return result

    def get_sub_field_by_name(self, name):
        # only works for astructs
        if issubclass(self.type, AmigaStruct):
            sub_field = getattr(self.type.sdef, name)
            return sub_field

    def __getattr__(self, name):
        """allow to access the field def of a sub astruct by name directly"""
        # special names
        if name == "base_offset":
            return self.get_base_offset()
        elif name == "parent_def":
            return self._parent_def
        # search sub field
        sub_field = self.get_sub_field_by_name(name)
        if sub_field:
            # clone field def and adjust base offset
            new_field = sub_field.copy()
            new_field._base_offset = self._base_offset + self.offset
            new_field._parent_def = self
            return new_field
        else:
            raise AttributeError(name)


class AmigaStructFieldDefs:
    def __init__(self, type_name):
        self._type_name = type_name
        self._field_defs = []
        self._name_to_field_def = {}
        self._total_size = 0
        self._alias_names = {}
        self._alias_type = None

    def get_num_field_defs(self):
        return len(self._field_defs)

    def get_total_size(self):
        return self._total_size

    def get_alias_type(self):
        return self._alias_type

    def add_field_def(self, field_def):
        field_name = field_def.name
        self._field_defs.append(field_def)
        self._name_to_field_def[field_name] = field_def
        self._total_size += field_def.size
        # find alias name
        alias_name = self._to_alias_name(field_def.name)
        if alias_name != field_name:
            self._alias_names[alias_name] = field_name

    def get_type_name(self):
        return self._type_name

    def get_field_defs(self):
        return self._field_defs

    def get_field_def(self, idx):
        return self._field_defs[idx]

    def __getitem__(self, key):
        return self._field_defs[key]

    def find_field_def_by_name(self, name):
        fdef = self._name_to_field_def.get(name)
        if not fdef:
            # try alias
            name = self._alias_names.get(name)
            if name:
                fdef = self._name_to_field_def.get(name)
        return fdef

    def __getattr__(self, name):
        fdef = self.find_field_def_by_name(name)
        if fdef:
            return fdef
        raise AttributeError("Invalid key '{}'".format(name))

    def find_field_def_by_offset(self, offset):
        """return field_def, delta that matches offset, otherwise None, 0"""
        for f in self._field_defs:
            end = f.offset + f.size
            if offset >= f.offset and offset < end:
                delta = offset - f.offset
                return f, delta
        return None, 0

    def find_sub_field_defs_by_offset(self, base_offset):
        """return array with field_def leading to embedded struct field at offset

        return [field_defs], delta or None, 0
        """
        field_defs = []
        cur_cls = self
        offset = base_offset
        while True:
            field_def, delta = cur_cls.find_field_def_by_offset(offset)
            if not field_def:
                return None, 0
            field_defs.append(field_def)
            # is it an embedded struct?
            if not issubclass(field_def.type, AmigaStruct):
                break
            # new search
            offset -= field_def.offset
            cur_cls = field_def.type.sdef
        return field_defs, delta

    def find_sub_field_defs_by_name(self, *names):
        """return array with field_defs or None"""
        if not names:
            return None
        field_defs = []
        cur_cls = self
        for name in names:
            if not cur_cls:
                return None
            field_def = cur_cls.find_field_def_by_name(name)
            if not field_def:
                return None
            field_defs.append(field_def)
            # next sub class
            if issubclass(field_def.type, AmigaStruct):
                cur_cls = field_def.type.sdef
        return field_defs

    def get_alias_name(self, name):
        return self._alias_names.get(name)

    def _to_alias_name(self, name):
        """convert camel case names to underscore and remove prefix"""
        # strip leading prefix
        pos = name.find("_")
        if pos > 0:
            name = name[pos + 1 :]
        # to underscore
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class AmigaStructFields:
    def __init__(self, astruct):
        self.astruct = astruct
        self.sdef = astruct.sdef
        self._fields = []
        self._name_to_field = {}
        for field_def in self.sdef.get_field_defs():
            field = self._create_field_type(field_def)
            self._fields.append(field)
            self._name_to_field[field_def.name] = field

    def get_fields(self):
        """return all field instances"""
        return self._fields

    def get_field_by_index(self, index):
        """return the type instance associated with the field"""
        return self._fields[index]

    def get_field_by_name(self, name):
        return self._name_to_field.get(name)

    def get_field_by_name_or_alias(self, name, subfield_aliases=None):
        field = self._name_to_field.get(name)
        if field is None:
            # alias name
            alias_name = self.sdef.get_alias_name(name)
            if alias_name:
                field = self._name_to_field.get(alias_name)
            # subfield alias
            if field is None and subfield_aliases:
                field_def_path = subfield_aliases.get(name)
                if field_def_path:
                    return self.find_sub_field_by_def_path(field_def_path)
        return field

    def find_field_by_offset(self, offset):
        """return field, delta or None, 0"""
        field_def, delta = self.sdef.find_field_def_by_offset(offset)
        if not field_def:
            return None, 0
        return self._fields[field_def.index], delta

    def find_sub_fields_by_offset(self, base_offset):
        """return [fields], delta or None, 0"""
        cur_self = self
        offset = base_offset
        fields = []
        while True:
            field, delta = cur_self.find_field_by_offset(offset)
            if not field:
                return None, 0
            fields.append(field)
            # is a struct?
            if not isinstance(field, AmigaStruct):
                break
            # next sub struct
            cur_self = field.sfields
            offset -= field.get_offset()
        return fields, delta

    def find_sub_field_by_def(self, field_def):
        """return field associated with the field_def"""
        def_path = field_def.get_def_path()
        return self.find_sub_field_by_def_path(def_path)

    def find_sub_field_by_def_path(self, def_path):
        """return field or None"""
        field = None
        astruct = self.astruct
        for field_def in def_path:
            idx = field_def.index
            assert isinstance(astruct, field_def.struct)
            assert field_def == astruct.sdef.get_field_def(idx)
            field = astruct.sfields.get_field_by_index(idx)
            if not isinstance(field, AmigaStruct):
                break
            # next
            astruct = field
        return field

    def find_field_def_by_addr(self, addr):
        """return field, delta or None, 0"""
        offset = addr - self.astruct._addr
        return self.sdef.find_field_def_by_offset(offset)

    def find_field_by_addr(self, addr):
        """return field, delta or None, 0"""
        offset = addr - self.astruct._addr
        return self.find_field_by_offset(offset)

    def find_sub_fields_by_addr(self, addr):
        """return [fields], delta or None, 0"""
        offset = addr - self.astruct._addr
        return self.find_sub_fields_by_offset(offset)

    def _create_field_type(self, field_def):
        astruct = self.astruct
        addr = astruct._addr + field_def.offset
        base_offset = astruct._base_offset + field_def.offset
        cls_type = field_def.type.get_alias_type()
        field = cls_type(
            astruct._mem, addr, offset=field_def.offset, base_offset=base_offset
        )
        return field


class AmigaStruct(TypeBase):

    # overwrite in derived class!
    _format = None
    # top-level alias names for subfields
    _subfield_aliases = None
    _sfdp = None
    # the structure definition is filled in by the decorator
    sdef = None

    @classmethod
    def get_signature(cls):
        return cls.sdef.get_type_name()

    @classmethod
    def get_alias_type(cls):
        alias_type = cls.sdef._alias_type
        if alias_type:
            return alias_type
        return cls

    @classmethod
    def _alloc(cls, alloc, tag, **kwargs):
        if tag is None:
            tag = cls.get_signature()
        return alloc.alloc_struct(cls, label=tag)

    @classmethod
    def _free(cls, alloc, mem_obj):
        alloc.free_struct(mem_obj)

    # ----- instance -----

    def __init__(self, mem, addr, **kwargs):
        super(AmigaStruct, self).__init__(mem, addr, **kwargs)
        # create field instances
        self.sfields = AmigaStructFields(self)
        # refs to be freed automatically
        self._free_refs = []
        # setup fields (if any)
        self.setup(kwargs, self._alloc, self._free_refs)

    def setup(self, setup_dict, alloc=None, free_refs=None):
        """setup the fields of the struct"""
        assert type(setup_dict) is dict
        all_refs = []
        for key, val in setup_dict.items():
            field = self.sfields.get_field_by_name_or_alias(key, self._sfdp)
            if field:
                field.setup(val, alloc, free_refs)

    def free(self):
        for free_ref in self._free_refs:
            free_ref.free_ref()
        super().free()

    def __str__(self):
        return "[AStruct:%s,@%06x+%06x]" % (
            self.sdef.get_type_name(),
            self._addr,
            self._byte_size,
        )

    def get(self, field_name):
        """return field instance by name"""
        return self.sfields.get_field_by_name_or_alias(field_name, self._sfdp)

    def __getattr__(self, field_name):
        field = self.get(field_name)
        if field is not None:
            return field
        return super().__getattr__(field_name)

    def __setattr__(self, field_name, val):
        if field_name[0] != "_" and field_name != "sfields":
            # check for field name and forbid access
            field = self.get(field_name)
            if field is not None:
                raise AttributeError(
                    "Field {} is read-only in {}".format(field_name, self)
                )
        super().__setattr__(field_name, val)
