from amitools.vamos.AmigaLibrary import AmigaLibrary
from lexec.ExecStruct import LibraryDef

class IFFParseLibrary(AmigaLibrary):
  name = "iffparse.library"

  def __init__(self, version=39, profile=False):
    AmigaLibrary.__init__(self, self.name, version, LibraryDef, profile)
