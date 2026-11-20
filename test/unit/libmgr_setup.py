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


def libmgr_setup_lifecycle_callbacks_test():
    """post_setup runs once the base libs are live; pre_shutdown is idempotent."""
    machine = Machine()
    runtime = Runtime(machine)
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    scheduler = Scheduler(machine)
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, PathManager())
    slm.setup()
    events = []
    slm.add_post_setup_callback(lambda lib_mgr: events.append(("post", lib_mgr)))
    slm.add_pre_shutdown_callback(lambda lib_mgr: events.append(("pre", lib_mgr)))

    slm.open_base_libs()
    # post_setup ran once, at the end of open_base_libs
    assert events == [("post", slm)]

    slm.close_base_libs()
    # pre_shutdown ran before the base libs closed ...
    assert events[-1] == ("pre", slm)

    slm.cleanup()
    # ... and again from cleanup, so the hooks must be idempotent
    assert events.count(("post", slm)) == 1
    assert events.count(("pre", slm)) == 2


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
