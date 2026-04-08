from .astruct import (
    AmigaStruct,
    AmigaStructTypes,
    AmigaStructFieldDefs,
    _StructFieldDescriptor,
    APTR_SELF,
    BPTR_SELF,
    TypeBase,
    FieldDef,
)
from .pointer import APTR, BPTR


class AmigaStructDecorator(object):
    def __call__(self, cls):
        # check class and store base name (without Struct postfix)
        type_name = self._validate_class(cls)
        # setup struct def via format
        struct_def = self._setup_fields(cls, cls._format, type_name)
        cls.sdef = struct_def
        # any sub field aliases?
        if cls._subfield_aliases:
            self._setup_subfield_aliases(cls, cls._subfield_aliases)
        self._install_field_descriptors(cls)
        cls._byte_size = struct_def.get_total_size()
        # add to pool
        AmigaStructTypes.add_struct(cls)
        return cls

    def _setup_subfield_aliases(self, cls, aliases):
        alias_map = {}
        for alias, path in aliases.items():
            alias_path = path.split(".")
            def_path = cls.sdef.find_sub_field_defs_by_name(*alias_path)
            assert def_path
            alias_map[alias] = def_path
        cls._sfdp = alias_map

    def _install_field_descriptors(self, cls):
        field_attr_paths = {}

        for field_def in cls.sdef.get_field_defs():
            field_attr_paths.setdefault(field_def.name, (field_def.index,))

        for alias_name, field_name in cls.sdef._alias_names.items():
            field_def = cls.sdef.find_field_def_by_name(field_name)
            if field_def is not None:
                field_attr_paths.setdefault(alias_name, (field_def.index,))

        if cls._sfdp:
            for alias_name, def_path in cls._sfdp.items():
                field_attr_paths.setdefault(
                    alias_name, tuple(field_def.index for field_def in def_path)
                )

        cls._field_attr_paths = field_attr_paths

        existing_names = set()
        for base in cls.mro():
            existing_names.update(base.__dict__.keys())

        for field_name, field_path in field_attr_paths.items():
            if field_name in existing_names:
                continue
            setattr(cls, field_name, _StructFieldDescriptor(field_path))
            existing_names.add(field_name)

    def _setup_fields(self, cls, format, type_name):
        struct_def = AmigaStructFieldDefs(type_name)

        # run through fields
        for field_type, field_name in format:
            # replace self pointers
            if field_type is APTR_SELF:
                field_type = APTR(cls)
            elif field_type is BPTR_SELF:
                field_type = BPTR(cls)

            # ensure correct format
            if type(field_type) is not type or not issubclass(field_type, TypeBase):
                raise RuntimeError(
                    "invalid field: {}: {} in {}".format(
                        field_name, field_type, cls.__name__
                    )
                )

            field_size = field_type.get_byte_size()
            if field_size is None:
                raise RuntimeError(
                    "invalid field: {}: {} in {}".format(
                        field_name, field_type, cls.__name__
                    )
                )

            # create field
            index = struct_def.get_num_field_defs()
            offset = struct_def.get_total_size()
            field_def = FieldDef(
                index=index,
                offset=offset,
                type=field_type,
                name=field_name,
                size=field_size,
                struct=cls,
            )
            # add to struct
            struct_def.add_field_def(field_def)

        return struct_def

    def _validate_class(self, cls):
        # make sure cls is derived from AmigaStruct
        if cls.__bases__ != (AmigaStruct,):
            raise RuntimeError("cls must dervive from AmigaStruct")
        # make sure a format is declared
        _format = getattr(cls, "_format", None)
        if _format is None:
            raise RuntimeError("cls must contain a _format")
        # ensure that class ends with Struct
        name = cls.__name__
        if not name.endswith("Struct"):
            raise RuntimeError("cls must be named *Struct")
        base_name = name[: -len("Struct")]
        return base_name


AmigaStructDef = AmigaStructDecorator()


class AmigaClassDecorator:
    def __call__(self, cls):
        assert issubclass(cls, AmigaStruct)
        # store as derived class
        assert cls.sdef._alias_type is None
        cls.sdef._alias_type = cls
        return cls


AmigaClassDef = AmigaClassDecorator()
