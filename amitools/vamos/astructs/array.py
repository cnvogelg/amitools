from .typebase import TypeBase


class ArrayType(TypeBase):
    _element_type = None
    _array_size = None
    _element_byte_size = None

    @classmethod
    def get_element_type(cls):
        return cls._element_type

    @classmethod
    def get_array_size(cls):
        return cls._array_size

    @classmethod
    def get_signature(cls):
        return "{}[{}]".format(cls._element_type.get_signature(), cls._array_size)

    def __init__(self, mem, addr, **kwargs):
        super(ArrayType, self).__init__(mem, addr, **kwargs)

    def get(self, index):
        """Return n-th element in array"""
        entry_addr = self._get_entry_addr(index)
        cls_type = self._element_type.get_alias_type()
        return cls_type(self._mem, entry_addr)

    def _get_entry_addr(self, index):
        assert index >= 0 and index < self._array_size
        return self.get_addr() + index * self._element_byte_size

    def __getitem__(self, key):
        return self.get(key)


class ArrayIter:
    def __init__(self, array):
        self._array = array
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        a = self._array
        if self._index == a.get_array_size():
            raise StopIteration
        entry = a.get(self._index)
        self._index += 1
        return entry


ARRAYTypes = {}


def ARRAY(element_type, array_size):
    """create a new array type class the references the given type"""
    name = "ARRAY[" + str(array_size) + "]_" + element_type.__name__
    if name in ARRAYTypes:
        return ARRAYTypes[name]
    else:
        element_byte_size = element_type.get_byte_size()
        byte_size = element_byte_size * array_size
        new_type = type(
            name,
            (ArrayType,),
            dict(
                _element_type=element_type,
                _array_size=array_size,
                _element_byte_size=element_byte_size,
                _byte_size=byte_size,
            ),
        )
        ARRAYTypes[name] = new_type
        return new_type
