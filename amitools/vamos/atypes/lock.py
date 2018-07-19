from amitools.vamos.astructs import FileLockStruct, FileHandleStruct
from .atype import AmigaType
from .atypedef import AmigaTypeDef


@AmigaTypeDef(FileLockStruct)
class FileLock(AmigaType):
  pass


@AmigaTypeDef(FileHandleStruct)
class FileHandle(AmigaType):
  pass
