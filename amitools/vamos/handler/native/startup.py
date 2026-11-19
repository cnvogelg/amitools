"""Startup marshalling for a native (68k) AmigaDOS handler.

A handler is started exactly like AmigaDOS starts one: the handler binary is
loaded as a seglist, a process is created from it, and the *startup packet*
(``ACTION_STARTUP``) is sent to the process's ``pr_MsgPort``. The packet
carries the device node (a ``DosListDeviceStruct``) whose ``dol_Startup``
points at a ``FileSysStartupMsg`` with the ``DosEnvec`` describing the volume.

This module owns the memory structures of that handshake:

* :func:`build_startup` allocates the ``FileSysStartupMsg`` + ``DosEnvec`` and
  the device-name BSTR (mirroring ``DiskSession`` for the RDB partitions);
* :func:`configure_handler_port` turns a ``MsgPort`` into a real Exec signal
  port bound to the handler task;
* :func:`add_device_node` publishes the device in the DOS list.

Everything allocated here is released by the returned
:class:`StartupResources` so the manager can tear a handler down again.
"""

from amitools.vamos.libstructs import (
    DosEnvecStruct,
    FileSysStartupMsgStruct,
    MsgPortFlags,
    NodeType,
)

# AmigaDOS handler startup/shutdown packet types
ACTION_STARTUP = 0
ACTION_DIE = 5

# the handler's pr_MsgPort is signalled with SIGB_DOS, exactly like a process
# port (see dos/Cli.py). Bits 0..15 are reserved per task (Task.new_task sets
# sig_alloc to 0xFFFF), so this never clashes with AllocSignal(-1).
SIGB_DOS = 8

# the device node type (dos/dosextens.h: DLT_DEVICE)
DLT_DEVICE = 0

# dol_GlobVec markers for C and assembler handlers (dos/dosextens.h)
GLOBVEC_ASM = -2
GLOBVEC_C = -1


def _set_field(struct, name, value):
    field = getattr(struct, name)
    if hasattr(field, "val"):
        field.val = value
    elif hasattr(field, "aptr"):
        field.aptr = value
    elif hasattr(field, "bptr"):
        field.bptr = value
    else:
        field.set(value)


class StartupResources:
    """the memory a started handler's startup handshake owns"""

    def __init__(self, alloc, startup, env, device_name):
        self.alloc = alloc
        self.startup = startup
        self.env = env
        self.device_name = device_name

    def free(self):
        if self.startup is not None:
            self.startup.free()
            self.startup = None
        if self.env is not None:
            self.env.free()
            self.env = None
        if self.device_name is not None:
            self.alloc.free_bstr(self.device_name)
            self.device_name = None


def build_startup(alloc, unit, device, geometry):
    """allocate ``FileSysStartupMsg`` + ``DosEnvec`` for a handler

    ``geometry`` is any object exposing the ``DosEnvec`` fields (the
    ``DiskPartition.dos_env`` of an RDB partition, or a synthetic geometry).
    Returns a :class:`StartupResources`; the caller frees it with ``free()``.
    """
    env = alloc.alloc_astruct(DosEnvecStruct, label="NativeDosEnvec")
    # map the DosEnvec fields onto the geometry attribute names used by the
    # disk session (``DiskPartition.dos_env``)
    values = {
        "de_TableSize": getattr(geometry, "size", 0) or 16,
        "de_SizeBlock": geometry.block_size,
        "de_SecOrg": geometry.sec_org,
        "de_Surfaces": geometry.surfaces,
        "de_SectorPerBlock": geometry.sec_per_blk,
        "de_BlocksPerTrack": geometry.blk_per_trk,
        "de_Reserved": geometry.reserved,
        "de_PreAlloc": geometry.pre_alloc,
        "de_Interleave": geometry.interleave,
        "de_LowCyl": geometry.low_cyl,
        "de_HighCyl": geometry.high_cyl,
        "de_NumBuffers": geometry.num_buffer,
        "de_BufMemType": geometry.buf_mem_type,
        "de_MaxTransfer": geometry.max_transfer,
        "de_Mask": geometry.mask,
        "de_BootPri": geometry.boot_pri,
        "de_DosType": geometry.dos_type,
        "de_Baud": geometry.baud,
        "de_Control": geometry.control,
        "de_BootBlocks": geometry.boot_blocks,
    }
    for name, value in values.items():
        _set_field(env, name, value or 0)

    device_name = alloc.alloc_bstr(device, label="NativeDeviceName")
    startup = None
    try:
        startup = alloc.alloc_astruct(
            FileSysStartupMsgStruct, label="NativeFileSysStartupMsg"
        )
        _set_field(startup, "fssm_Unit", unit)
        _set_field(startup, "fssm_Device", device_name.addr)
        _set_field(startup, "fssm_Environ", env.addr)
        _set_field(startup, "fssm_Flags", 0)
        return StartupResources(alloc, startup, env, device_name)
    except Exception:
        env.free()
        alloc.free_bstr(device_name)
        raise


def configure_handler_port(port, sig_bit, task_addr):
    """turn ``port`` into a real Exec signal port for the handler task

    Sets ``PA_SIGNAL``, the allocated signal bit and the task to signal, and
    initialises the message list. The port is *not* registered in the
    ``PortManager``: it must take the Exec signal path (see the transport).
    """
    port.pri.val = 0
    port.node.type.val = NodeType.NT_MSGPORT
    port.flags.val = MsgPortFlags.PA_SIGNAL
    port.sig_bit.val = sig_bit
    port.sig_task.aptr = task_addr
    port.msg_list.new(NodeType.NT_MESSAGE)
    return port


def add_device_node(
    dos_list,
    name,
    startup_bptr,
    task,
    seg_list=0,
    glob_vec=0,
    handler=0,
):
    """publish a started handler as a ``DLT_DEVICE`` DOS list entry

    ``task`` is the handler's ``pr_MsgPort`` address (``dol_Task``),
    ``seg_list`` the loaded seglist BPTR and ``handler`` the BSTR BPTR of the
    binary name. Returns the created entry.
    """
    return dos_list.add_device(
        name,
        startup_bptr,
        task=task,
        seg_list=seg_list,
        glob_vec=glob_vec,
        handler=handler,
    )
