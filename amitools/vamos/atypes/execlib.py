from amitools.vamos.astructs import ExecLibraryStruct, SoftIntListStruct, IntVectorStruct
from .library import Library
from .atype import AmigaType
from .atypedef import AmigaTypeDef
from .bitfield import BitFieldType
from .node import NodeType
from .task import Task


@BitFieldType
class AttnFlags:
  AFF_68010 = (1 << 0)
  AFF_68020 = (1 << 1)
  AFF_68030 = (1 << 2)
  AFF_68040 = (1 << 3)
  AFF_68881 = (1 << 4)
  AFF_68882 = (1 << 5)
  AFF_FPU40 = (1 << 6)
  AFF_68060 = (1 << 7)


@AmigaTypeDef(SoftIntListStruct)
class SoftIntList(AmigaType):
  pass


@AmigaTypeDef(IntVectorStruct)
class IntVector(AmigaType):
  pass


@AmigaTypeDef(ExecLibraryStruct, wrap={'attn_flags': AttnFlags})
class ExecLibrary(AmigaType):

  def __init__(self, mem, addr):
    AmigaType.__init__(self, mem, addr)
    # extra alloc info
    self._lib = None

  def setup(self, version=0, revision=0, attn_flags=0, max_loc_mem=0):
    self.lib_node.setup(version, revision)
    self.attn_flags = attn_flags
    self.max_loc_mem = max_loc_mem
    # init lists
    self.mem_list.new_list(NodeType.NT_MEMORY)
    self.resource_list.new_list(NodeType.NT_RESOURCE)
    self.device_list.new_list(NodeType.NT_DEVICE)
    self.intr_list.new_list(NodeType.NT_INTERRUPT)
    self.lib_list.new_list(NodeType.NT_LIBRARY)
    self.port_list.new_list(NodeType.NT_MSGPORT)
    self.task_ready.new_list(NodeType.NT_TASK)
    self.task_wait.new_list(NodeType.NT_TASK)
    self.semaphore_list.new_list(NodeType.NT_SEMAPHORE)
    self.mem_handlers.new_list()

  def fill_funcs(self, opcode=None, param=None):
    self.lib_node.fill_funcs(opcode, param)

  @classmethod
  def alloc(cls, alloc, name, id_str, neg_size, pos_size=None):
    pos_size = cls.get_type_size()
    lib = Library.alloc(alloc, name, id_str, neg_size, pos_size)
    exec_lib = ExecLibrary.init_from(lib)
    exec_lib._lib = lib
    return exec_lib

  def free(self):
    self._lib.free()
