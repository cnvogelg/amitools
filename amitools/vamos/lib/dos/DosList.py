from amitools.vamos.astructs import CSTR
from amitools.vamos.log import log_doslist, log_dos
from amitools.vamos.libstructs import (
    DosListDeviceStruct,
    DosListVolumeStruct,
    DosListAssignStruct,
    AssignListStruct,
    FileHandleStruct,
    ExAllControlStruct,
    FileInfoBlockStruct,
    DosPacketStruct,
    CLIStruct,
    RDArgsStruct,
)

from .Error import (
    DOSTRUE,
    DOSFALSE,
    NO_ERROR,
    ERROR_DEVICE_NOT_MOUNTED,
    ERROR_OBJECT_WRONG_TYPE,
)
from . import Lock


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
    def __init__(self, path_mgr, assign_mgr, mem, alloc, handler_mgr=None):
        self.mem = mem
        self.alloc = alloc
        self.path_mgr = path_mgr
        self.assign_mgr = assign_mgr
        self.handler_mgr = handler_mgr
        self.entries_by_b_addr = {}
        self.entries_by_name = {}
        self.devices_by_name = {}
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
            # non-filesystem handlers are devices, added in add_host_devices
            if self._is_filesystem(vol):
                self.add_volume(vol)
        assigns = path_mgr.get_all_assign_names()
        for assign in assigns:
            alist = path_mgr.get_assign(assign).get_assigns()
            self.add_assign(assign, alist)
        return self.get_head_addr()

    def _is_filesystem(self, name):
        """is the handler behind this volume/device a file system?"""
        if self.handler_mgr is None:
            return True
        return self.handler_mgr.is_filesystem(name)

    def _is_native(self, name):
        """is the handler behind this volume/device a native (68k) one?"""
        if self.handler_mgr is None:
            return False
        handler = self.handler_mgr.get_handler(name)
        return getattr(handler, "is_native", False)

    def get_head_addr(self):
        if self.first_entry is None:
            return 0
        return self.first_entry.mem.addr

    def free_list(self):
        for entry in list(self.entries):
            self.remove_entry(entry)
            self.free_entry(entry)

    def _handler_port(self, name):
        """the packet port of the handler registered as ``name`` (0 if none)"""
        if self.handler_mgr is None:
            return 0
        handler = self.handler_mgr.get_handler(name)
        dispatcher = getattr(handler, "dispatcher", None)
        return dispatcher.port if dispatcher is not None else 0

    def add_host_devices(self):
        """Publish mounted volumes and devices in the DOS list.

        Every handler is reachable through its own packet port (its
        ``dispatcher``). A filesystem volume gets a paired device entry backed
        by that port; a non-filesystem device (``NIL:``, ``CONSOLE:``, ...)
        gets a device entry backed by its port too. The ports are owned by the
        handlers (freed when their dispatchers are detached).
        """
        for volume in tuple(self.entries):
            if volume.struct_def is not DosListVolumeStruct:
                continue
            # a native handler's node is published by its manager (step 24c):
            # skip it here so the two do not create a duplicate
            if self._is_native(volume.name):
                continue
            port = self._handler_port(volume.name)
            self.add_device(volume.name, startup_bptr=0, task=port)
            _struct_write(volume.struct, "dol_Task", port)
        # device handlers (NIL:, CONSOLE:, ...) become device-only entries
        if self.handler_mgr is not None:
            for name in self.handler_mgr.get_all_names():
                if self.handler_mgr.is_filesystem(name):
                    continue
                if self.get_entry_by_name(name) is not None:
                    continue
                self.add_device(name, startup_bptr=0, task=self._handler_port(name))

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
        index = (
            self.devices_by_name
            if entry.struct_def is DosListDeviceStruct
            else self.entries_by_name
        )
        if key in index:
            raise ValueError("DOS list entry already exists: %s" % entry.name)
        self.entries_by_b_addr[entry.baddr] = entry
        index[key] = entry
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
        seg_list=0,
        glob_vec=0,
        handler=0,
    ):
        """Append a DLT_DEVICE backed by a FileSysStartupMsg BPTR.

        ``seg_list`` is the BPTR of an already loaded handler seglist and
        ``handler`` the BPTR of the handler binary name (a BSTR) used by
        ``LoadSeg`` when ``seg_list`` is 0. Both default to 0 for the Python
        handlers whose code runs in-process. ``glob_vec`` is the handler's
        global vector (``-1``/``-2`` for C/asm handlers).
        """
        entry = DosListEntry(name, DosListDeviceStruct)
        entry.exclusive = exclusive
        entry.unit = unit
        self._add_entry(entry)
        _struct_write(entry.struct, "dol_Type", 0)
        _struct_write(entry.struct, "dol_Task", task)
        _struct_write(entry.struct, "dol_Lock", 0)
        _struct_write(entry.struct, "dol_Handler", handler)
        _struct_write(entry.struct, "dol_StackSize", 0)
        _struct_write(entry.struct, "dol_Priority", 0)
        _struct_write(entry.struct, "dol_Startup", startup_bptr)
        _struct_write(entry.struct, "dol_SegList", seg_list)
        _struct_write(entry.struct, "dol_GlobVec", glob_vec)
        return entry

    def fill_device(self, entry, task=0, seg_list=0, glob_vec=0, handler=0):
        """Fill in the handler fields of an existing ``DLT_DEVICE`` entry.

        Used by the native handler manager to *adopt* a ``--disk`` partition
        node (step 24c): the handler's ``dol_Task``/``dol_SegList``/
        ``dol_GlobVec``/``dol_Handler`` are set while ``dol_Startup`` - owned by
        the :class:`~amitools.vamos.disk.DiskSession` - is left untouched. The
        defaults clear the fields again (e.g. when the handler stops).
        """
        if entry.struct_def is not DosListDeviceStruct:
            raise ValueError("not a DOS device entry: %s" % entry.name)
        _struct_write(entry.struct, "dol_Task", task)
        _struct_write(entry.struct, "dol_SegList", seg_list)
        _struct_write(entry.struct, "dol_GlobVec", glob_vec)
        _struct_write(entry.struct, "dol_Handler", handler)
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
        index = (
            self.devices_by_name
            if entry.struct_def is DosListDeviceStruct
            else self.entries_by_name
        )
        index.pop(entry.name.lower(), None)
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
        if not self.is_assign_entry(entry):
            return None
        self.remove_entry(entry)
        # free_entry releases dol_Lock and every AssignList lock and frees
        # the AssignList nodes; releasing them here again would double-free
        self.free_entry(entry)
        self.assign_mgr.del_assign(name)
        return True

    def is_assign_entry(self, entry):
        """is a DOS list entry a directory assign?"""
        return entry is not None and _struct_read(entry.struct, "dol_Type") == 1

    def _rebuild_assign_list(self, entry):
        """rewrite dol_Lock/dol_List from ``entry.locks`` (first is primary)"""
        for alist in entry.alist:
            alist.free()
        entry.alist = []
        _struct_write(entry.struct, "dol_Lock", 0)
        _struct_write(entry.struct, "dol_List", 0)
        first = True
        last = None
        for lock in entry.locks:
            if first:
                _struct_write(entry.struct, "dol_Lock", lock.mem.addr)
                first = False
                continue
            alist = self.alloc.alloc_astruct(AssignListStruct, label="AssignList")
            alist.al_Next.aptr = 0
            alist.al_Lock.aptr = lock.mem.addr
            entry.alist.append(alist)
            if last is not None:
                last.al_Next.aptr = alist.addr
            else:
                _struct_write(entry.struct, "dol_List", alist.addr)
            last = alist

    def _sync_assign_mgr(self, entry):
        """mirror an assign's directory list into the path manager

        ``entry.assigns`` is the canonical list of Amiga paths: it also keeps
        paths of a late assign that does not exist (and thus has no lock).
        """
        paths = list(entry.assigns)
        if not paths:
            paths = [str(lock.ami_path) for lock in entry.locks]
        self.assign_mgr.set_assign(entry.name, paths)

    def set_assign_paths(self, name, paths):
        """create/conver an assign pointing at the given Amiga paths.

        AssignLate()/AssignPath() delegate here. An existing assign is
        replaced; a volume/device of the same name is left alone and None is
        returned.
        """
        entry = self.get_entry_by_name(name)
        if entry is not None and not self.is_assign_entry(entry):
            return None
        if entry is not None:
            self.remove_assign(name)
        entry = self.add_assign(name, list(paths), append=False)
        entry.locks = []
        _struct_write(entry.struct, "dol_List", 0)
        for path in paths:
            lock = self.lock_mgr.create_lock(None, path, False)
            if lock is None:
                log_doslist.warning("assign %s: path does not exist: %s", name, path)
            else:
                entry.locks.append(lock)
        self._rebuild_assign_list(entry)
        self._link_head(entry)
        self._sync_assign_mgr(entry)
        return entry

    def add_assign_lock(self, name, lock):
        """AssignAdd(): append a directory lock to an existing assign"""
        entry = self.get_entry_by_name(name)
        if not self.is_assign_entry(entry):
            return False
        entry.locks.append(lock)
        path = str(lock.ami_path)
        if path not in entry.assigns:
            entry.assigns.append(path)
        self._rebuild_assign_list(entry)
        self._sync_assign_mgr(entry)
        return True

    def remove_assign_lock(self, name, lock):
        """RemAssignList(): remove a directory lock from an assign"""
        entry = self.get_entry_by_name(name)
        if not self.is_assign_entry(entry):
            return False
        index = None
        for i, cur in enumerate(entry.locks):
            if self.lock_mgr.same_lock(cur, lock):
                index = i
                break
        if index is None:
            return False
        stored = entry.locks.pop(index)
        path = str(stored.ami_path)
        if path in entry.assigns:
            entry.assigns.remove(path)
        # drop the DOS list's view first, then unlink the entry if empty
        self._rebuild_assign_list(entry)
        if entry.locks:
            self._sync_assign_mgr(entry)
            # like AmigaDOS the stored lock is released, but a lock handed in
            # by the caller stays usable (it is not the assign's lock then)
            if stored is not lock:
                self.lock_mgr.release_lock(stored)
        else:
            self.remove_assign(name)
            # the destroyed assign releases its last resource too
            self.lock_mgr.release_lock(stored)
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

    def get_entry_by_name(self, name, flags=None):
        key = name.lower()
        if flags is not None and flags & self.LDF_DEVICES:
            device = self.devices_by_name.get(key)
            if device is not None:
                return device
        entry = self.entries_by_name.get(key)
        if entry is not None:
            return entry
        return self.devices_by_name.get(key)

    def get_device_by_name(self, name):
        """the ``DLT_DEVICE`` entry named ``name`` (or ``None``)

        Unlike :meth:`get_entry_by_name` this never falls back to a volume or
        assign of the same name, so a caller that needs the *device* node (the
        native handler manager, step 24c) is not confused by a volume entry.
        """
        return self.devices_by_name.get(name.lower())

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

    def get_first_entry(self, flags):
        """the first entry matching the DOS list type flags"""
        return self._next_dos_entry(self.first_entry, flags)

    def get_next_entry(self, entry, flags):
        """the entry after ``entry`` matching the DOS list type flags"""
        if entry is None:
            return None
        return self._next_dos_entry(entry.next, flags)

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


