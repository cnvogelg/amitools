import pytest
from amitools.vamos.machine import MockMemory, MockCPU, REG_D0
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.astructs import (
    AmigaStruct,
    AmigaStructDef,
    AmigaClassDef,
    WORD,
    UWORD,
    BPTR_VOID,
    LONG,
    APTR,
    APTR_SELF,
    CSTR,
    BSTR,
)


@AmigaStructDef
class MyStruct(AmigaStruct):
    _format = [
        (WORD, "ms_Word"),
        (UWORD, "ms_Pad"),
        (BPTR_VOID, "ms_SegList"),
        (LONG, "ms_StackSize"),
    ]  # 12


@AmigaStructDef
class SubStruct(AmigaStruct):
    _format = [
        (MyStruct, "ss_My"),  # 0 +12
        (APTR(MyStruct), "ss_MyPtr"),  # 12 +4
        (APTR_SELF, "ss_SubPtr"),  # 16 +4
        (MyStruct, "ss_My2"),
    ]  # 20 +12
    # = 32


def astructs_astruct_base_class_test():
    # check class members
    assert MyStruct.sdef.get_type_name() == "My"
    assert MyStruct.get_byte_size() == 12
    # get field defs
    field_defs = MyStruct.sdef.get_field_defs()
    assert field_defs
    assert len(field_defs) == 4
    # get one field
    field_def = MyStruct.sdef.get_field_def(0)
    assert field_def.name == "ms_Word"
    # find by name
    ms_Word = MyStruct.sdef.find_field_def_by_name("ms_Word")
    assert MyStruct.sdef.ms_Word == ms_Word
    res = MyStruct.sdef.find_sub_field_defs_by_name("ms_Word")
    assert res == [ms_Word]
    # find by alias name
    stack_size = MyStruct.sdef.stack_size  # alias for ms_StackSize
    assert stack_size is MyStruct.sdef.ms_StackSize
    # offset of fields
    fd, delta = MyStruct.sdef.find_field_def_by_offset(4)
    assert fd.name == "ms_SegList"
    assert delta == 0
    fd, delta = MyStruct.sdef.find_field_def_by_offset(3)
    assert fd.name == "ms_Pad"
    assert delta == 1
    # offset/base offset of fields
    assert MyStruct.sdef.ms_Pad.offset == 2
    assert MyStruct.sdef.ms_Pad.base_offset == 2
    # signature
    assert MyStruct.get_signature() == "My"


def astructs_astruct_base_inst_test():
    # check instance
    mem = MockMemory()
    ms = MyStruct(mem, 0x10)
    assert str(ms) == "[AStruct:My,@000010+00000c]"
    # field access
    fields = ms.sfields.get_fields()
    assert len(fields) == 4
    field = ms.sfields.get_field_by_index(0)
    assert field.get_addr() == 0x10
    assert ms.get("ms_Word") == field
    assert ms.sfields.find_field_by_offset(0) == (field, 0)
    assert ms.sfields.find_field_by_addr(0x10) == (field, 0)
    assert ms.sfields.find_field_def_by_addr(0x10) == (ms.sdef[0], 0)
    assert ms.ms_Word == field
    # alias name
    field = ms.ms_StackSize
    assert ms.stack_size == field
    # access
    ms.get("ms_Word").set(-3000)
    assert ms.get("ms_Word").get() == -3000
    # access via __getattr__
    ms.ms_Word.set(2000)
    assert ms.ms_Word.get() == 2000
    # find field
    field = ms.ms_Word
    assert ms.sfields.find_sub_field_by_def(MyStruct.sdef.ms_Word) == field
    # try to assign field directly -> forbidden!
    with pytest.raises(AttributeError):
        ms.ms_Word = 42


def astructs_astruct_base_inst_reg_test():
    cpu = MockCPU()
    mem = MockMemory()
    ms = MyStruct(mem, 0x10)
    ms.ms_Word.val = 42
    # prepare pointer
    cpu.w_reg(REG_D0, 0x10)
    MyStructAPtr = APTR(MyStruct)
    ptr = MyStructAPtr(cpu=cpu, reg=REG_D0, mem=mem)
    assert ptr.aptr == 0x10
    ms2 = ptr.ref
    assert ms2.ms_Word.val == 42


def astructs_astruct_base_inst_setup_test():
    mem = MockMemory()
    ms = MyStruct(mem, 0x10, ms_Word=42, ms_Pad=21, ms_SegList=0x400)
    assert ms.ms_Word.val == 42
    assert ms.ms_Pad.val == 21
    assert ms.ms_SegList.aptr == 0x400


