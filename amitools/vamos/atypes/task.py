from amitools.vamos.astructs import TaskStruct
from .atype import AmigaType
from .atypedef import AmigaTypeDef


@AmigaTypeDef(TaskStruct)
class Task(AmigaType):
  pass