# ----- fd functions (RKRM AmigaDOS 3, "DOS list" and "DOS objects") -----


def lock_dos_list(dos, ctx, flags):
    return dos.dos_list.lock_dos_list(flags)


def unlock_dos_list(dos, ctx, flags):
    dos.dos_list.unlock_dos_list(flags)


def next_dos_entry(dos, ctx, node, flags):
    return dos.dos_list.next_dos_entry(flags, node)


def find_dos_entry(dos, ctx, dlist, name_ptr, flags):
    if name_ptr == 0:
        log_dos.info(
            "FindDosEntry(dlist=0x%x, name=NULL, flags=0x%x) -> 0", dlist, flags
        )
        return 0
    try:
        name = ctx.mem.r_cstr(name_ptr)
    except Exception:
        log_dos.info("FindDosEntry: failed to read CSTR at 0x%x", name_ptr)
        return 0
    if name and name.endswith(":"):
        name = name[:-1]
    entry = dos.dos_list.get_entry_by_name(name, flags)
    if entry is None:
        log_dos.info("FindDosEntry('%s', flags=0x%x) -> 0 (not found)", name, flags)
        return 0
    entry_type = entry.struct.dol_Type.val
    type_matches = False
    if entry_type == 0 and (flags & 4):
        type_matches = True
    elif entry_type == 2 and (flags & 8):
        type_matches = True
    elif entry_type == 1 and (flags & 16):
        type_matches = True
    if not type_matches:
        log_dos.info(
            "FindDosEntry('%s', flags=0x%x) -> 0 (type %d doesn't match)",
            name,
            flags,
            entry_type,
        )
        return 0
    log_dos.info("FindDosEntry('%s', flags=0x%x) -> 0x%x", name, flags, entry.mem.addr)
    return entry.mem.addr