def astructs_astruct_sub_struct_class_test():
    # check class
    assert SubStruct.sdef.get_type_name() == "Sub"
    assert SubStruct.get_byte_size() == 32
    assert len(SubStruct.sdef.get_field_defs()) == 4
    field_defs = SubStruct.sdef.get_field_defs()
    field_names = list(map(lambda x: x.name, field_defs))
    assert field_names == ["ss_My", "ss_MyPtr", "ss_SubPtr", "ss_My2"]
    # find by name
    assert SubStruct.sdef.find_field_def_by_name("ss_My")
    res = SubStruct.sdef.find_sub_field_defs_by_name("ss_My", "ms_Pad")
    assert res == [SubStruct.sdef.ss_My, MyStruct.sdef.ms_Pad]
    assert SubStruct.sdef.find_sub_field_defs_by_name("ss_My", "Foo") is None
    assert SubStruct.sdef.find_sub_field_defs_by_name("ss_SubPtr", "Foo") is None
    # field defs
    assert SubStruct.sdef.find_field_def_by_offset(3) == (SubStruct.sdef.ss_My, 3)
    assert SubStruct.sdef.find_field_def_by_offset(23) == (SubStruct.sdef.ss_My2, 3)
    # find sub field defs
    sub_fds = SubStruct.sdef.find_sub_field_defs_by_offset(3)
    assert sub_fds == ([SubStruct.sdef.ss_My, MyStruct.sdef.ms_Pad], 1)
    sub_fds = SubStruct.sdef.find_sub_field_defs_by_offset(23)
    assert sub_fds == ([SubStruct.sdef.ss_My2, MyStruct.sdef.ms_Pad], 1)
    # access sub field
    assert SubStruct.sdef.ss_My.ms_Word == MyStruct.sdef.ms_Word
    # offset/base offset of field
    assert SubStruct.sdef.ss_My2.offset == 20
    assert SubStruct.sdef.ss_My2.base_offset == 20
    assert SubStruct.sdef.ss_My2.ms_Pad.offset == 2
    assert SubStruct.sdef.ss_My2.ms_Pad.base_offset == 22
    # parent defs
    assert SubStruct.sdef.ss_My2.ms_Pad.parent_def == SubStruct.sdef.ss_My2
    # def path
    assert SubStruct.sdef.ss_My2.ms_Pad.get_def_path() == [
        SubStruct.sdef.ss_My2,
        MyStruct.sdef.ms_Pad,
    ]


def astructs_astruct_sub_struct_inst_test():
    # check instance
    mem = MockMemory()
    ss = SubStruct(mem, 0x10)
    assert str(ss) == "[AStruct:Sub,@000010+000020]"
    assert ss.mem is mem
    assert ss.addr == 0x10
    # get/find field
    ms = ss.ss_My
    assert type(ms) is MyStruct
    assert ms.addr == 0x10
    assert ms.ms_Pad.addr == 0x12
    assert ss.get("ss_My") is ms
    assert ss.sfields.find_field_by_offset(3) == (ms, 3)
    assert ss.sfields.find_field_by_addr(0x13) == (ms, 3)
    ms2 = ss.ss_My2
    assert type(ms2) is MyStruct
    assert ms2.addr == 0x10 + 20
    assert ms2.ms_Pad.addr == 0x12 + 20
    assert ss.get("ss_My2") is ms2
    assert ss.sfields.find_field_by_offset(23) == (ms2, 3)
    assert ss.sfields.find_field_by_addr(0x13 + 20) == (ms2, 3)
    # get sub fields
    sub_fs = ss.sfields.find_sub_fields_by_offset(3)
    assert sub_fs == ([ms, ms.ms_Pad], 1)
    sub_fs = ss.sfields.find_sub_fields_by_offset(23)
    assert sub_fs == ([ms2, ms2.ms_Pad], 1)
    # getattr/setattr
    ss.ss_My.ms_Word.set(2000)
    assert ss.ss_My.ms_Word.get() == 2000
    # addr/offset/base_offset
    assert ss.ss_My.addr == 0x10
    assert ss.ss_My.mem == mem
    assert ss.ss_My2.addr == 0x10 + 20
    assert ss.ss_My2.offset == 20
    assert ss.ss_My2.base_offset == 20
    # sub field: addr/offset/base_offset
    assert ss.ss_My2.ms_Pad.addr == 0x10 + 22
    assert ss.ss_My2.ms_Pad.offset == 2
    assert ss.ss_My2.ms_Pad.base_offset == 22
    # find sub field
    field = ss.ss_My2.ms_Pad
    assert ss.sfields.find_sub_field_by_def(SubStruct.sdef.ss_My2.ms_Pad) == field


