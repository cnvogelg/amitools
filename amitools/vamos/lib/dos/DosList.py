from amitools.vamos.log import log_doslist
from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import (
    DosListVolumeStruct,
    DosListAssignStruct,
    AssignListStruct,
)


class DosListEntry:
    def __init__(self, name, struct_def):
        self.name = name
        self.struct_def = struct_def
        self.mem = None
        self.baddr = 0
        self.next = None

    def __str__(self):
        return "[%s@%06x=b@%06x]" % (self.name, self.mem.addr, self.baddr)


class DosList:
    def __init__(self, path_mgr, assign_mgr, mem, alloc):
        self.mem = mem
        self.alloc = alloc
        self.path_mgr = path_mgr
        self.assign_mgr = assign_mgr
        self.entries_by_b_addr = {}
        self.entries_by_name = {}
        self.entries = []
        self.first_entry = None
        self.LDF_ASSIGNS = 1 << 4
        self.LDF_VOLUMES = 1 << 3

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
            if last_entry is None:
                self.first_entry = entry
            else:
                last_entry.next = entry
                last_entry.access.w_s("dol_Next", entry.baddr << 2)
            last_entry = entry
        assigns = path_mgr.get_all_assign_names()
        for assign in assigns:
            alist = path_mgr.get_assign(assign).get_assigns()
            entry = self.add_assign(assign, alist)
            if last_entry is None:
                self.first_entry = entry
            else:
                last_entry.next = entry
                last_entry.access.w_s("dol_Next", entry.baddr << 2)
            last_entry = entry

    def free_list(self):
        for entry in self.entries:
            self.alloc.free_bstr(entry.name_addr)
            self.alloc.free_struct(entry.mem)
            for lock in entry.locks:
                self.lock_mgr.release_lock(lock)
            for alist in entry.alist:
                self.alloc.free_struct(alist)

    def _add_entry(self, entry):
        # allocate amiga entry
        entry.locks = []
        entry.alist = []
        entry.mem = self.alloc.alloc_struct(entry.struct_def, label=entry.name)
        entry.baddr = entry.mem.addr >> 2
        entry.access = AccessStruct(self.mem, entry.struct_def, entry.mem.addr)
        entry.name_addr = self.alloc.alloc_bstr("DosListName", entry.name)
        entry.access.w_s("dol_Name", entry.name_addr.addr)
        # register in lists
        self.entries_by_b_addr[entry.baddr] = entry
        self.entries_by_name[entry.name.lower()] = entry
        self.entries.append(entry)
        log_doslist.info("add entry: %s", entry)

    def add_volume(self, name):
        entry = DosListEntry(name, DosListVolumeStruct)
        self._add_entry(entry)
        entry.access.w_s("dol_Type", 2)  # volume
        entry.access.w_s("dol_Task", 1)  # something != 0
        entry.name = name
        entry.assigns = [name + ":"]
        return entry

    def add_assign(self, name, assign_names):
        entry = DosListEntry(name, DosListAssignStruct)
        self._add_entry(entry)
        entry.access.w_s("dol_Type", 1)  # directory
        entry.access.w_s("dol_Task", 1)  # something != 0
        entry.name = name
        entry.assigns = assign_names
        return entry

    # This call is used by the dos.library to create an
    # assign or relocate one.
    def create_assign(self, name, lock):
        syspath = lock.ami_path
        entry = self.get_entry_by_name(name)
        if entry == None:
            entry = self.add_assign(name, [name + ":"])
            entry.locks.append(lock)
            entry.access.w_s("dol_Lock", lock.mem.addr)
            entry.next = self.first_entry
            self.first_entry = entry
            self.assign_mgr.clear_assign(name.lower())
            self.assign_mgr.add_assign(name.lower(), [syspath])
            return entry
        else:
            if entry.access.r_s("dol_Type") != 1:
                return None
            oldlock_addr = entry.access.r_s("dol_Lock")
            oldlock = self.lock_mgr.get_by_b_addr(oldlock_addr >> 2)
            self.lock_mgr.release_lock(oldlock)
            entry.access.w_s("dol_Lock", lock.mem.addr)
            entry.assigns = [name + ":"]
            entry.locks = [lock]
            self._release_locklist(entry)
            self.assign_mgr.clear_assign(name.lower())
            self.assign_mgr.add_assign(name.lower(), [syspath])
            return entry

    def remove_assign(self, name):
        entry = self.get_entry_by_name(name)
        if entry.access.r_s("dol_Type") != 1:
            return None
        if entry != None:
            oldlock_addr = entry.access.r_s("dol_Lock")
            oldlock = self.lock_mgr.get_by_b_addr(oldlock_addr >> 2)
            self.lock_mgr.release_lock(oldlock)
            self._release_locklist(entry)
            others = self.first_entry
            if others == entry:
                self.first_entry = entry.next
            else:
                while others.next != None and others.next != entry:
                    others = others.next
                if others.next == entry:
                    others.next = entry.next
                    others.access.w_s("dol_Next", entry.access.r_s("dol_Next"))
            del self.entries_by_name[name.lower()]
            del self.entries_by_b_addr[entry.baddr]
            self.entries.remove(entry)
            self.alloc.free_struct(entry.mem)
            self.assign_mgr.clear_assign(name.lower())
        return True

    def _release_locklist(self, entry):
        alist_addr = entry.access.r_s("dol_List")
        entry.access.w_s("dol_List", 0)
        entry.alist = []
        while alist_addr != 0:
            alist = AccessStruct(self.mem, AssignListStruct, alist_addr)
            oldlock_addr = alist.r_s("al_Lock")
            oldlock = self.lock_mgr.get_by_b_addr(oldlock_addr >> 2)
            self.lock_mgr.release_lock(oldlock)
            entry.alist.remove(alist)
            nextaddr = alist.access.r_s("al_Next")
            self.alloc.free_struct(alist.mem)
            alist_addr = nextaddr

    # after creating the device list, the volume and assign
    # locks have to be added.
    def add_locks(self, lock_mgr):
        self.lock_mgr = lock_mgr
        for entry in self.entries:
            first = True
            assign_last = None
            name_addr = entry.access.r_s("dol_Name")
            # print "*** Entry %s, Name address is %s,%s" % (entry.mem,name_addr,self.mem.r_bstr(name_addr))
            for dirs in entry.assigns:
                lock = lock_mgr.create_lock(None, dirs, False)
                if lock is None:
                    log_doslist.warning("%s does not exist", dirs)
                else:
                    entry.locks.append(lock)
                    if first:
                        entry.access.w_s("dol_Lock", lock.mem.addr)
                        first = False
                    else:
                        assign_entry = self.alloc.alloc_struct(
                            AssignListStruct, label="AssignList"
                        )
                        entry.alist.append(assign_entry)
                        assign_entry.access.w_s("al_Next", 0)
                        assign_entry.access.w_s("al_Lock", lock.mem.addr)
                        if assign_last != None:
                            assign_last.w_s("al_Next", assign_entry.addr)
                        else:
                            entry.access.w_s("dol_List", assign_entry.addr)
                        assign_last = assign_entry.access

    def get_entry_by_b_addr(self, baddr):
        if baddr not in self.entries_by_b_addr:
            return None
        else:
            return self.entries_by_b_addr[baddr]

    def get_entry_by_name(self, name):
        if name.lower() not in self.entries_by_name:
            return None
        else:
            return self.entries_by_name[name.lower()]

    def _next_dos_entry(self, entry, flags):
        while entry != None:
            t = entry.access.r_s("dol_Type")
            if t == 1 and flags & self.LDF_ASSIGNS:
                return entry
            elif t == 2 and flags & self.LDF_VOLUMES:
                return entry
            entry = entry.next
        return None

    def lock_dos_list(self, flags):
        # Yes, this algorithm is really the one in the
        # dos.library.
        entry = self._next_dos_entry(self.first_entry, flags)
        if entry == None:
            return 0
        else:
            return entry.mem.addr + 1

    def unlock_dos_list(self, flags):
        pass

    def next_dos_entry(self, flags, node):
        if node == 0:
            return 0
        if node & 1:
            entry = self.entries_by_b_addr[(node - 1) >> 2]
        else:
            entry = self.entries_by_b_addr[node >> 2].next
            entry = self._next_dos_entry(entry, flags)
        if entry == None:
            return 0
        else:
            return entry.mem.addr
