from amitools.vamos.astructs import LibraryStruct
from amitools.vamos.label import LabelLib
from amitools.vamos.machine.opcodes import op_rts
from .atype import AmigaType
from .atypedef import AmigaTypeDef
from .node import NodeType
from .bitfield import BitFieldType
from .cstring import CString


@BitFieldType
class LibFlags(object):
  LIBF_SUMMING = (1 << 0)
  LIBF_CHANGED = (1 << 1)
  LIBF_SUMUSED = (1 << 2)
  LIBF_DELEXP = (1 << 3)


@AmigaTypeDef(LibraryStruct, wrap={'flags': LibFlags})
class Library(AmigaType):

  def __init__(self, mem, addr, alloc=None):
    AmigaType.__init__(self, mem, addr)
    # extra alloc info
    self._name_cstr = None
    self._id_str_cstr = None
    self._label = None
    self._alloc = alloc
    self._mem_obj = None

  def set_name(self, val):
    self.get_node().set_name(val)

  def get_name(self, ptr=False):
    return self.get_node().get_name(ptr)

  def setup(self, version=0, revision=0,
            type=NodeType.NT_LIBRARY, pri=0, flags=0):
    """set all lib values but name, id_str, pos_size, neg_size."""
    node = self.get_node()
    node.set_succ(0)
    node.set_pred(0)
    node.set_type(type)
    node.set_pri(pri)

    self.set_flags(flags)
    self.set_pad(0)
    self.set_version(version)
    self.set_revision(revision)
    self.set_sum(0)
    self.set_open_cnt(0)

  def fill_funcs(self, opcode=None, param=None):
    """quickly fill the function table of a library with an opcode and param"""
    if opcode is None:
      opcode = op_rts
    neg_size = self.neg_size
    off = 6
    while off < neg_size:
      addr = self._addr - off
      self._mem.w16(addr, opcode)
      if param:
        self._mem.w32(addr + 2, param)
      off += 6

  @classmethod
  def alloc(cls, alloc, name, id_str, neg_size, pos_size=None, fd=None):
    """alocate library and optional name and id_str CStrings"""
    # calc size
    if pos_size is None:
      pos_size = cls.get_type_size()
    # round neg_size to multiple of four
    neg_size = (neg_size + 3) & ~3
    total_size = pos_size + neg_size
    # allocate lib
    mem_obj = alloc.alloc_memory(None, total_size, add_label=False)
    addr_base = mem_obj.addr + neg_size
    lib = cls(alloc.get_mem(), addr_base)
    lib._mem_obj = mem_obj
    lib._alloc = alloc
    lib._size = total_size
    # set pos/neg size
    lib.set_pos_size(pos_size)
    lib.set_neg_size(neg_size)
    # add label?
    label_mgr = alloc.get_label_mgr()
    if label_mgr:
      struct = lib.get_type_struct()
      lib._label = LabelLib(name, addr_base, neg_size, pos_size, struct, fd)
      label_mgr.add_label(lib._label)
    # set name and id_str
    if name:
      lib._name_cstr = CString.alloc(alloc, name)
      lib.set_name(lib._name_cstr)
    if id_str:
      lib._id_str_cstr = CString.alloc(alloc, id_str)
      lib.set_id_string(lib._id_str_cstr)
    return lib

  def free(self):
    if not self._alloc:
      raise RuntimeError("can't free")
    mem_obj = self._mem_obj
    if mem_obj is None:
      addr = self._addr - self.neg_size
      mem_obj = self._alloc.get_memory(addr)
    self._alloc.free_memory(mem_obj)
    # cleanup name
    if self._name_cstr:
      self._name_cstr.free()
      self._name_cstr = None
    # cleanup id str
    if self._id_str_cstr:
      self._id_str_cstr.free()
      self._id_str_cstr = None
    # cleanup label
    if self._label:
      self._alloc.get_label_mgr().remove_label(self._label)
      self._label = None
    # clear state
    self._alloc = None
    self._mem_obj = None
    self._addr = 0

  def calc_sum(self):
    """calc the lib sum and return it"""
    neg_size = self.get_neg_size()
    addr = self._addr - neg_size
    lib_sum = 0
    while addr < self._addr:
      val = self._mem.r32(addr)
      lib_sum += val
      addr += 4
    lib_sum &= 0xffffffff
    return lib_sum

  def update_sum(self):
    """calc new lib sum and store it"""
    lib_sum = self.calc_sum()
    self.set_sum(lib_sum)
    return lib_sum

  def check_sum(self):
    """calc and compare lib sum with stored value"""
    lib_sum = self.calc_sum()
    got_sum = self.get_sum()
    return lib_sum == got_sum

  def inc_open_cnt(self):
    cnt = self.get_open_cnt()
    cnt += 1
    self.set_open_cnt(cnt)

  def dec_open_cnt(self):
    cnt = self.get_open_cnt()
    cnt -= 1
    self.set_open_cnt(cnt)
