from amitools.vamos.astructs import LibraryStruct
from amitools.vamos.label import LabelLib
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

  def __init__(self, mem, addr):
    AmigaType.__init__(self, mem, addr)
    # extra alloc info
    self.name_obj = None
    self.id_str_obj = None
    self.label = None

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

  @classmethod
  def alloc(cls, alloc, name, id_str, neg_size, pos_size=None):
    """alocate library and optional name and id_str CStrings"""
    # handle name
    if type(name) is CString:
      name_obj = None
    elif type(name) is str:
      tag = "LibName(%s)" % name
      name_obj = CString.alloc(alloc, name, tag)
      name = name_obj
    else:
      raise ValueError("name must be str or CString")
    # handle id_str
    if type(id_str) is CString:
      id_str_obj = None
    elif type(id_str) is str:
      tag = "LibIdStr(%s)" % name
      id_str_obj = CString.alloc(alloc, id_str, tag)
      id_str = id_str_obj
    else:
      raise ValueError("id_str must be str or CString")
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
    lib.mem_obj = mem_obj
    lib.alloc = alloc
    lib.size = total_size
    # set pos/neg size
    lib.set_pos_size(pos_size)
    lib.set_neg_size(neg_size)
    # add label?
    label_mgr = alloc.get_label_mgr()
    if label_mgr:
      lib.label = LabelLib(lib)
      label_mgr.add_label(lib.label)
    # set name and id_str
    lib.name_obj = name_obj
    lib.id_str_obj = id_str_obj
    lib.set_name(name)
    lib.set_id_string(id_str)
    return lib

  def free(self):
    if not self.alloc:
      raise RuntimeError("can't free")
    self.alloc.free_memory(self.mem_obj)
    self.alloc = None
    self.mem_obj = None
    self.addr = 0
    # cleanup name
    if self.name_obj:
      self.name_obj.free()
      self.name_obj = None
    # cleanup id str
    if self.id_str_obj:
      self.id_str_obj.free()
      self.id_str_obj = None
    # cleanup label
    if self.label:
      self.alloc.get_label_mgr().remove_label(self.label)
      self.label = None

  def calc_sum(self):
    """calc the lib sum and return it"""
    neg_size = self.get_neg_size()
    addr = self.addr - neg_size
    lib_sum = 0
    while addr < self.addr:
      val = self.mem.r32(addr)
      lib_sum += val
      addr += 4
    lib_sum &= 0xffffffff
    return lib_sum

  def update_sum(self):
    """calc new lib sum and store it"""
    lib_sum = self.calc_sum()
    self.set_sum(lib_sum)

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
