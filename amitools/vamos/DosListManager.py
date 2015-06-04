import logging
from Log import log_doslist
from label.LabelRange import LabelRange
from lib.dos.DosStruct import *

class DosListEntry:
  def __init__(self,name):
    self.name = name
    self.addr = 0
    self.baddr = 0

  def __str__(self):
    return "[%s@%06x=b@%06x]" % (self.name, self.addr, self.baddr)

class DosListManager(LabelRange):
  def __init__(self, path_mgr, base_addr, size):
    self.path_mgr = path_mgr
    self.base_addr = base_addr
    self.cur_addr = base_addr
    log_doslist.info("init manager: base=%06x" % self.base_addr)

    self.entries_by_b_addr = {}
    self.entries_by_name = {}

    LabelRange.__init__(self, "doslist", base_addr, size)
    self.entry_device_def = DosListDeviceDef
    self.entry_volume_def = DosListVolumeDef
    self.entry_assign_def = DosListAssignDef
    self.entry_size = DosListDeviceDef.get_size()

  # direct read access to doslist structure
  def r32_doslist(self, addr):
    # find out associated file handle
    rel = int((addr - self.base_addr) / self.entry_size)
    entry_addr = self.base_addr + rel * self.entry_size
    b_addr = entry_addr >> 2
    entry = self.get_entry_by_b_addr(b_addr)
    if entry != None:
      # get addon text
      delta = addr - entry_addr
      name,off,val_type_name = self.entry_volume_def.get_name_for_offset(delta, 2)
      type_name = self.entry_volume_def.get_type_name()
      addon="%s+%d = %s(%s)+%d  %s" % (type_name, delta, name, val_type_name, off, entry)

      # get some special values
      val = 0

      self.trace_mem_int('R', 2, addr, val, text="DLIST", level=logging.INFO, addon=addon)
      return val
    else:
      self.trace_mem_int('R', 2, addr, val, text="NO_DLIST", level=logging.WARN)
      return 0

  def _add_entry(self, entry):
    entry.addr = self.cur_addr
    self.cur_addr += self.entry_size
    entry.baddr = entry.addr >> 2
    self.entries_by_b_addr[entry.baddr] = entry
    self.entries_by_name[entry.name] = entry
    log_doslist.info("add entry: %s", entry)

  def add_volume(self, name):
    entry = DosListEntry(name)
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
