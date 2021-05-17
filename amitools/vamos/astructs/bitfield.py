import inspect
from .scalar import ScalarType


class BitField:
    _name_to_val = None  # will be filled by decorator
    _val_to_name = None  # will be filled by decorator
    _names = None  # will be filled by decorator

    @classmethod
    def to_strs(cls, val, check=True):
        res = []
        for name in cls._names:
            bf_val = cls._name_to_val[name]
            if bf_val & val == bf_val:
                res.append(name)
                val &= ~bf_val
        if val != 0:
            if check:
                raise ValueError("invalid bits set: %x" % val)
            else:
                res.append(str(val))
        return res

    @classmethod
    def to_str(cls, val, check=True):
        return "|".join(cls.to_strs(val, check))

    @classmethod
    def from_strs(cls, *args):
        val = 0
        for name in args:
            if name in cls._name_to_val:
                bf_val = cls._name_to_val[name]
                val |= bf_val
            else:
                raise ValueError("invalid bit mask name: " + name)
        return val

    @classmethod
    def from_str(cls, val):
        return cls.from_strs(*val.split("|"))

    @classmethod
    def _get_bit_mask(cls, val):
        if type(val) is str:
            if val in cls._name_to_val:
                return cls._name_to_val[val]
            elif "|" in val:
                res = 0
                for v in val.split("|"):
                    res |= cls._name_to_val[v]
                return res
            else:
                raise ValueError("invalid bit mask name: " + val)
        else:
            return val

    @classmethod
    def is_set(cls, what, val):
        bmask = cls._get_bit_mask(what)
        return val & bmask == bmask

    @classmethod
    def is_clr(cls, what, val):
        bmask = cls._get_bit_mask(what)
        return val & bmask == 0

    def __str__(self):
        return self.to_str(self.get(), False)

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__, str(self))

    def has_bits(self, what):
        bmask = self._get_bit_mask(what)
        return self.get() & bmask == bmask

    def set_bits(self, what):
        bmask = self._get_bit_mask(what)
        super().set(self.get() | bmask)

    def clr_bits(self, what):
        bmask = self._get_bit_mask(what)
        super().set(self.get() & ~bmask)

    def set(self, val):
        bmask = self._get_bit_mask(val)
        super().set(bmask)


def BitFieldType(cls):
    """a class decorator that generates a bit field class"""

    assert issubclass(cls, BitField)
    assert issubclass(cls, ScalarType)
    assert not cls._signed

    # collect public integer vals
    _name_to_val = {}
    _val_to_name = {}
    _names = []
    mem = inspect.getmembers(cls)
    for name, val in mem:
        if type(val) is int and name[0] != "_":
            # check that val is really a bit mask
            if val & (val - 1) != 0:
                raise ValueError("no bit mask in bit field: " % name)
            _name_to_val[name] = val
            _val_to_name[val] = name
            _names.append(name)
    cls._name_to_val = _name_to_val
    cls._val_to_name = _val_to_name
    cls._names = _names

    return cls
