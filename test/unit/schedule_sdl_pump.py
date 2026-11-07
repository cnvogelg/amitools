import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.machine import Code, Machine, REG_D0
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, SchedulerConfig, PythonTask, NativeTask
from amitools.vamos.schedule.task import TaskState


@pytest.fixture
def pump(monkeypatch):
    lib = ExecLibrary()
    lib.intuition_lib = SimpleNamespace(
        sdl_window_id_2_sdl_window={7: 7},
        check_refresh=Mock(),
        ingest_sdl_event=Mock(return_value=None),
        drain_pending_intui_events=Mock(),
    )
    sdl = SimpleNamespace(
        SDL_Event=SimpleNamespace,
        SDL_PollEvent=Mock(return_value=0),
        SDL_WaitEventTimeout=Mock(return_value=0),
    )
    monkeypatch.setitem(sys.modules, "sdl2", sdl)
    return lib, sdl


@pytest.mark.parametrize("queued", [0, 1], ids=["empty", "ignored-flood"])
def schedule_sdl_bounded_poll_test(pump, queued):
    lib, sdl = pump
    calls = 0

    def poll(event):
        nonlocal calls
        calls += 1
        assert calls < 1000, "event pump did not yield"
        return queued

    sdl.SDL_PollEvent = poll
    assert lib._wait_core(None)
    assert 0 < calls < 1000
    sdl.SDL_WaitEventTimeout.assert_not_called()
    lib.intuition_lib.check_refresh.assert_called_once_with(None)


def schedule_sdl_dispatch_batch_test(pump):
    lib, sdl = pump
    first, second = object(), object()
    sdl.SDL_PollEvent.side_effect = [1, 1, 1, 1, 0]
    lib.intuition_lib.ingest_sdl_event.side_effect = [None, first, None, second]
    assert lib._wait_core(None)
    assert [
        call.args[1]
        for call in lib.intuition_lib.drain_pending_intui_events.call_args_list
    ] == [first, second]
    sdl.SDL_WaitEventTimeout.assert_not_called()


def schedule_sdl_idle_wait_test(pump):
    lib, sdl = pump
    pending = object()
    sdl.SDL_WaitEventTimeout.return_value = 1
    lib.intuition_lib.ingest_sdl_event.return_value = pending
    assert lib._wait_core(None, wait=True)
    assert sdl.SDL_WaitEventTimeout.call_args.args[1] > 0
    lib.intuition_lib.drain_pending_intui_events.assert_called_once_with(None, pending)


@pytest.mark.parametrize("absent", [False, True])
def schedule_sdl_no_source_test(pump, absent):
    lib, sdl = pump
    if absent:
        lib.intuition_lib = None
    else:
        lib.intuition_lib.sdl_window_id_2_sdl_window.clear()
    assert lib._wait_core(None) is False
    sdl.SDL_PollEvent.assert_not_called()
    sdl.SDL_WaitEventTimeout.assert_not_called()


def schedule_sdl_no_scheduler_test():
    lib = ExecLibrary()
    lib.signal_func = SimpleNamespace(get_my_sched_task=lambda: None)
    lib.register_SDL_poll(None)


@pytest.fixture
def context():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    scheduler = Scheduler(machine, SchedulerConfig(slice_cycles=40))
    owned = []

    def python(name, function):
        stack = alloc.alloc_memory(4096)
        owned.append(stack)
        task = PythonTask(name, machine, function, stack.addr + stack.size)
        scheduler.add_task(task)
        return task

    ctx = SimpleNamespace(
        machine=machine, alloc=alloc, scheduler=scheduler, python=python, owned=owned
    )
    yield ctx
    for memory in reversed(owned):
        alloc.free_memory(memory)
    assert alloc.is_all_free()
    machine.cleanup()


@pytest.mark.parametrize("source_alive", [False, True])
def schedule_sdl_runnable_task_test(context, source_alive):
    scheduler = context.scheduler
    polls = 0

    def poll():
        nonlocal polls
        polls += 1
        assert polls < 100, "pump kept scheduler alive after the last task ended"
        return source_alive

    def run(task):
        for _ in range(3):
            task.reschedule()
        return 42

    task = context.python("running", run)
    scheduler.message_pump = poll
    scheduler.message_wait = Mock(side_effect=AssertionError("wait while runnable"))
    assert scheduler.schedule()
    assert task.get_exit_code() == 42
    assert polls > 1
    assert not scheduler.running
    scheduler.message_wait.assert_not_called()