def attempt_lock_dos_list(dos, ctx, flags):
    log_dos.info("AttemptLockDosList(flags=0x%x)", flags)
    return dos.dos_list.lock_dos_list(flags)


def inhibit(dos, ctx, name, onoff):
    dev_name = name if name else ""
    if dev_name.endswith(":"):
        dev_name = dev_name[:-1]
    entry = dos.dos_list.get_entry_by_name(dev_name)
    if (
        entry is None
        or entry.struct.dol_Type.val != 0
        or not entry.exclusive
        or entry.struct.dol_Task.aptr != 0
    ):
        dos.setioerr(ctx, ERROR_DEVICE_NOT_MOUNTED)
        log_dos.info("Inhibit('%s', %d) -> false", dev_name, onoff)
        return DOSFALSE
    entry.inhibited = bool(onoff)
    dos.setioerr(ctx, NO_ERROR)
    log_dos.info("Inhibit('%s', %d) -> true", dev_name, onoff)
    return DOSTRUE


def make_dos_entry(dos, ctx, name_ptr, entry_type):
    try:
        name = ctx.mem.r_cstr(name_ptr) if name_ptr else ""
    except Exception:
        name = ""
    if not name:
        name = f"vol_{entry_type:x}"
    struct_defs = {
        0: DosListDeviceStruct,
        1: DosListAssignStruct,
        2: DosListVolumeStruct,
    }
    struct_def = struct_defs.get(entry_type)
    if struct_def is None:
        dos.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
        return 0
    entry = ctx.alloc.alloc_astruct(struct_def, label=f"DosList({name})")
    entry.dol_Next.aptr = 0
    entry.dol_Type.val = entry_type
    entry.dol_Task.aptr = 0
    entry.dol_Lock.aptr = 0
    if struct_def is DosListDeviceStruct:
        entry.dol_Handler.aptr = 0
        entry.dol_StackSize.val = 0
        entry.dol_Priority.val = 0
        entry.dol_Startup.val = 0
        entry.dol_SegList.aptr = 0
        entry.dol_GlobVec.val = 0
    elif struct_def is DosListVolumeStruct:
        entry.dol_LockList.aptr = 0
        entry.dol_DiskType.val = 0
    else:
        entry.dol_List.aptr = 0
    name_mem = ctx.alloc.alloc_bstr(name, label="DosListName")
    entry.dol_Name.aptr = name_mem.addr
    dos.dos_entries[entry.addr] = {
        "mem": entry,
        "name": name_mem,
        "name_text": name,
        "dos_list_entry": None,
    }
    log_dos.info("MakeDosEntry('%s', type=%d) -> 0x%x", name, entry_type, entry.addr)
    return entry.addr


