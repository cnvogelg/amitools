from amitools.vamos.machine import MockMemory
from amitools.vamos.astructs import AmigaStruct, AmigaStructDef


@AmigaStructDef
class MyStruct(AmigaStruct):
  _format = [
      ('WORD', 'ms_Word'),
      ('UWORD', 'ms_Pad'),
      ('BPTR', 'ms_SegList'),
      ('LONG', 'ms_StackSize'),
  ]


@AmigaStructDef
class SubStruct(AmigaStruct):
  _format = [
      ('My', 'ss_My'),
      ('My*', 'ss_MyPtr'),
      ('Sub*', 'ss_SubPtr')
  ]


def astruct_astruct_base_test():
  # check class
  assert MyStruct.get_type_name() == 'My'
  assert MyStruct.get_size() == 12
  assert len(MyStruct.get_fields()) == 4
  assert MyStruct.get_num_fields() == 4
  ms_Word = MyStruct.get_field_by_name('ms_Word')
  assert MyStruct.ms_Word_field == ms_Word
  assert MyStruct.get_field_names(
  ) == ['ms_Word', 'ms_Pad', 'ms_SegList', 'ms_StackSize']
  # offset
  assert MyStruct.get_field_offset_for_path('ms_SegList') == 4
  assert MyStruct.get_field_offset_for_path('ms_Pad') == 2
  MyStruct.dump_type()
  # data class
  dc = MyStruct.get_data_class()
  assert dc
  assert dc.__name__ == 'MyData'
  data = dc(ms_Word=12, ms_Pad=0, ms_SegList=3, ms_StackSize=5)
  # check instance
  mem = MockMemory()
  ms = MyStruct(mem, 0x10)
  assert str(ms) == "[AStruct:My,@000010+00000c]"
  # data
  data = ms.read_data()
  ms.write_data(data)
  ms.dump()
  # access
  ms.write_field("ms_Word", -3000)
  assert ms.read_field("ms_Word") == -3000
  word_field = ms.get_field_by_name('ms_Word')
  assert ms.read_field_ext("ms_Word") == (ms, word_field, -3000)
  # addr to field
  stack_field = ms.get_field_by_name('ms_StackSize')
  addr = ms.get_field_addr(stack_field)
  assert ms.get_struct_field_for_addr(addr) == (ms, stack_field, 0)
  assert ms.get_struct_field_for_name('ms_StackSize') == (ms, stack_field)
  # getattr/setattr
  ms.ms_Word = 2000
  assert ms.ms_Word == 2000


def astruct_astruct_sub_struct_test():
  # check class
  assert SubStruct.get_type_name() == 'Sub'
  assert SubStruct.get_size() == 20
  assert len(SubStruct.get_fields()) == 3
  assert SubStruct.get_num_fields() == 3
  assert SubStruct.get_field_by_name('ss_My')
  assert SubStruct.get_field_names() == ['ss_My', 'ss_MyPtr', 'ss_SubPtr']
  assert SubStruct.get_field_offset_for_path('ss_My') == 0
  assert SubStruct.get_field_offset_for_path('ss_My.ms_SegList') == 4
  SubStruct.dump_type()
  # check instance
  mem = MockMemory()
  ss = SubStruct(mem, 0x10)
  assert str(ss) == "[AStruct:Sub,@000010+000014]"
  # data
  data = ss.read_data()
  ss.write_data(data)
  ss.dump()
  # access
  ss.write_field("ss_My.ms_Word", -3000)
  assert ss.read_field("ss_My.ms_Word") == -3000
  # create my instance
  my_field = ss.get_field_by_index(0)
  ms = ss.create_struct(my_field)
  word_field = ms.get_field_by_name('ms_Word')
  assert ss.read_field_ext("ss_My.ms_Word") == (ms, word_field, -3000)
  # addr to field
  stack_field = ms.get_field_by_name('ms_StackSize')
  addr = ms.get_field_addr(stack_field)
  assert ss.get_struct_field_for_addr(addr) == (ms, stack_field, 0)
  assert ss.get_struct_field_for_name(
      'ss_My.ms_StackSize') == (ms, stack_field)
  # getattr/setattr
  ss.ss_My.ms_Word = 2000
  assert ss.ss_My.ms_Word == 2000


