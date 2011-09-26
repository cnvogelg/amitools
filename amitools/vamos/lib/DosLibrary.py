from amitools.vamos.AmigaLibrary import *

class DosLibrary(AmigaLibrary):
  
  def __init__(self, version, context):
    AmigaLibrary.__init__(self,"dos.library", version, 30, 200, 10, context)
