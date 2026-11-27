from .TimerDevice import TimerDevice
from amitools.vamos.libcore import LibImpl
from amitools.vamos.libstructs import (
    ExecLibraryStruct,
    IORequestStruct,
    MsgPortStruct,
    NodeType,
)
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType
from amitools.vamos.log import log_exec
from .lexec.PortManager import PortManager
from .lexec.SemaphoreManager import SemaphoreManager
from .lexec.memheader import AllocatorMemHeader
from .lexec.softint import SoftIntFunc
from .lexec.signalfunc import SignalMixin
from .lexec.interruptfunc import InterruptMixin
from .lexec.taskfunc import TaskMixin
from .lexec.msgfunc import MessageMixin
from .lexec.listfunc import ListMixin
from .lexec.memfunc import MemoryMixin
from .lexec.poolfunc import PoolMixin
from .lexec.modfunc import ModuleMixin
from .lexec.libfunc import LibraryMixin
from .lexec.devicefunc import DeviceMixin
from .lexec.resourcefunc import ResourceMixin
from .lexec.rawiofunc import RawIOMixin
from .lexec.semaphorefunc import SemaphoreMixin
from .lexec.miscfunc import MiscMixin


class ExecLibrary(
    SignalMixin,
    InterruptMixin,
    TaskMixin,
    MessageMixin,
    ListMixin,
    MemoryMixin,
    PoolMixin,
    ModuleMixin,
    LibraryMixin,
    DeviceMixin,
    ResourceMixin,
    RawIOMixin,
    SemaphoreMixin,
    MiscMixin,
    LibImpl,
):
    """the ``exec.library`` implementation.

    the LVO groups live in topic mixins (``lexec/``); this class only carries
    the lifecycle and the shared state (ctx, managers, memory header, ...).
    """

    def get_struct_def(self):
        return ExecLibraryStruct

    def setup_lib(self, ctx, base_addr):
        log_exec.info("setup exec.library")
        self.ctx = ctx
        self.lib_mgr = ctx.lib_mgr
        self.alloc = ctx.alloc
        self.intuition_lib = None
        self.graphics_lib = None
        ctx.exec_lib = self
        self._pools = {}
        self._poolid = 0x1000
        # tasks added via AddTask(): keep the mapped task alive
        self._added_tasks = []
        self.exec_lib = ExecLibraryType(ctx.mem, base_addr)
        # init all exec lists
        self.exec_lib.mem_list.new(NodeType.NT_MEMORY)
        self.exec_lib.resource_list.new(NodeType.NT_RESOURCE)
        self.exec_lib.device_list.new(NodeType.NT_DEVICE)
        self.exec_lib.intr_list.new(NodeType.NT_INTERRUPT)
        self.exec_lib.lib_list.new(NodeType.NT_LIBRARY)
        self.exec_lib.port_list.new(NodeType.NT_MSGPORT)
        self.exec_lib.task_ready.new(NodeType.NT_TASK)
        self.exec_lib.task_wait.new(NodeType.NT_TASK)
        self.exec_lib.semaphore_list.new(NodeType.NT_SEMAPHORE)
        self.exec_lib.mem_handlers.new()
        # set some system contants
        attn_flags = 0
        if ctx.cpu_name == "68030(fake)":
            attn_flags = 7
        elif ctx.cpu_name == "68020":
            attn_flags = 3
        elif ctx.cpu_name == "68040":
            attn_flags = 127
        self.exec_lib.attn_flags.val = attn_flags
        self.exec_lib.max_loc_mem.val = ctx.ram_size
        # Nominal PAL timing; the E-clock counter uses host monotonic time.
        self.exec_lib.VBlankFrequency.val = 50
        self.exec_lib.PowerSupplyFrequency.val = 50
        self.exec_lib.ex_EClockFrequency.val = TimerDevice.ECLOCK_HZ
        # create the managers
        self.port_mgr = PortManager(ctx.alloc)
        self.semaphore_mgr = SemaphoreManager(ctx.alloc, ctx.mem)
        self.mem = ctx.mem
        self.memory_header = AllocatorMemHeader(ctx.alloc, self.exec_lib.mem_list)
        self.soft_int = SoftIntFunc(ctx, base_addr)
        # cache the IORequest/MsgPort field offsets used by the device LVOs
        io_sdef = IORequestStruct.sdef
        msgport_sdef = MsgPortStruct.sdef
        io_msg_off = io_sdef.find_field_def_by_name("io_Message").offset
        io_msg_sdef = io_sdef.find_field_def_by_name("io_Message").type.sdef
        io_msg_node_off = io_msg_sdef.find_field_def_by_name("mn_Node").offset
        io_msg_node_sdef = io_msg_sdef.find_field_def_by_name("mn_Node").type.sdef
        self._io_device_off = io_sdef.find_field_def_by_name("io_Device").offset
        self._io_flags_off = io_sdef.find_field_def_by_name("io_Flags").offset
        self._io_error_off = io_sdef.find_field_def_by_name("io_Error").offset
        self._io_reply_port_off = (
            io_msg_off + io_msg_sdef.find_field_def_by_name("mn_ReplyPort").offset
        )
        self._io_node_type_off = (
            io_msg_off
            + io_msg_node_off
            + io_msg_node_sdef.find_field_def_by_name("ln_Type").offset
        )
        self._msg_port_list_off = msgport_sdef.find_field_def_by_name(
            "mp_MsgList"
        ).offset
        self._msg_port_sigbit_off = msgport_sdef.find_field_def_by_name(
            "mp_SigBit"
        ).offset
        self._msg_port_sigtask_off = msgport_sdef.find_field_def_by_name(
            "mp_SigTask"
        ).offset

    def finish_lib(self, ctx):
        self.memory_header.free()
