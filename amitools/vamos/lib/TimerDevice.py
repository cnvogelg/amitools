from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.Log import *

class TimerDevice(AmigaLibrary):

  def __init__(self, name, config):
    AmigaLibrary.__init__(self, name, LibraryDef, config)
