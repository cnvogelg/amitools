from amitools.vamos.astructs import ProcessStruct, CLIStruct, PathListStruct
from .atype import AmigaTypeWithName, AmigaType
from .atypedef import AmigaTypeDef
from .node import NodeType


@AmigaTypeDef(PathListStruct)
class PathList(AmigaType):
  pass


@AmigaTypeDef(CLIStruct)
class CLI(AmigaType):
  pass


@AmigaTypeDef(ProcessStruct)
class Process(AmigaTypeWithName):

  def setup(self):
    self.task.setup(nt=NodeType.NT_PROCESS)
    self.msg_port.setup()
    self.local_vars.new_list()

  def set_name(self, val):
    self.task.node.name = val

  def get_name(self, ptr=False):
    return self.task.node.get_name(ptr)
