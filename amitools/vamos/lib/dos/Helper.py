"""Generic helpers shared by the dos.library fd modules.

These are the small building blocks every front-end needs: the callee-pc log
helper, the current-directory/home-directory lookups, the DOS list head
publisher, the DOSTRUE/DOSFALSE error mapper, the ``setioerr`` setter, the
message unlink helper and the DOS-internal memory allocator/bookkeeper.

``DosLibrary`` keeps the same method names as one-line delegating wrappers so
the other ``dos/`` modules and the tests can keep calling ``dos._alloc_mem``,
``dos.get_current_dir``, ``dos.setioerr``, ... unchanged.
"""

from amitools.vamos.error import VamosInternalError
from amitools.vamos.log import log_dos
from amitools.vamos.machine.regs import REG_A7
from amitools.vamos.schedule import SchedulerEvent

from .Error import DOSFALSE, DOSTRUE

# truncate logged buffers (shared by the file I/O and stdio modules)
MAX_SHOW_DATA = 32


def get_callee_pc(dos, ctx):
    """a call stub log helper to extract the callee's pc"""
    sp = ctx.cpu.r_reg(REG_A7)
    return ctx.mem.r32(sp)


def get_current_dir(dos, ctx):
    cur_dir = ctx.process.get_current_dir()
    return dos.lock_mgr.get_by_b_addr(cur_dir >> 2)


def get_home_dir(dos, ctx):
    """Get the program's home directory lock (PROGDIR:)"""
    home_dir = ctx.process.get_home_dir()
    return dos.lock_mgr.get_by_b_addr(home_dir >> 2)


def get_cwd_path(dos, ctx):
    """Amiga path of the current directory lock (or None)"""
    cur_dir = get_current_dir(dos, ctx)
    return cur_dir.ami_path if cur_dir is not None else None


def update_dos_list_head(dos):
    """Publish the current DOS list head through DOSBase."""
    head_addr = dos.dos_list.get_head_addr()
    dos.dos_info.di_DevInfo.aptr = head_addr
    return head_addr


def bool_result(dos, ctx, ok, err):
    dos.setioerr(ctx, 0 if ok else err)
    return DOSTRUE if ok else DOSFALSE


def set_io_err(dos, ctx, err):
    dos.io_err = err
    process = ctx.process
    if process is None:
        return
    amiga_process = getattr(process, "this_task", None)
    if amiga_process is None:
        amiga_process = getattr(process, "ami_proc", None)
    if amiga_process is not None:
        amiga_process.pr_Result2.val = err


def unlink_msg(dos, ctx, msg_addr):
    """unlink a message node from its list, ignoring a broken chain"""
    try:
        ln_succ = ctx.mem.r32(msg_addr + 0)
        ln_pred = ctx.mem.r32(msg_addr + 4)
        if ln_succ != 0 and ln_pred != 0:
            ctx.mem.w32(ln_pred + 0, ln_succ)
            ctx.mem.w32(ln_succ + 4, ln_pred)
    except Exception:
        pass


def alloc_mem(dos, name, size):
    mem = dos.alloc.alloc_memory(size, label=name)
    dos.mem_allocs[mem.addr] = mem
    return mem.addr


def free_mem(dos, addr):
    if addr in dos.mem_allocs:
        mem = dos.mem_allocs[addr]
        dos.alloc.free_memory(mem)
        del dos.mem_allocs[addr]
    else:
        raise VamosInternalError(f"Invalid DOS free mem: {addr:06x}")


def create_child_process(dos, ctx, name, **kw_args):
    """the process CreateNewProc() makes: a DosProcess by default.

    an embedder may return a subclass that serves the DOS calls of a
    process vamos did not load as a program.
    """
    from amitools.vamos.task import DosProcess

    return DosProcess(ctx.machine, ctx.alloc, name, **kw_args)


def child_proc_event(dos, event):
    """free a process made by CreateNewProc() once its task has ended"""
    if event.type != SchedulerEvent.Type.REMOVE_TASK:
        return
    child = dos.child_procs.pop(event.task, None)
    if child is None:
        return
    port_addr = child.proc.msg_port.addr
    if dos.port_mgr.has_port(port_addr):
        dos.port_mgr.unregister_port(port_addr)
    log_dos.info("CreateNewProc: process %06x ended", child.proc.addr)
    child.free()


class HelperMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def update_dos_list_head(self):
        return update_dos_list_head(self)

    def get_callee_pc(self, ctx):
        """a call stub log helper to extract the callee's pc"""
        return get_callee_pc(self, ctx)

    def get_current_dir(self, ctx):
        return get_current_dir(self, ctx)

    def get_home_dir(self, ctx):
        """Get the program's home directory lock (PROGDIR:)"""
        return get_home_dir(self, ctx)

    def get_cwd_path(self, ctx):
        """Amiga path of the current directory lock (or None)"""
        return get_cwd_path(self, ctx)

    def setioerr(self, ctx, err):
        return set_io_err(self, ctx, err)

    def _alloc_mem(self, name, size):
        return alloc_mem(self, name, size)

    def _free_mem(self, addr):
        return free_mem(self, addr)

    def create_child_process(self, ctx, name, **kw_args):
        """the process CreateNewProc() makes: a DosProcess by default.

        an embedder may return a subclass that serves the DOS calls of a
        process vamos did not load as a program.
        """
        return create_child_process(self, ctx, name, **kw_args)

    def _child_proc_event(self, event):
        """free a process made by CreateNewProc() once its task has ended"""
        return child_proc_event(self, event)