def astructs_astruct_baddr_test():
    mem = MockMemory()
    ms = MyStruct(mem, 0x10)
    # write int to baddr
    ms.ms_SegList.set(0x40)
    # bptr auto converts back to baddr
    assert ms.ms_SegList.get() == 0x40
    # baddr is stored in mem
    assert mem.r32(0x14) == 0x40
    # write baddr
    ms.ms_SegList.set(0x20)
    assert mem.r32(0x14) == 0x20


def astructs_astruct_alloc_ptr_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    MyStructPtr = APTR(MyStruct)
    ptr = MyStructPtr(mem, 0x10)
    assert ptr.aptr == 0
    res = ptr.alloc_ref(alloc)
    assert type(res) is MyStruct
    assert ptr.aptr != 0
    ptr.free_ref()
    assert ptr.aptr == 0
    assert alloc.is_all_free()


def astructs_astruct_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    res = MyStruct.alloc(alloc, ms_Word=21, ms_Pad=42)
    assert type(res) is MyStruct
    assert res.ms_Word.val == 21
    assert res.ms_Pad.val == 42
    res.free()
    assert alloc.is_all_free()


def astructs_astruct_alloc_sub_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    res = SubStruct.alloc(alloc, ss_My={"ms_Word": 21, "ms_Pad": 42})
    assert type(res) is SubStruct
    assert res.ss_My.ms_Word.val == 21
    assert res.ss_My.ms_Pad.val == 42
    res.free()
    assert alloc.is_all_free()


@AmigaStructDef
class PlainStruct(AmigaStruct):
    _format = [
        (APTR_SELF, "ps_Next"),
        (APTR_SELF, "ps_Prev"),
        (CSTR, "ps_Name"),
        (BSTR, "ps_Bname"),
    ]


def astructs_astruct_plain_setup_test():
    mem = MockMemory()
    pc = PlainStruct(mem, 0x10, next=0x100, prev=0x200, name=0x120, bname=0x140)
    assert pc.next.aptr == 0x100
    assert pc.prev.aptr == 0x200
    assert pc.name.aptr == 0x120
    assert pc.bname.aptr == 0x140


@AmigaClassDef
class PlainClass(PlainStruct):
    def foo(self):
        result = []
        prev = self.prev.ref
        if prev:
            prev_foo = prev.foo()
            result.append(prev_foo)
        txt = self.name.str
        if txt:
            result.append(txt)
        next = self.next.ref
        if next:
            next_foo = next.foo()
            result.append(next_foo)
        return " ".join(result)


def astructs_astruct_class_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    pc = PlainClass.alloc(alloc)
    assert type(pc) == PlainClass
    assert pc.foo() == ""
    # alloc a name
    pc.name.alloc_str(alloc, "hello")
    assert pc.foo() == "hello"
    # another struct
    pc2 = PlainClass.alloc(alloc, name="world!")
    assert type(pc2) == PlainClass
    assert pc2.name.str == "world!"
    assert pc2.foo() == "world!"
    pc.next.ref = pc2
    assert pc.foo() == "hello world!"
    # more struct
    pc3 = PlainClass.alloc(alloc, name="what:", bname="ugh!", next=pc2)
    assert pc3.foo() == "what: world!"
    assert pc3.next.ref is pc2
    assert pc3.name.str == "what:"
    assert pc3.bname.str == "ugh!"
    pc3.free()
    pc2.free()
    # clean up pc
    pc.name.free_str()
    pc.free()
    assert alloc.is_all_free()


@AmigaStructDef
class SubPlainStruct(AmigaStruct):
    _format = [
        (PlainStruct, "plain"),
        (PlainStruct, "plain2"),
    ]
    _subfield_aliases = {"name": "plain.name"}


@AmigaClassDef
class SubPlainClass(SubPlainStruct):
    pass


def astructs_astruct_class_sub_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    spc = SubPlainClass.alloc(alloc, plain={"name": "abc"}, plain2={"name": "cde"})
    assert type(spc) == SubPlainClass
    assert spc.plain.name.str == "abc"
    assert spc.plain2.name.str == "cde"
    spc.free()
    assert alloc.is_all_free()


def astructs_astruct_class_subfield_alias_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    spc = SubPlainClass.alloc(alloc, name="abc", plain2={"name": "cde"})
    assert type(spc) == SubPlainClass
    assert spc.plain.name.str == "abc"
    assert spc.plain2.name.str == "cde"
    spc.free()
    assert alloc.is_all_free()
