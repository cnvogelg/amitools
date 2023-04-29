from .typebase import TypeBase
from .pointer import APTR, BPTR


class CStringType(TypeBase):
    def __init__(self, mem, addr, **kwargs):
        super(CStringType, self).__init__(mem, addr, **kwargs)

    def get(self):
        if self._addr == 0:
            return None
        else:
            return self._mem.r_cstr(self._addr)

    def set(self, val):
        if self._addr == 0:
            raise ValueError("Can't set NULL string!")
        else:
            self._mem.w_cstr(self._addr, val)

    def __getattr__(self, key):
        if key == "str":
            return self.get()
        else:
            return super(CStringType, self).__getattr__(key)

    def __setattr__(self, key, val):
        if key == "str":
            self.set(val)
        else:
            super(CStringType, self).__setattr__(key, val)

    def __eq__(self, other):
        # compare against other string
        if type(other) is str:
            return self.get() == other
        elif other is None:
            return self.get() is None
        else:
            return super(CStringType, self).__eq__(other)

    def __str__(self):
        return str(self.get())

    @classmethod
    def _alloc(cls, alloc, tag, txt):
        if tag is None:
            tag = "CString('%s')" % txt
        return alloc.alloc_cstr(txt, label=tag)

    @classmethod
    def _free(cls, alloc, mem_obj):
        alloc.free_cstr(mem_obj)


class BStringType(TypeBase):
    def __init__(self, mem, addr, **kwargs):
        super(BStringType, self).__init__(mem, addr, **kwargs)

    def get(self):
        if self._addr == 0:
            return None
        else:
            return self._mem.r_bstr(self._addr)

    def set(self, val):
        if self._addr == 0:
            raise ValueError("Can't set BNULL string!")
        else:
            self._mem.w_bstr(self._addr, val)

    def __getattr__(self, key):
        if key == "str":
            return self.get()
        else:
            return super(BStringType, self).__getattr__(key)

    def __setattr__(self, key, val):
        if key == "str":
            self.set(val)
        else:
            super(BStringType, self).__setattr__(key, val)

    def __eq__(self, other):
        # compare against other string
        if type(other) is str:
            return self.get() == other
        elif other is None:
            return self.get() is None
        else:
            super(BStringType, self).__eq__(other)

    def __str__(self):
        return str(self.get())

    @classmethod
    def _alloc(cls, alloc, tag, txt):
        if tag is None:
            tag = "BString('%s')" % txt
        return alloc.alloc_bstr(txt, label=tag)

    @classmethod
    def _free(cls, alloc, mem_obj):
        alloc.free_bstr(mem_obj)


class CSTR(APTR(CStringType)):
    @classmethod
    def get_signature(cls):
        return "CSTR"

    def get_str(self):
        if self.aptr == 0:
            return None
        else:
            return self.ref.get()

    def set_str(self, val):
        if self.aptr == 0:
            raise ValueError("Can't set NULL string!")
        else:
            self.ref.set(val)

    def __getattr__(self, key):
        if key == "str":
            return self.get_str()
        else:
            return super(CSTR, self).__getattr__(key)

    def __setattr__(self, key, val):
        if key == "str":
            self.set_str(val)
        else:
            super(CSTR, self).__setattr__(key, val)

    def alloc_str(self, alloc, txt):
        return self.alloc_ref(alloc, txt)

    def free_str(self):
        self.free_ref()

    def setup(self, val, alloc=None, free_refs=None):
        if type(val) is str:
            if alloc:
                self.alloc_str(alloc, val)
                free_refs.append(self)
            else:
                raise ValueError("no alloc for str!")
        else:
            return super().setup(val, alloc, free_refs)


class BSTR(BPTR(BStringType)):
    @classmethod
    def get_signature(cls):
        return "BSTR"

    def get_str(self):
        if self.bptr == 0:
            return None
        else:
            return self.ref.get()

    def set_str(self, val):
        if self.bptr == 0:
            raise ValueError("Can't set BNULL string!")
        else:
            self.ref.set(val)

    def __getattr__(self, key):
        if key == "str":
            return self.get_str()
        else:
            return super(BSTR, self).__getattr__(key)

    def __setattr__(self, key, val):
        if key == "str":
            self.set_str(val)
        else:
            super(BSTR, self).__setattr__(key, val)

    def alloc_str(self, alloc, txt):
        return self.alloc_ref(alloc, txt)

    def free_str(self):
        self.free_ref()

    def setup(self, val, alloc=None, free_refs=None):
        if type(val) is str:
            if alloc:
                self.alloc_str(alloc, val)
                free_refs.append(self)
            else:
                raise ValueError("no alloc for str!")
        else:
            return super().setup(val, alloc, free_refs)
