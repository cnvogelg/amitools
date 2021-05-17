import inspect
from .scalar import ScalarType


class Enum:
    _name_to_val = None  # will be set by decorator
    _val_to_name = None  # will be set by decorator
    _names = None
    _values = None

    @classmethod
    def to_str(cls, val, check=True):
        if val in cls._val_to_name:
            return cls._val_to_name[val]
        if check:
            raise ValueError("%s is an unknown Enum value" % val)
        else:
            return str(val)

    @classmethod
    def from_str(cls, name):
        if name in cls._name_to_val:
            return cls._name_to_val[name]
        raise ValueError("'%s' is an unknown Enum string" % name)

    def __str__(self):
        return self.to_str(self.get(), False)

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__, str(self))

    def set(self, val):
        # allow to set values
        if val in self._values:
            super().set(val)
        # or names
        elif val in self._names:
            super().set(self.from_str(val))
        else:
            raise ValueError("Invalid enum value: " + val)


def EnumType(cls):
    """a class decorator that generates an enum class"""

    assert issubclass(cls, Enum)
    assert issubclass(cls, ScalarType)
    assert not cls._signed

    # collect integer vals
    _name_to_val = {}
    _val_to_name = {}
    _names = []
    _values = []
    mem = inspect.getmembers(cls)
    for name, val in mem:
        if type(val) is int and name[0] != "_":
            _name_to_val[name] = val
            _val_to_name[val] = name
            _names.append(name)
            _values.append(val)

    cls._name_to_val = _name_to_val
    cls._val_to_name = _val_to_name
    cls._names = _names
    cls._values = _values

    return cls
