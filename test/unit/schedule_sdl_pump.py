import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
from amitools.vamos.display.sdl import SDLDisplay
from amitools.vamos.machine import Code, Machine, REG_D0
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, SchedulerConfig, PythonTask, NativeTask
from amitools.vamos.schedule.task import TaskState


@pytest.fixture
def pump(monkeypatch):
    lib = IntuitionLibrary()
    lib.host_windows = {7: 7}
    lib.check_refresh = Mock()
    lib.ingest_event = Mock(return_value=None)
    lib.drain_pending_intui_events = Mock()
    lib.display = SDLDisplay()
    lib.display.convert_event = Mock(return_value=object())
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
    ctx = SimpleNamespace(cpu=Mock())
    assert lib._pump_display(ctx)
    assert 0 < calls < 1000
    sdl.SDL_WaitEventTimeout.assert_not_called()
    lib.check_refresh.assert_called_once_with(ctx)
    ctx.cpu.set_cpu_context.assert_called_once_with(ctx.cpu.get_cpu_context.return_value)


def schedule_sdl_dispatch_batch_test(pump):
    lib, sdl = pump
    first, second = object(), object()
    sdl.SDL_PollEvent.side_effect = [1, 1, 1, 1, 0]
    lib.ingest_event.side_effect = [None, first, None, second]
    ctx = SimpleNamespace(cpu=Mock())
    assert lib._pump_display(ctx)
    assert [
        call.args[1]
        for call in lib.drain_pending_intui_events.call_args_list
    ] == [first, second]
    sdl.SDL_WaitEventTimeout.assert_not_called()


def schedule_sdl_idle_wait_test(pump):
    lib, sdl = pump
    pending = object()
    sdl.SDL_WaitEventTimeout.return_value = 1
    lib.ingest_event.return_value = pending
    ctx = SimpleNamespace(cpu=Mock())
    assert lib._pump_display(ctx, wait=True)
    assert sdl.SDL_WaitEventTimeout.call_args.args[1] > 0
    lib.drain_pending_intui_events.assert_called_once_with(ctx, pending)


def schedule_display_no_source_test(pump):
    lib, sdl = pump
    lib.host_windows.clear()
    ctx = SimpleNamespace(cpu=Mock())
    assert lib._pump_display(ctx) is False
    sdl.SDL_PollEvent.assert_not_called()
    sdl.SDL_WaitEventTimeout.assert_not_called()


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
    scheduler.add_after_schedule_callback(poll)
    idle_wait = Mock(side_effect=AssertionError("wait while runnable"))
    scheduler.add_idle_callback(idle_wait)
    assert scheduler.schedule()
    assert task.get_exit_code() == 42
    assert polls > 1
    assert not scheduler.running
    idle_wait.assert_not_called()


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

    scheduler.add_after_schedule_callback(lambda: True)
    idle_wait = wait
    scheduler.add_idle_callback(idle_wait)
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

    scheduler.add_after_schedule_callback(lambda: True)
    idle_wait = wait
    scheduler.add_idle_callback(idle_wait)
    assert scheduler.schedule()
    assert first.get_exit_code() == second.get_exit_code() == 42
    assert resumed == ["first", "second"]


def schedule_sdl_poll_exception_test(context):
    scheduler = context.scheduler
    context.python("not-started", lambda task: 0)
    scheduler.add_after_schedule_callback(Mock(side_effect=RuntimeError("poll failed")))
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
        return lib._pump_display(SimpleNamespace(cpu=Mock()))

    scheduler.add_after_schedule_callback(pump_batch)
    idle_wait = Mock(side_effect=AssertionError("native task is runnable"))
    scheduler.add_idle_callback(idle_wait)
    assert scheduler.schedule()
    assert native.get_exit_code() == 42
    assert batches > 1
    idle_wait.assert_not_called()


def schedule_sdl_run_until_idle_never_waits_test(context):
    from amitools.vamos.schedule import RunResult

    scheduler = context.scheduler

    def run(task):
        assert task.wait(1) == 1
        return 42

    task = context.python("external-wakeup", run)
    scheduler.add_after_schedule_callback(Mock(return_value=True))
    idle_wait = Mock(side_effect=AssertionError("blocking idle API"))
    scheduler.add_idle_callback(idle_wait)
    assert scheduler.run_until_idle() == RunResult.IDLE
    assert not scheduler.running
    idle_wait.assert_not_called()
    task.set_signal(1, 1)
    assert scheduler.run_until_idle() == RunResult.DONE
    assert task.get_exit_code() == 42


def schedule_sdl_cycle_budget_still_limits_native_task_test(context):
    from amitools.vamos.schedule import RunResult

    memory = context.machine.get_mem()
    program = bytes.fromhex("4e71") * 200 + bytes.fromhex("702a4e75")
    code = context.alloc.alloc_memory(len(program))
    stack = context.alloc.alloc_memory(4096)
    context.owned.extend([code, stack])
    memory.w_block(code.addr, program)
    task = NativeTask(
        "budgeted",
        context.machine,
        Code(code.addr, stack.addr + stack.size, get_regs=[REG_D0]),
    )
    context.scheduler.add_task(task)
    context.scheduler.add_after_schedule_callback(Mock(return_value=True))
    idle_wait = Mock(side_effect=AssertionError("budget API wait"))
    context.scheduler.add_idle_callback(idle_wait)
    outcomes = []
    for _ in range(100):
        result = context.scheduler.run_until_idle(max_cycles=40)
        outcomes.append(result)
        if result == RunResult.DONE:
            break
        assert result == RunResult.BUSY
    assert RunResult.BUSY in outcomes and outcomes[-1] == RunResult.DONE
    assert task.get_exit_code() == 42
    idle_wait.assert_not_called()


def schedule_multiple_callbacks_and_removal_test(context):
    scheduler = context.scheduler
    called = []
    def first():
        called.append("first")
        scheduler.remove_after_schedule_callback(first)
        scheduler.remove_after_schedule_callback(removed)
        scheduler.add_after_schedule_callback(added)
        return True
    def removed():
        called.append("removed")
    def added():
        called.append("added")
    def second():
        called.append("second")
    for callback in (first, removed, second, first):
        scheduler.add_after_schedule_callback(callback)
    context.python("task", lambda task: 0)
    assert scheduler.schedule()
    assert called == ["first", "second", "second", "added"]
    assert not scheduler.running


def schedule_idle_calls_all_sources_test(context):
    scheduler = context.scheduler
    calls = []
    a = lambda: calls.append("a") or True
    b = lambda: calls.append("b") or False
    scheduler.add_idle_callback(a)
    scheduler.add_idle_callback(a)
    scheduler.add_idle_callback(b)
    assert scheduler._call_callbacks(scheduler.idle_callbacks)
    assert calls == ["a", "b"]
    scheduler.remove_idle_callback(a)
    scheduler.remove_idle_callback(b)
    assert not scheduler.idle_callbacks


def schedule_gadget_callback_restores_cpu_on_failure_test(pump):
    lib, _ = pump
    ctx = SimpleNamespace(cpu=Mock())
    saved = ctx.cpu.get_cpu_context.return_value
    lib._pump_display_events = Mock(side_effect=ValueError("guest hook failed"))
    with pytest.raises(ValueError, match="guest hook failed"):
        lib._pump_display(ctx)
    ctx.cpu.set_cpu_context.assert_called_once_with(saved)
