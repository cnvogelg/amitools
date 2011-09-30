from amitools.vamos.AmigaLibrary import *
from amitools.vamos.structure.DosStruct import DosLibraryDef

class DosLibrary(AmigaLibrary):
  
  def __init__(self, version, context):
    AmigaLibrary.__init__(self,"dos.library", version, 30, 200, DosLibraryDef, context)
