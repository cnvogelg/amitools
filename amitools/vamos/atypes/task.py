from amitools.vamos.astructs import TaskStruct
from .atype import AmigaType
from .atypedef import AmigaTypeDef
from .bitfield import BitFieldType
from .enum import EnumType
from .node import NodeType
from .cstring import CString


@BitFieldType
class TaskFlags(object):
  TF_PROCTIME = (1L << 0)
  TF_ETASK = (1L << 3)
  TF_STACKCHK = (1L << 4)
  TF_EXCEPT = (1L << 5)
  TF_SWITCH = (1L << 6)
  TF_LAUNCH = (1L << 7)


@EnumType
class TaskState(object):
  TS_INVALID = 0
  TS_ADDED = 1
  TS_RUN = 2
  TS_READY = 3
  TS_WAIT = 4
  TS_EXCEPT = 5
  TS_REMOVED = 6


@AmigaTypeDef(TaskStruct, wrap={'Flags': TaskFlags, 'State': TaskState})
class Task(AmigaType):

  def __init__(self, mem, addr, alloc=None):
    AmigaType.__init__(self, mem, addr)
    # extra alloc info
    self._alloc = alloc
    self._name_obj = None
    self._mem_obj = None

  def setup(self, pri=0, flags=0, nt=NodeType.NT_TASK):
    node = self.get_node()
    node.set_type(nt)
    node.set_pri(pri)

    self.set_flags(flags)
    self.set_state(TaskState.TS_INVALID)
    self.mem_entry.new_list(NodeType.NT_MEMORY)

  @classmethod
  def alloc(cls, alloc, name):
    # handle name
    tag = name
    if type(name) is CString:
      name_obj = None
    elif type(name) is str:
      tag = "TaskName(%s)" % name
      name_obj = CString.alloc(alloc, name, tag)
      name = name_obj
    else:
      raise ValueError("name must be str or CString")
    task = cls._alloc(alloc, tag)
    task.set_name(name)
    task._name_obj = name_obj
    return task

  def free(self):
    AmigaType.free(self)
    if self._name_obj:
      self._name_obj.free()
      self._name_obj = None

  def set_name(self, val):
    self.get_node().set_name(val)

  def get_name(self, ptr=False):
    return self.get_node().get_name(ptr)
