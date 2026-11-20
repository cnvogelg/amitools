"""A Python-task stand-in for a native 68k handler (HANDLER.md step 23).

The :class:`~amitools.vamos.handler.native.manager.NativeHandlerManager` can be
driven without a 68k binary by injecting a ``task_factory`` (see
``NativeHandlerManager(task_factory=...)``). This module provides a small
handler that runs as a *Python* scheduler task and answers the handful of
``ACTION_*`` packets the native-handler tests use. It exercises the whole
transport (message port + signals + reply port) while keeping the tests
deterministic and free of an external assembler.

The harness records what it saw so a test can assert on the startup packet, the
action sequence and the open-lock set.
"""

from amitools.vamos.handler.base import ERROR_OBJECT_IN_USE
from amitools.vamos.handler.native import HandlerProgram
from amitools.vamos.libstructs import InfoDataStruct
from amitools.vamos.libtypes import DosPacket, MsgPort
from amitools.vamos.task import ExecTask

# the DOS actions the tiny handler understands (dos/dos.h)
ACTION_STARTUP = 0
ACTION_DIE = 5
ACTION_LOCATE_OBJECT = 8
ACTION_FREE_LOCK = 15
ACTION_EXAMINE_OBJECT = 23
ACTION_DISK_INFO = 25
ACTION_INFO = 26
ERROR_ACTION_NOT_KNOWN = 209

# the synthetic geometry the harness reports for ACTION_INFO/DISK_INFO
INFO_NUM_BLOCKS = 1000
INFO_NUM_BLOCKS_USED = 250
INFO_BYTES_PER_BLOCK = 512
INFO_DISK_TYPE = 0x444F5303  # 'DOS\3' (international FFS)
INFO_DISK_STATE = 82  # HandlerInfoData.DISK_STATE_VALIDATED


class _Owner:
    """frees the Python task and the handler port it allocated"""

    def __init__(self, task, port):
        self.task = task
        self.port = port

    def free(self):
        if self.task is not None:
            self.task.free()
            self.task = None
        if self.port is not None:
            self.port.free()
            self.port = None


class TaskHandler:
    """a callable ``task_factory`` that serves packets from a Python task

    ``startup_pkt`` is the raw startup ``DosPacket``; ``actions`` is the list of
    action codes in the order they arrived; ``locks`` maps a fake lock BPTR to
    the requested path. ``next_lock`` is the BPTR the next locate returns.
    """

    def __init__(self):
        self.port = None
        self.mem = None
        self.actions = []
        self.locks = {}
        self.next_lock = 1
        self.startup_pkt = None
        self.exit_code = None
        # a test may clear this to simulate a handler that stops answering
        self.reply = True

    # ----- the task factory -----

    def __call__(self, manager, handler):
        alloc = manager.alloc
        machine = manager.machine
        messages = manager.exec_impl.msg_func
        mem = alloc.get_mem()
        self.mem = mem
        self.port = MsgPort.alloc(alloc)
        self.port.new()

        def run(task):
            return self._serve(messages, mem)

        task = ExecTask(machine, alloc, "task_handler", func=run)
        return HandlerProgram(
            task.get_sched_task(),
            task.get_ami_task(),
            self.port,
            owner=_Owner(task, self.port),
        )

    # ----- the handler loop -----

    def _serve(self, messages, mem):
        while True:
            msg = messages.wait_port(self.port)
            messages.get_msg(self.port)
            pkt = DosPacket(mem, msg.node.name.aptr)
            action = pkt.type.val
            self.actions.append(action)
            keep_running = self._handle(pkt, action)
            if self.reply:
                messages.reply_msg(msg)
            if not keep_running:
                return 0

    def _handle(self, pkt, action):
        if action == ACTION_STARTUP:
            self.startup_pkt = pkt
            pkt.res1.val = 1
            pkt.res2.val = 0
        elif action == ACTION_DIE:
            if self.locks:
                pkt.res1.val = 0
                pkt.res2.val = ERROR_OBJECT_IN_USE
                return True
            pkt.res1.val = 1
            pkt.res2.val = 0
            return False
        elif action == ACTION_LOCATE_OBJECT:
            bptr = self.next_lock
            self.next_lock += 1
            self.locks[bptr] = pkt.arg2.val
            pkt.res1.val = bptr
            pkt.res2.val = 0
        elif action == ACTION_FREE_LOCK:
            self.locks.pop(pkt.arg1.val, None)
            pkt.res1.val = 1
            pkt.res2.val = 0
        elif action == ACTION_EXAMINE_OBJECT:
            pkt.res1.val = 1
            pkt.res2.val = 0
        elif action == ACTION_INFO:
            # arg2 is a BPTR to the caller's InfoData
            self._write_info(pkt.arg2.val << 2)
            pkt.res1.val = 1
            pkt.res2.val = 0
        elif action == ACTION_DISK_INFO:
            # arg1 is a BPTR to the caller's InfoData (no lock)
            self._write_info(pkt.arg1.val << 2)
            pkt.res1.val = 1
            pkt.res2.val = 0
        else:
            pkt.res1.val = 0
            pkt.res2.val = ERROR_ACTION_NOT_KNOWN
        return True

    def _write_info(self, info_addr):
        info = InfoDataStruct(self.mem, info_addr)
        info.id_NumSoftErrors.val = 0
        info.id_UnitNumber.val = 0
        info.id_DiskState.val = INFO_DISK_STATE
        info.id_NumBlocks.val = INFO_NUM_BLOCKS
        info.id_NumBlocksUsed.val = INFO_NUM_BLOCKS_USED
        info.id_BytesPerBlock.val = INFO_BYTES_PER_BLOCK
        info.id_DiskType.val = INFO_DISK_TYPE
        info.id_InUse.val = 0
