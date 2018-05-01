from amitools.vamos.astructs import ResidentStruct, AutoInitStruct, LibraryStruct
from amitools.vamos.mem import MemoryCache
from .bitfield import BitFieldType
from .node import NodeType
from .atype import AmigaType
from .atypedef import AmigaTypeDef
from .cstring import CString


@BitFieldType
class ResidentFlags:
  RTF_AUTOINIT = 1 << 7
  RTF_AFTERDOS = 1 << 2
  RTF_SINGLETASK = 1 << 1
  RTF_COLDSTART = 1 << 0


@AmigaTypeDef(AutoInitStruct)
class AutoInit(AmigaType):

  def setup(self, pos_size=0, functions=0, init_struct=0, init_func=0):
    if pos_size == 0:
      pos_size = LibraryStruct.get_size()
    self.pos_size = pos_size
    self.functions = functions
    self.init_struct = init_struct
    self.init_func = init_func


@AmigaTypeDef(ResidentStruct, wrap={'flags': ResidentFlags, 'type': NodeType})
class Resident(AmigaType):

  RTC_MATCHWORD = 0x4afc

  def __init__(self, mem, addr):
    AmigaType.__init__(self, mem, addr)
    # extra alloc info
    self._name_obj = None
    self._id_str_obj = None

  @classmethod
  def find(cls, mem, addr, size, only_first=True, mem_cache=True):
    """scan a memory region for resident structures and return the residents.
       if 'only_first' is set return a single instance or None.
       otherwise a list of Resident objects.
    """
    # use a memory cache to speed up search
    if mem_cache:
      memc = MemoryCache(addr, size)
      memc.read_cache(mem)
      mem = memc
    # start search
    end_addr = addr + size
    finds = []
    while addr < end_addr:
      # look for match word
      mw = mem.r16(addr)
      if mw == cls.RTC_MATCHWORD:
        # check pointer
        ptr = mem.r32(addr + 2)
        if ptr == addr:
          # yes its a resident...
          if only_first:
            return cls(mem, addr)
          finds.append(cls(mem, addr))
          # read end skip
          addr = mem.r32(addr + 6)
      addr += 2
    # nothing found for single match:
    if only_first:
      return None
    return finds

  @classmethod
  def alloc(cls, alloc, name, id_str):
    """alocate resident and optional name and id_str CStrings"""
    # handle name
    if type(name) is CString:
      name_obj = None
    elif type(name) is str:
      tag = "ResName(%s)" % name
      name_obj = CString.alloc(alloc, name, tag)
      name = name_obj
    else:
      raise ValueError("name must be str or CString")
    # handle id_str
    if type(id_str) is CString:
      id_str_obj = None
    elif type(id_str) is str:
      tag = "ResIdStr(%s)" % name
      id_str_obj = CString.alloc(alloc, id_str, tag)
      id_str = id_str_obj
    else:
      raise ValueError("id_str must be str or CString")
    # allocate resident
    res = cls._alloc(alloc)
    res._name_obj = name_obj
    res._id_str_obj = id_str_obj
    res.set_name(name)
    res.set_id_string(id_str)
    return res

  def free(self):
    if not self.alloc:
      raise RuntimeError("can't free")
    AmigaType.free(self)
    # cleanup name
    if self._name_obj:
      self._name_obj.free()
      self._name_obj = None
    # cleanup id str
    if self._id_str_obj:
      self._id_str_obj.free()
      self._id_str_obj = None

  def is_valid(self):
    if self.match_word != self.RTC_MATCHWORD:
      return False
    return self.match_tag == self.get_addr()

  def setup(self, flags=0, version=0, type=NodeType.NT_LIBRARY, pri=0, init=0):
    self.set_match_word(self.RTC_MATCHWORD)
    self.set_match_tag(self.addr)
    self.set_end_skip(self.addr + self.get_type_size())
    self.set_flags(flags)
    self.set_version(version)
    self.set_type(type)
    self.set_pri(pri)
    self.set_init(init)

  def get_auto_init(self):
    return AutoInit(self._mem, self.get_init())

  def set_auto_init(self, val):
    self.set_init(val._addr)
