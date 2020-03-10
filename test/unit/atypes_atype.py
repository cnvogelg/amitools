from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.astructs import AmigaStruct, AmigaStructDef
from amitools.vamos.atypes import AmigaType, AmigaTypeDef, CString


@AmigaStructDef
class MyStruct(AmigaStruct):
    _format = [
        ("WORD", "ms_Word"),
        ("UWORD", "ms_Pad"),
        ("BPTR", "ms_SegList"),
        ("LONG", "ms_StackSize"),
        ("char*", "ms_String"),
    ]


@AmigaStructDef
class SubStruct(AmigaStruct):
    _format = [("My", "ss_My"), ("My*", "ss_MyPtr"), ("Sub*", "ss_SubPtr")]


class Bla(object):
    def __init__(self, val):
        self.val = val

    def __eq__(self, other):
        return self.val == other.val

    def __int__(self):
        return self.val

    @staticmethod
    def setf(obj):
        assert type(obj) is Bla
        return obj.val

    @staticmethod
    def getf(val):
        return Bla(val)


def atypes_atype_base_test():

    # simple type without extra contents
    # wrap field 'pad' with getter/setter
    @AmigaTypeDef(MyStruct, wrap={"pad": (Bla.getf, Bla.setf)})
    class MyType(AmigaType):
        pass

    # create a type instance
    mem = MockMemory()
    alloc = MemoryAlloc(mem, addr=0x100)
    mt = MyType(mem, 0x10)
    # regular values (signed/unsigend)
    mt.set_word(-3)
    assert mt.get_word() == -3
    # direct access
    mt.word = 5
    assert mt.word == 5
    # wrapped type
    assert type(mt.get_pad()) is Bla
    mt.set_pad(Bla(3))
    assert mt.get_pad() == Bla(3)
    assert mt.get_pad(raw=True) == 3
    mt.set_pad(21, raw=True)
    assert mt.get_pad() == Bla(21)
    # direct access
    mt.pad = Bla(39)
    assert mt.pad == Bla(39)
    # cstring
    assert type(mt.get_string()) is CString
    txt = "hello, word!"
    cstr = CString.alloc(alloc, txt)
    cstr_addr = cstr.get_addr()
    mt.set_string(cstr)
    assert mt.get_string() == txt
    assert mt.get_string() == CString(mem, cstr_addr)
    assert mt.get_string(ptr=True) == cstr_addr
    mt.string = cstr
    assert mt.string == txt
    assert mt.string == cstr
    cstr.free()


def atypes_atype_complex_test():

    # complex type with own ctor
    # wrap field 'pad' with getter only, assume int() setter
    @AmigaTypeDef(MyStruct, wrap={"pad": Bla.getf})
    class MyType(AmigaType):
        def __init__(self, mem, addr, extra=None):
            AmigaType.__init__(self, mem, addr)
            self._extra = extra

    # create a type instance: signature is (mem, addr, extra)
    mem = MockMemory()
    mt = MyType(mem, 0x10, "hello")
    assert mt._extra == "hello"
    # regular values (signed/unsigend)
    mt.set_word(-3)
    assert mt.get_word() == -3
    # wrapped type
    assert type(mt.get_pad()) is Bla
    mt.set_pad(Bla(3))
    assert mt.get_pad() == Bla(3)
    assert mt.get_pad(raw=True) == 3
    mt.set_pad(21, raw=True)
    assert mt.get_pad() == Bla(21)


def atypes_atype_struct_test():
    # complex type with own ctor
    # wrap field 'pad' with getter only, assume int() setter
    @AmigaTypeDef(SubStruct)
    class SubType(AmigaType):
        pass

    # create instance
    mem = MockMemory()
    st = SubType(mem, 0x10)
    # get struct
    mt = st.get_my()
    my_type = AmigaType.find_type("My")
    assert type(mt) is my_type
    assert mt.get_addr() == 0x10
    assert mt == st.my
    # struct pointer
    # null pointer -> None
    mtp = st.get_my_ptr()
    assert mtp is None
    assert st.my_ptr is None
    # valid pointer -> type object
    st.set_my_ptr(0x30)
    mtp = st.get_my_ptr()
    assert type(mtp) is my_type
    assert mtp.get_addr() == 0x30
    st.my_ptr = 0x40
    assert st.my_ptr.get_addr() == 0x40
    assert type(st.my_ptr) is my_type
    # self pointer
    msp = st.get_sub_ptr()
    assert msp is None
    st.set_sub_ptr(0x50)
    msp = st.get_sub_ptr()
    assert type(msp) is type(st)
    assert msp.get_addr() == 0x50
    st.sub_ptr = 0x60
    assert st.sub_ptr.get_addr() == 0x60
    assert type(st.sub_ptr) is type(st)
    # null pointer
    st.set_sub_ptr(None)
    assert st.get_sub_ptr() is None
    assert st.get_sub_ptr(ptr=True) == 0
    st.sub_ptr = None
    assert st.sub_ptr is None


def atypes_atype_alloc_test():
    @AmigaTypeDef(MyStruct, wrap={"pad": (Bla.getf, Bla.setf)})
    class MyType(AmigaType):
        pass

    @AmigaTypeDef(SubStruct)
    class SubType(AmigaType):
        pass

    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # my type
    mt = MyType.alloc(alloc)
    assert mt
    assert mt.get_addr() != 0
    mt.free()
    # sub
    st = SubType.alloc(alloc)
    assert st
    assert st.get_addr() != 0
    st.free()
    assert alloc.is_all_free()
