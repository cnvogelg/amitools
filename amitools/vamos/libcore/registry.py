from amitools.vamos.Exceptions import VamosInternalError
from .impl import LibImpl

class LibRegistry:
  def __init__(self, vamos_libs=None):
    # use default list
    if vamos_libs is None:
      import amitools.vamos.lib.LibList as LibList
      vamos_libs = LibList.vamos_libs
    # state
    self.vamos_libs = vamos_libs
    # map of open libs
    self.open_libs = {}

  def find_cls_by_name(self, name):
    """search a library by name and return its class"""
    if name in self.vamos_libs:
      return self.vamos_libs[name]

  def has_name(self, name):
    """test if a given name is available"""
    return name in self.vamos_libs

  def get_all_cls(self):
    """return all registered lib classes"""
    return self.vamos_libs.values()

  def get_all_names(self):
    """return all registered lib class names"""
    return self.vamos_libs.keys()

  def get_open_libs(self):
    return self.open_libs.values()

  def has_open_libs(self):
    return len(self.open_libs) > 0

  def open_lib(self, name):
    """open a library and create instance of it"""
    # try to find class
    lib_cls = self.find_cls_by_name(name)
    if lib_cls is None:
      return None
    lib = lib_cls()
    return self._int_open_lib(name, lib)

  def open_fake_lib(self, name):
    """open an empty fake lib of given name"""
    # create generic lib
    lib = LibImpl()
    return self._int_open_lib(name, lib)

  def _int_open_lib(self, name, lib):
    # only allow opening once
    if name in self.open_libs:
      raise VamosInternalError("Lib '%s' already opened!" % name)
    self.open_libs[name] = lib
    return lib

  def close_lib(self, name):
    if name not in self.open_libs:
      raise VamosInternalError("Lib '%s' not opened!" % name)
    del self.open_libs[name]
