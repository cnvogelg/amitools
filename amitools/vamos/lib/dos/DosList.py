import logging
from amitools.vamos.Log import log_doslist
from amitools.vamos.AccessStruct import AccessStruct
from DosStruct import DosListDeviceDef, DosListVolumeDef, DosListAssignDef, AssignListDef
from amitools.vamos.lib.dos.LockManager import LockManager

class DosListEntry:
  def __init__(self,name,struct_def):
    self.name = name
    self.struct_def = struct_def
    self.mem = None
    self.baddr = 0

  def __str__(self):
    return "[%s@%06x=b@%06x]" % (self.name, self.mem.addr, self.baddr)

class DosList:
  def __init__(self, mem, alloc):
    self.mem   = mem
    self.alloc = alloc
    self.entries_by_b_addr = {}
    self.entries_by_name = {}
    self.entries = []

  def __str__(self):
    res = "["
    for en in self.entries:
      res = res + en.__str__()
    res = res + "]"
    return res

  def build_list(self, path_mgr):
    """build the dos list and return a bptr of the first entry"""
    # fill dos list
    last_entry = None
    volumes = path_mgr.get_all_volume_names()
    for vol in volumes:
      entry = self.add_volume(vol)
      if last_entry is not None:
        last_entry.access.w_s('dol_Next', entry.baddr)
      last_entry = entry
    assigns,auto_assigns = path_mgr.get_all_assigns()
    for assign in assigns:
      entry = self.add_assign(assign,assigns[assign])
      if last_entry is not None:
        last_entry.access.w_s('dol_Next', entry.baddr)
      last_entry = entry

  def free_list(self):
    for entry in self.entries:
      self.alloc.free_struct(entry.mem)

  def _add_entry(self, entry):
    # allocate amiga entry
    entry.mem    = self.alloc.alloc_struct(entry.name,entry.struct_def)
    entry.baddr  = entry.mem.addr >> 2
    entry.access = AccessStruct(self.mem,entry.struct_def,entry.mem.addr)
    name_addr    = self.alloc.alloc_bstr("DosListName",entry.name)
    entry.access.w_s("dol_Name",name_addr.addr)
    # register in lists
    self.entries_by_b_addr[entry.baddr] = entry
    self.entries_by_name[entry.name.lower()] = entry
    self.entries.append(entry)
    log_doslist.info("add entry: %s", entry)

  def add_volume(self, name):
    entry = DosListEntry(name,DosListVolumeDef)
    self._add_entry(entry)
    entry.access.w_s("dol_Type",2) #volume
    entry.name    = name
    entry.assigns = [name+":"]
    return entry
  
  def add_assign(self, name, assign_names):
    entry = DosListEntry(name,DosListAssignDef)
    self._add_entry(entry)
    entry.access.w_s("dol_Type",1) #directory
    entry.name    = name
    entry.assigns = assign_names
    return entry

  # after creating the device list, the volume and assign
  # locks have to be added.
  def add_locks(self, lock_mgr):
    for entry in self.entries:
      first       = True
      assign_last = None
      name_addr   = entry.access.r_s("dol_Name")
      #print "*** Entry %s, Name address is %s,%s" % (entry.mem,name_addr,self.mem.access.r_bstr(name_addr))
      for dirs in entry.assigns:
        lock = lock_mgr.create_lock(None,dirs,False)
        if first:
          entry.access.w_s("dol_Lock",lock.mem.addr)
          first = False
        else:
          assign_entry = self.alloc.alloc_struct("AssignList",AssignListDef)
          access       = AccessStruct(self.mem,AssignListDef,assign_entry.addr)
          access.w_s("al_Next",0)
          access.w_s("al_Lock",lock.mem.addr)
          if assign_last != None:
            assign_last.w_s("al_Next",assign_entry.addr)
          else:
            entry.access.w_s("dol_List",assign_entry.addr)
          assign_last = access

  def get_entry_by_b_addr(self, baddr):
    if not self.entries_by_b_addr.has_key(baddr):
      return None
    else:
      return self.entries_by_b_addr[baddr]

  def get_entry_by_name(self, name):
    if not self.entries_by_name.has_key(name.lower()):
      return None
    else:
      return self.entries_by_name[name.lower()]
