import collections
from .astruct import AmigaStruct


class InvalidAmigaTypeException(Exception):
  def __init__(self, type_name):
    self.type_name = type_name

  def __str__(self):
    return self.type_name


Field = collections.namedtuple('Field',
                               ['type_sig',
                                'name',
                                'offset',
                                'size',
                                'end',
                                'struct_type',
                                'base_type',
                                'is_pointer',
                                'index'
                                ])


class AmigaStructDecorator(object):

  def decorate(self, cls):
    name = self._validate_class(cls)
    cls._type_name = name
    # store struct pool and class
    self.cls = cls
    self.types = AmigaStruct._types
    self.struct_pool = AmigaStruct._struct_pool
    # setup field data
    self._setup_fields(cls)
    # create data class
    self._create_data_class(cls)
    # add to pool
    self.struct_pool[name] = cls
    return cls

  def _create_data_class(self, cls):
    names = cls._field_names
    data_name = cls._type_name + "Data"
    data_cls = collections.namedtuple(data_name, names)
    cls._data_class = data_cls

  def _setup_fields(self, cls):
    total_size = 0
    offset = 0
    name_to_field = {}
    index = 0
    fields = []
    names = []
    my_name = cls._type_name

    # run through fields
    for type_sig, name in self.cls._format:

      # check type signature
      pure_name = self._validate_type_signature(my_name, type_sig)

      # calc size of field
      size = self._lookup_type_size(type_sig)

      # is pointer? struct type or base type?
      is_pointer = self._is_pointer(type_sig)
      struct_type = self._get_struct_type(pure_name)
      base_type = self._get_base_type(pure_name)

      # its my type
      if pure_name == my_name:
        struct_type = cls
        if not is_pointer:
          raise RuntimeError("Can't embed myself in struct!")

      # create field
      field = Field(type_sig=type_sig, name=name,
                    offset=offset, size=size, end=offset+size,
                    struct_type=struct_type, base_type=base_type,
                    is_pointer=is_pointer, index=index)
      fields.append(field)

      # store name -> index mapping
      name_to_field[name] = field
      names.append(name)

      # add name to class directly
      field_name = name + "_field"
      if getattr(cls, field_name, None) is not None:
        raise RuntimeError("field '%s' already a member of class!" % name)
      setattr(cls, field_name, field)

      index += 1
      offset += size
      total_size += size

    # store in class
    cls._total_size = total_size
    cls._fields = fields
    cls._name_to_field = name_to_field
    cls._field_names = names
    cls._num_fields = index

  def _get_struct_type(self, pure_name):
    if self.struct_pool.has_key(pure_name):
      return self.struct_pool[pure_name]
    else:
      return None

  def _get_base_type(self, pure_name):
    if self.types.has_key(pure_name):
      return self.types[pure_name]
    else:
      return None

  def _lookup_type_size(self, full_type_name):
    # array?
    comp = full_type_name.split('|')
    type_name = comp[0]
    array_mult = 1
    for m in comp[1:]:
      array_mult *= int(m)

    # its a pointer ;)
    if self._is_pointer(type_name):
      base = 4
    # look for standard type
    elif self.types.has_key(type_name):
      base = 2 ** self.types[type_name][0]
    # look for user type
    elif self.struct_pool.has_key(type_name):
      t = self.struct_pool[type_name]
      base = t.get_size()
    else:
      raise InvalidAmigaTypeException(type_name)

    return array_mult * base

  def _is_pointer(self, name):
    return name.find('*') != -1

  def _validate_type_signature(self, my_name, type_sig):
    type_name = self._get_pure_name(type_sig)
    # its me
    if type_name == my_name:
      return type_name
    # is it an internal type?
    elif self.types.has_key(type_name):
      return type_name
    # a sub type?
    elif self.struct_pool.has_key(type_name):
      return type_name
    else:
      raise InvalidAmigaTypeException(type_name)

  def _get_pure_name(self, name):
    # remove array post fixes and pointers
    comp = name.split('|')
    type_name = comp[0].split('*')[0]
    return type_name

  def _validate_class(self, cls):
    # make sure cls is derived from AmigaStruct
    if cls.__bases__ != (AmigaStruct, ):
      raise RuntimeError("cls must dervive from AmigaStruct")
    # make sure a format is declared
    _format = getattr(cls, '_format', None)
    if _format is None:
      raise RuntimeError("cls must contain a _format")
    # ensure that class ends with Struct
    name = cls.__name__
    if not name.endswith('Struct'):
      raise RuntimeError("cls must be named *Struct")
    base_name = name[:-len('Struct')]
    return base_name


def AmigaStructDef(cls):
  """a class decorator that setups up an amiga struct class"""
  decorator = AmigaStructDecorator()
  return decorator.decorate(cls)