def add_dos_entry(dos, ctx, dlist_ptr):
    record = dos.dos_entries.get(dlist_ptr)
    ok = record is not None and record["dos_list_entry"] is None
    if ok:
        try:
            record["dos_list_entry"] = dos.dos_list.add_existing_entry(
                record["name_text"], record["mem"], record["name"]
            )
        except ValueError:
            ok = False
        else:
            dos.update_dos_list_head()
    log_dos.info("AddDosEntry(0x%x) -> %s", dlist_ptr, ok)
    return DOSTRUE if ok else DOSFALSE


def rem_dos_entry(dos, ctx, dlist_ptr):
    record = dos.dos_entries.get(dlist_ptr)
    entry = record["dos_list_entry"] if record is not None else None
    ok = entry is not None and dos.dos_list.remove_entry(entry)
    if ok:
        record["dos_list_entry"] = None
        dos.update_dos_list_head()
    log_dos.info("RemDosEntry(0x%x) -> %s", dlist_ptr, ok)
    return DOSTRUE if ok else DOSFALSE


def free_dos_entry(dos, ctx, dlist_ptr):
    entry = dos.dos_entries.pop(dlist_ptr, None)
    if entry:
        linked_entry = entry["dos_list_entry"]
        if linked_entry is not None:
            dos.dos_list.remove_entry(linked_entry)
            dos.update_dos_list_head()
        ctx.alloc.free_bstr(entry["name"])
        ctx.alloc.free_struct(entry["mem"])
    log_dos.info("FreeDosEntry(0x%x)", dlist_ptr)
    return 0


def is_file_system(dos, ctx, name_ptr):
    name = ctx.mem.r_cstr(name_ptr)
    log_dos.info("IsFileSystem('%s'):", name)
    lock = dos.get_current_dir(ctx)
    res = dos.file_mgr.is_file_system(lock, name)
    log_dos.info("IsFileSystem('%s'): %s", name, res)
    if res:
        return DOSTRUE
    else:
        return DOSFALSE


