from amitools.vamos.lib.lexec.ExecStruct import LibraryDef

class LibImpl(object):
  """base class for all Python-based library implementations"""

  def is_base_lib(self):
    return False

  def get_struct_def(self):
    """return the structure of your library pos_size"""
    return LibraryDef

  def setup_lib(self, ctx, base_addr):
    pass

  def finish_lib(self, ctx):
    pass
