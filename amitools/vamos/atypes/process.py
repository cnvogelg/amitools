from amitools.vamos.astructs import ProcessStruct, CLIStruct
from .atype import AmigaType
from .atypedef import AmigaTypeDef


@AmigaTypeDef(ProcessStruct)
class Process(AmigaType):
  pass


@AmigaTypeDef(CLIStruct)
class CLI(AmigaType):
  pass