def alloc_dos_object(dos, ctx, obj_type, tags_ptr):
    if obj_type == 0:  # DOS_FILEHANDLE
        name = "DOS_FILEHANDLE"
        struct_def = FileHandleStruct
    elif obj_type == 1:  # DOS_EXALLCONTROL
        name = "DOS_EXALLCONTROL"
        struct_def = ExAllControlStruct
    elif obj_type == 2:  # DOS_FIB
        name = "DOS_FIB"
        struct_def = FileInfoBlockStruct
    elif obj_type == 3:  # DOS_STDPKT
        name = "DOS_STDPKT"
        struct_def = DosPacketStruct
    elif obj_type == 4:  # DOS_CLI
        name = "DOS_CLI"
        struct_def = CLIStruct
    elif obj_type == 5:  # DOS_RDARGS
        name = "DOS_RDARGS"
        struct_def = RDArgsStruct
    else:
        log_dos.error("AllocDosObject: invalid type=%d", obj_type)
        return 0
    if struct_def is None:
        log_dos.warning("AllocDosObject: unsupported type=%d/%s", obj_type, name)
        return 0
    # DOS_CLI needs its standard string buffers (prompt/setname/command name/
    # command file) allocated as well, so build it through the CLI helper.
    # A bare CLIStruct would leave those pointers NULL and a caller writing
    # through them (SetPrompt, SetCurrentDirName, ...) would corrupt low memory.
    extra = None
    if obj_type == 4:
        from .Cli import alloc_cli_struct

        dos_obj, extra = alloc_cli_struct(dos, ctx, label=name)
    else:
        dos_obj = ctx.alloc.alloc_astruct(struct_def, label=name)
    log_dos.info(
        "AllocDosObject: type=%d/%s tags_ptr=%08x -> dos_obj=%s",
        obj_type,
        name,
        tags_ptr,
        dos_obj,
    )
    # store struct
    ptr = dos_obj.addr
    dos.dos_objs[ptr] = (dos_obj, obj_type, extra)
    # pre fill struct
    if obj_type == 0:
        dos_obj.fh_Pos.val = 0xFFFFFFFF
        dos_obj.fh_End.val = 0xFFFFFFFF
    return ptr


def free_dos_object(dos, ctx, obj_type, ptr):
    # retrieve struct
    if ptr in dos.dos_objs:
        entry = dos.dos_objs[ptr]
        del dos.dos_objs[ptr]
        # check type
        if obj_type != entry[1]:
            log_dos.warning("FreeDosObject: type mismatch %d != %d", obj_type, entry[1])
        # Freeing a control also releases an unfinished scan.
        if entry[1] == 1:
            Lock.drop_exall_scan(dos, ptr)
        # DOS_CLI also owns its string buffers (see alloc_dos_object)
        extra = entry[2] if len(entry) > 2 else None
        if extra:
            for mem_obj in extra:
                ctx.alloc.free_memory(mem_obj)
        # free struct
        ctx.alloc.free_struct(entry[0])
    else:
        log_dos.error("FreeDosObject: type=%d ptr=%08x -> NOT FOUND!", obj_type, ptr)


class DosListMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def IsFileSystem(self, ctx, name_ptr):
        return is_file_system(self, ctx, name_ptr)

    def AllocDosObject(self, ctx, obj_type, tags_ptr):
        return alloc_dos_object(self, ctx, obj_type, tags_ptr)

    def FreeDosObject(self, ctx, obj_type, ptr):
        return free_dos_object(self, ctx, obj_type, ptr)

    def LockDosList(self, ctx, flags):
        return lock_dos_list(self, ctx, flags)

    def UnLockDosList(self, ctx, flags):
        return unlock_dos_list(self, ctx, flags)

    def NextDosEntry(self, ctx, node, flags):
        return next_dos_entry(self, ctx, node, flags)

    def FindDosEntry(self, ctx, dlist, name_ptr, flags):
        return find_dos_entry(self, ctx, dlist, name_ptr, flags)

    def AttemptLockDosList(self, ctx, flags):
        return attempt_lock_dos_list(self, ctx, flags)

    def Inhibit(self, ctx, name: CSTR, onoff):
        return inhibit(self, ctx, name.get_str(), onoff)

    def MakeDosEntry(self, ctx, name_ptr, entry_type):
        return make_dos_entry(self, ctx, name_ptr, entry_type)

    def AddDosEntry(self, ctx, dlist_ptr):
        return add_dos_entry(self, ctx, dlist_ptr)

    def RemDosEntry(self, ctx, dlist_ptr):
        return rem_dos_entry(self, ctx, dlist_ptr)

    def FreeDosEntry(self, ctx, dlist_ptr):
        return free_dos_entry(self, ctx, dlist_ptr)
