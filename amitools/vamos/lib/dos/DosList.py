from amitools.vamos.log import log_doslist
from amitools.vamos.libstructs import (
    DosListDeviceStruct,
    DosListVolumeStruct,
    DosListAssignStruct,
    AssignListStruct,
)


def _struct_field(struct, path):
    field = struct.get_path(path)
    if field is None:
        raise AttributeError(f"{type(struct).__name__} has no field path {path!r}")
    return field


def _struct_read(struct, path):
    field = _struct_field(struct, path)
    if hasattr(field, "val"):
        return field.val
    if hasattr(field, "aptr"):
        return field.aptr
    if hasattr(field, "bptr"):
        return field.bptr
    return field.get()


def _struct_write(struct, path, value):
    field = _struct_field(struct, path)
    if hasattr(field, "val"):
        field.val = value
    elif hasattr(field, "aptr"):
        field.aptr = value
    elif hasattr(field, "bptr"):
        field.aptr = value
    else:
        field.set(value)


class DosListEntry:
    def __init__(self, name, struct_def):
        self.name = name
        self.struct_def = struct_def
        self.mem = None
        self.struct = None
        self.baddr = 0
        self.next = None
        self.name_addr = None
        self.locks = []
        self.alist = []
        self.assigns = []
        self.exclusive = False
        self.inhibited = False
        self.unit = None

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
        self.LDF_DEVICES = 1 << 2
        self.LDF_ASSIGNS = 1 << 4
        self.LDF_VOLUMES = 1 << 3

    def __str__(self):
        res = "["
        for en in self.entries:
            res = res + en.__str__()
        res = res + "]"
        return res

    def build_list(self, path_mgr):
        """Build the DOS list and return its first entry's byte address."""
        # fill dos list
        volumes = path_mgr.get_all_volume_names()
        for vol in volumes:
            self.add_volume(vol)
        assigns = path_mgr.get_all_assign_names()
        for assign in assigns:
            alist = path_mgr.get_assign(assign).get_assigns()
            self.add_assign(assign, alist)
        return self.get_head_addr()

    def get_head_addr(self):
        if self.first_entry is None:
            return 0
        return self.first_entry.mem.addr

    def free_list(self):
        for entry in list(self.entries):
            self.remove_entry(entry)
            self.free_entry(entry)

    def free_entry(self, entry):
        """Free a detached entry and its DOS-list-owned allocations."""
        if entry in self.entries:
            raise ValueError("DOS list entry must be removed before it is freed")
        lock_mgr = getattr(self, "lock_mgr", None)
        if lock_mgr is not None:
            for lock in entry.locks:
                lock_mgr.release_lock(lock)
        for alist in entry.alist:
            alist.free()
        self.alloc.free_bstr(entry.name_addr)
        entry.mem.free()

    def _link_tail(self, entry):
        _struct_write(entry.struct, "dol_Next", 0)
        if self.first_entry is None:
            self.first_entry = entry
            return
        tail = self.first_entry
        while tail.next is not None:
            tail = tail.next
        tail.next = entry
        _struct_write(tail.struct, "dol_Next", entry.mem.addr)

    def _link_head(self, entry):
        old_head = self.first_entry
        entry.next = old_head
        _struct_write(
            entry.struct,
            "dol_Next",
            old_head.mem.addr if old_head is not None else 0,
        )
        self.first_entry = entry

    def _register_entry(self, entry):
        key = entry.name.lower()
        if key in self.entries_by_name:
            raise ValueError("DOS list entry already exists: %s" % entry.name)
        self.entries_by_b_addr[entry.baddr] = entry
        self.entries_by_name[key] = entry
        self.entries.append(entry)
        log_doslist.info("add entry: %s", entry)

    def _add_entry(self, entry, append=True):
        # allocate amiga entry
        entry.mem = entry.struct = self.alloc.alloc_astruct(
            entry.struct_def, label=entry.name
        )
        entry.baddr = entry.mem.addr >> 2
        entry.name_addr = self.alloc.alloc_bstr(entry.name, label="DosListName")
        _struct_write(entry.struct, "dol_Name", entry.name_addr.addr)
        self._register_entry(entry)
        if append:
            self._link_tail(entry)

    def add_existing_entry(self, name, struct, name_addr):
        """Adopt a MakeDosEntry() allocation without reallocating it."""
        entry = DosListEntry(name, type(struct))
        entry.mem = entry.struct = struct
        entry.baddr = struct.addr >> 2
        entry.name_addr = name_addr
        self._register_entry(entry)
        self._link_tail(entry)
        return entry

    def add_volume(self, name):
        entry = DosListEntry(name, DosListVolumeStruct)
        self._add_entry(entry)
        _struct_write(entry.struct, "dol_Type", 2)  # volume
        _struct_write(entry.struct, "dol_Task", 1)  # something != 0
        entry.name = name
        entry.assigns = [name + ":"]
        return entry

    def add_assign(self, name, assign_names, append=True):
        entry = DosListEntry(name, DosListAssignStruct)
        self._add_entry(entry, append=append)
        _struct_write(entry.struct, "dol_Type", 1)  # directory
        _struct_write(entry.struct, "dol_Task", 1)  # something != 0
        entry.name = name
        entry.assigns = assign_names
        return entry

    def add_device(
        self,
        name,
        startup_bptr,
        task=0,
        exclusive=False,
        unit=None,
    ):
        """Append a DLT_DEVICE backed by a FileSysStartupMsg BPTR."""
        entry = DosListEntry(name, DosListDeviceStruct)
        entry.exclusive = exclusive
        entry.unit = unit
        self._add_entry(entry)
        _struct_write(entry.struct, "dol_Type", 0)
        _struct_write(entry.struct, "dol_Task", task)
        _struct_write(entry.struct, "dol_Lock", 0)
        _struct_write(entry.struct, "dol_Handler", 0)
        _struct_write(entry.struct, "dol_StackSize", 0)
        _struct_write(entry.struct, "dol_Priority", 0)
        _struct_write(entry.struct, "dol_Startup", startup_bptr)
        _struct_write(entry.struct, "dol_SegList", 0)
        _struct_write(entry.struct, "dol_GlobVec", 0)
        return entry

    def remove_entry(self, entry):
        """Unlink an entry without freeing caller-owned allocations."""
        if isinstance(entry, int):
            entry = self.entries_by_b_addr.get(entry >> 2)
        if entry is None or entry not in self.entries:
            return False

        previous = None
        current = self.first_entry
        while current is not None and current is not entry:
            previous = current
            current = current.next
        if current is None:
            return False

        if previous is None:
            self.first_entry = entry.next
        else:
            previous.next = entry.next
            _struct_write(
                previous.struct,
                "dol_Next",
                entry.next.mem.addr if entry.next is not None else 0,
            )
        entry.next = None
        _struct_write(entry.struct, "dol_Next", 0)
        self.entries.remove(entry)
        self.entries_by_b_addr.pop(entry.baddr, None)
        self.entries_by_name.pop(entry.name.lower(), None)
        return True

    # This call is used by the dos.library to create an
    # assign or relocate one.
    def create_assign(self, name, lock):
        syspath = lock.ami_path
        entry = self.get_entry_by_name(name)
        if entry == None:
            entry = self.add_assign(name, [name + ":"], append=False)
            entry.locks.append(lock)
            _struct_write(entry.struct, "dol_Lock", lock.mem.addr)
            self._link_head(entry)
            self.assign_mgr.del_assign(name)
            self.assign_mgr.add_assign("%s:%s" % (name, syspath))
            return entry
        else:
            if _struct_read(entry.struct, "dol_Type") != 1:
                return None
            oldlock_addr = _struct_read(entry.struct, "dol_Lock")
            oldlock = self.lock_mgr.get_by_b_addr(oldlock_addr >> 2)
            self.lock_mgr.release_lock(oldlock)
            _struct_write(entry.struct, "dol_Lock", lock.mem.addr)
            entry.assigns = [name + ":"]
            entry.locks = [lock]
            self._release_locklist(entry)
            self.assign_mgr.del_assign(name)
            self.assign_mgr.add_assign("%s:%s" % (name, syspath))
            return entry

    def remove_assign(self, name):
        entry = self.get_entry_by_name(name)
        if entry is None or _struct_read(entry.struct, "dol_Type") != 1:
            return None
        oldlock_addr = _struct_read(entry.struct, "dol_Lock")
        oldlock = self.lock_mgr.get_by_b_addr(oldlock_addr >> 2)
        if oldlock is not None:
            self.lock_mgr.release_lock(oldlock)
        self._release_locklist(entry)
        self.remove_entry(entry)
        self.alloc.free_bstr(entry.name_addr)
        entry.mem.free()
        self.assign_mgr.del_assign(name)
        return True

    def _release_locklist(self, entry):
        alist_addr = _struct_read(entry.struct, "dol_List")
        _struct_write(entry.struct, "dol_List", 0)
        alist_mem_by_addr = {mem_obj.addr: mem_obj for mem_obj in entry.alist}
        entry.alist = []
        while alist_addr != 0:
            alist = AssignListStruct(self.mem, alist_addr)
            oldlock_addr = alist.al_Lock.aptr
            oldlock = self.lock_mgr.get_by_b_addr(oldlock_addr >> 2)
            self.lock_mgr.release_lock(oldlock)
            nextaddr = alist.al_Next.aptr
            mem_obj = alist_mem_by_addr.get(alist_addr)
            if mem_obj is not None:
                mem_obj.free()
            alist_addr = nextaddr

    # after creating the device list, the volume and assign
    # locks have to be added.
    def add_locks(self, lock_mgr):
        self.lock_mgr = lock_mgr
        for entry in self.entries:
            first = True
            assign_last = None
            name_addr = _struct_read(entry.struct, "dol_Name")
            # print "*** Entry %s, Name address is %s,%s" % (entry.mem,name_addr,self.mem.r_bstr(name_addr))
            for dirs in entry.assigns:
                lock = lock_mgr.create_lock(None, dirs, False)
                if lock is None:
                    log_doslist.warning("%s does not exist", dirs)
                else:
                    entry.locks.append(lock)
                    if first:
                        _struct_write(entry.struct, "dol_Lock", lock.mem.addr)
                        first = False
                    else:
                        assign_entry = self.alloc.alloc_astruct(
                            AssignListStruct, label="AssignList"
                        )
                        entry.alist.append(assign_entry)
                        assign_entry.al_Next.aptr = 0
                        assign_entry.al_Lock.aptr = lock.mem.addr
                        if assign_last != None:
                            assign_last.al_Next.aptr = assign_entry.addr
                        else:
                            _struct_write(entry.struct, "dol_List", assign_entry.addr)
                        assign_last = assign_entry

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
            t = _struct_read(entry.struct, "dol_Type")
            if t == 0 and flags & self.LDF_DEVICES:
                return entry
            elif t == 1 and flags & self.LDF_ASSIGNS:
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
