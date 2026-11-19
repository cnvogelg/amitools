from amitools.vamos.libcore import LibImpl
from amitools.vamos.libstructs import (
    DosInfoStruct,
    DosLibraryStruct,
    RootNodeStruct,
)
from amitools.vamos.log import log_dos

from .dos import DeviceProc, Helper, Lock, RecordLock, Timer, Var
from .dos.Args import ArgsMixin
from .dos.Assign import AssignMixin
from .dos.Cli import CliMixin
from .dos.Date import DateMixin
from .dos.DeviceProc import DeviceProcMixin
from .dos.DosFileOpener import DosFileOpener
from .dos.DosList import DosList, DosListMixin
from .dos.DosPacket import DosPacketMixin
from .dos.FileIO import FileIOMixin
from .dos.FileManager import FileManager
from .dos.Helper import HelperMixin
from .dos.Link import LinkMixin
from .dos.Lock import LockMixin
from .dos.LockManager import LockManager
from .dos.MatchFirstNext import MatchFirstNextMixin
from .dos.Notify import NotifyMixin
from .dos.PathPart import PathPartMixin
from .dos.PatternMatch import PatternMatchMixin
from .dos.RecordLock import RecordLockMixin
from .dos.Segments import SegmentsMixin
from .dos.Stdio import StdioMixin
from .dos.Timer import TimerMixin
from .dos.Var import VarMixin
from .dos.Volume import VolumeMixin


class DosLibrary(
    ArgsMixin,
    AssignMixin,
    CliMixin,
    DateMixin,
    DeviceProcMixin,
    DosListMixin,
    DosPacketMixin,
    FileIOMixin,
    HelperMixin,
    LinkMixin,
    LockMixin,
    MatchFirstNextMixin,
    NotifyMixin,
    PathPartMixin,
    PatternMatchMixin,
    RecordLockMixin,
    SegmentsMixin,
    StdioMixin,
    TimerMixin,
    VarMixin,
    VolumeMixin,
    LibImpl,
):
    """dos.library: fd binding via the per-package ``*Mixin`` classes.

    Every fd method lives in the ``dos/`` sub-package that owns the logic
    (HANDLER.md step 22m); this class only wires them together and keeps the
    library lifecycle.
    """

    # variable types/flags live in dos/Var; the fd names are re-exported here
    LV_VAR = Var.LV_VAR  # an variable
    LV_ALIAS = Var.LV_ALIAS  # an alias
    LVF_IGNORE = Var.LVF_IGNORE

    MAX_SHOW_DATA = Helper.MAX_SHOW_DATA

    # dvp_Flags (see dos/dosextens.h) live in dos/DeviceProc
    DVPF_UNLOCK = DeviceProc.DVPF_UNLOCK
    DVPF_ASSIGN = DeviceProc.DVPF_ASSIGN

    def __init__(self):
        super().__init__()
        # these helpers keep state only in the Python process and may be
        # used before setup_lib() (e.g. by tests or a bare LibProxy)
        self.record_locks = RecordLock.RecordLockManager(self)
        self.handler_mgr = None

    def get_struct_def(self):
        return DosLibraryStruct

    def setup_lib(self, ctx, base_addr):
        log_dos.info("setup dos.library")
        # init own state
        self.alloc = ctx.alloc
        self.path_mgr = ctx.path_mgr
        self.io_err = 0
        self.mem_allocs = {}
        self.seg_lists = {}
        self.matches = {}
        self.rdargs = {}
        self.dos_objs = {}
        self.exall_scans = {}
        self.dos_entries = {}
        self.errstrings = {}
        self.resident = []
        self.local_vars = {}
        self.global_vars = {}
        self.record_locks = RecordLock.RecordLockManager(self)
        self.lib_struct = DosLibraryStruct(ctx.mem, base_addr)
        # setup RootNode
        self.root_struct = ctx.alloc.alloc_astruct(RootNodeStruct, label="RootNode")
        self.root_node = self.root_struct
        self.lib_struct.dl_Root.aptr = self.root_struct.addr
        # setup DosInfo
        self.dos_info = ctx.alloc.alloc_astruct(DosInfoStruct, label="DosInfo")
        self.dos_info_struct = self.dos_info
        self.root_node.rn_Info.aptr = self.dos_info.addr
        # file system handlers are built by the caller (main) and passed in
        # via the context; dos.library only consumes them
        self.handler_mgr = ctx.handler_mgr
        # setup dos list
        self.dos_list = DosList(
            self.path_mgr,
            self.path_mgr.assign_mgr,
            ctx.mem,
            ctx.alloc,
            handler_mgr=self.handler_mgr,
        )
        self.dos_list.build_list(ctx.path_mgr)
        self.update_dos_list_head()
        # create file manager
        self.file_mgr = FileManager(
            self.handler_mgr, ctx.exec_lib.port_mgr, ctx.alloc, ctx.mem
        )
        self.dos_list.add_host_devices()
        self.update_dos_list_head()
        # let the segment loader open files through DOS
        if ctx.seg_loader is not None:
            ctx.seg_loader.set_file_opener(DosFileOpener(self.file_mgr))
        # create lock manager
        self.lock_mgr = LockManager(
            ctx.path_mgr,
            self.dos_list,
            ctx.alloc,
            ctx.mem,
            handler_mgr=self.handler_mgr,
        )
        # the packet decoder resolves locks through the lock manager
        self.file_mgr.lock_mgr = self.lock_mgr
        # equip the DosList with all the locks
        self.dos_list.add_locks(self.lock_mgr)
        Timer.setup_timer_request(self, ctx)
        # processes made by CreateNewProc(), by their scheduler task
        self.child_procs = {}
        self.port_mgr = ctx.exec_lib.port_mgr
        if ctx.scheduler is not None:
            ctx.scheduler.set_event_callback(self._child_proc_event)

    def finish_lib(self, ctx):
        Lock.drop_all_exall_scans(self)
        Timer.finish_timer_request(self, ctx)
        # free the child processes that still run
        for child in self.child_procs.values():
            child.free()
        self.child_procs = {}
        # finish file manager
        self.file_mgr.finish()
        # free dos list
        self.dos_list.free_list()
        # free resident nodes
        for res in self.resident:
            self._free_mem(res)
        # free shell variables
        while len(self.local_vars) > 0:
            var = list(self.local_vars.values())[0]
            Var.delete_var_node(self, ctx, var)
        # free RootNode
        self.root_struct.free()
        # free DosInfo
        self.dos_info.free()
