import logging
from amitools.vamos.Log import log_doslist
from DosStruct import DosListDeviceDef, DosListVolumeDef, DosListAssignDef

class DosListEntry:
  def __init__(self,name,struct_def):
    self.name = name
    self.struct_def = struct_def
    self.mem = None
    self.baddr = 0

  def __str__(self):
    return "[%s@%06x=b@%06x]" % (self.name, self.addr, self.baddr)

class DosList:
  def __init__(self, alloc):
    self.alloc = alloc
    self.entries_by_b_addr = {}
    self.entries_by_name = {}
    self.entries = []

  def build_list(self, path_mgr):
    """build the dos list and return a bptr of the first entry"""
    # fill dos list
    last_entry = None
    volumes = path_mgr.get_all_volume_names()
    for vol in volumes:
      entry = self.add_volume(vol)
      if last_entry is not None:
        last_entry.mem.w_s('dol_Next', entry.baddr)
      last_entry = entry

  def free_list(self):
    for entry in self.entries:
      self.alloc.free_struct(entry.mem)

  def _add_entry(self, entry):
    # allocate amiga entry
    entry.mem = self.alloc.alloc_struct(entry.name,entry.struct_def)
    entry.baddr = entry.mem.addr >> 2
    # register in lists
    self.entries_by_b_addr[entry.baddr] = entry
    self.entries_by_name[entry.name] = entry
    self.entries.append(entry)
    log_doslist.info("add entry: %s", entry)

  def add_volume(self, name):
    entry = DosListEntry(name,DosListVolumeDef)
    self._add_entry(entry)

  def get_entry_by_b_addr(self, baddr):
    if not self.entries_by_b_addr.has_key(baddr):
      return None
    else:
      return self.entries_by_b_addr[baddr]

  def get_entry_by_name(self, name):
    if not self.entries_by_name.has_key(name):
      return None
    else:
      return self.entries_by_name[name]