@pytest.mark.parametrize("source_alive", [False, True])
def schedule_sdl_wake_current_task_test(context, source_alive):
    scheduler = context.scheduler

    def run(task):
        assert task.wait(1) == 1
        assert task.get_state() == TaskState.TS_RUN
        return 42

    task = context.python("waiting", run)
    waits = 0

    def wait():
        nonlocal waits
        waits += 1
        assert waits == 1
        assert task.get_state() == TaskState.TS_WAIT
        task.set_signal(1, 1)
        return source_alive

    scheduler.message_pump = lambda: True
    scheduler.message_wait = wait
    assert scheduler.schedule()
    assert task.get_exit_code() == 42
    assert waits == 1


def schedule_sdl_wake_other_task_test(context):
    scheduler = context.scheduler
    resumed = []

    def run(task):
        assert task.wait(1) == 1
        assert task.get_state() == TaskState.TS_RUN
        resumed.append(task.name)
        return 42

    first = context.python("first", run)
    second = context.python("second", run)
    waits = 0

    def wait():
        nonlocal waits
        waits += 1
        assert waits <= 2
        assert not scheduler.ready_tasks
        waiting = scheduler.waiting_tasks[0]
        waiting.set_signal(1, 1)
        return True

    scheduler.message_pump = lambda: True
    scheduler.message_wait = wait
    assert scheduler.schedule()
    assert first.get_exit_code() == second.get_exit_code() == 42
    assert resumed == ["first", "second"]


def schedule_sdl_poll_exception_test(context):
    scheduler = context.scheduler
    context.python("not-started", lambda task: 0)
    scheduler.message_pump = Mock(side_effect=RuntimeError("poll failed"))
    with pytest.raises(RuntimeError, match="poll failed"):
        scheduler.schedule()
    assert not scheduler.running


def schedule_sdl_native_progress_test(context, pump):
    lib, sdl = pump
    scheduler = context.scheduler
    memory = context.machine.get_mem()
    program = bytes.fromhex("4e71") * 300 + bytes.fromhex("702a4e75")
    code = context.alloc.alloc_memory(len(program))
    stack = context.alloc.alloc_memory(4096)
    context.owned.extend([code, stack])
    memory.w_block(code.addr, program)
    native = NativeTask(
        "native",
        context.machine,
        Code(code.addr, stack.addr + stack.size, get_regs=[REG_D0]),
    )
    scheduler.add_task(native)
    batches = 0

    def pump_batch():
        nonlocal batches
        batches += 1
        calls = 0

        def ignored(event):
            nonlocal calls
            calls += 1
            assert calls < 1000, "event flood starved native execution"
            return 1

        sdl.SDL_PollEvent = ignored
        return lib._wait_core(None)

    scheduler.message_pump = pump_batch
    scheduler.message_wait = Mock(side_effect=AssertionError("native task is runnable"))
    assert scheduler.schedule()
    assert native.get_exit_code() == 42
    assert batches > 1
    scheduler.message_wait.assert_not_called()


def schedule_sdl_run_until_idle_never_waits_test(context):
    from amitools.vamos.schedule import RunResult
    scheduler = context.scheduler
    def run(task):
        assert task.wait(1) == 1
        return 42
    task = context.python('external-wakeup', run)
    scheduler.message_pump = Mock(return_value=True)
    scheduler.message_wait = Mock(side_effect=AssertionError('blocking idle API'))
    assert scheduler.run_until_idle() == RunResult.IDLE
    assert not scheduler.running
    scheduler.message_wait.assert_not_called()
    task.set_signal(1, 1)
    assert scheduler.run_until_idle() == RunResult.DONE
    assert task.get_exit_code() == 42


def schedule_sdl_cycle_budget_still_limits_native_task_test(context):
    from amitools.vamos.schedule import RunResult
    memory = context.machine.get_mem()
    program = bytes.fromhex('4e71') * 200 + bytes.fromhex('702a4e75')
    code = context.alloc.alloc_memory(len(program))
    stack = context.alloc.alloc_memory(4096)
    context.owned.extend([code, stack])
    memory.w_block(code.addr, program)
    task = NativeTask('budgeted', context.machine,
                      Code(code.addr, stack.addr + stack.size, get_regs=[REG_D0]))
    context.scheduler.add_task(task)
    context.scheduler.message_pump = Mock(return_value=True)
    context.scheduler.message_wait = Mock(side_effect=AssertionError('budget API wait'))
    outcomes = []
    for _ in range(100):
        result = context.scheduler.run_until_idle(max_cycles=40)
        outcomes.append(result)
        if result == RunResult.DONE:
            break
        assert result == RunResult.BUSY
    assert RunResult.BUSY in outcomes and outcomes[-1] == RunResult.DONE
    assert task.get_exit_code() == 42
    context.scheduler.message_wait.assert_not_called()
