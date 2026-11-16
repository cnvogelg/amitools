from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.libtypes import Message
from amitools.vamos.machine import Machine, MemoryMap, Runtime
from amitools.vamos.path import PathManager
from amitools.vamos.schedule import Scheduler, TaskState
from amitools.vamos.task import ExecTask


def libmgr_setup_default_test():
    machine = Machine()
    runtime = Runtime(machine)
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    scheduler = Scheduler(machine)
    path_mgr = PathManager()
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, path_mgr)
    slm.setup()
    slm.open_base_libs()
    slm.close_base_libs()
    slm.cleanup()


def libmgr_setup_shutdown_helper_test(monkeypatch):
    machine = Machine()
    runtime = Runtime(machine)
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    scheduler = Scheduler(machine)
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, PathManager())
    slm.setup()
    slm.open_base_libs()
    messages = slm.exec_impl.msg_func
    ports = []
    events = []

    def helper_func(task):
        port = messages.create_msg_port()
        ports.append(port)
        messages.wait_port(port)
        message = messages.get_msg(port)
        events.append("received")
        messages.reply_msg(message)
        messages.delete_msg_port(port)
        return 0

    helper = ExecTask(machine, slm.alloc, "Clipboard helper", func=helper_func)
    scheduler.add_task(helper.get_sched_task())
    scheduler.run_until_idle()

    def shutdown():
        events.append("expunge")
        reply = messages.create_msg_port()
        message = Message.alloc(slm.alloc)
        message.new(reply_port=reply)
        messages.put_msg(ports[0], message)
        messages.wait_port(reply)
        assert messages.get_msg(reply).addr == message.addr
        events.append("acknowledged")
        message.free()
        messages.delete_msg_port(reply)
        return 0

    monkeypatch.setattr(slm.lib_mgr.alib_mgr, "shutdown", shutdown)
    slm.close_base_libs()
    slm.cleanup()
    assert events == ["expunge", "received", "acknowledged"]
    assert helper.get_sched_task().get_state() == TaskState.TS_REMOVED
    helper.free()
    assert slm.alloc.is_all_free()
