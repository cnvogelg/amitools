import struct
from types import SimpleNamespace

import pytest

from amitools.vamos.dos import run_command
from amitools.vamos.libstructs import ProcessStruct
from amitools.vamos.machine import Machine, Runtime, REG_D0, REG_D1, REG_D2, REG_A0
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.task import Stack


@pytest.fixture
def context():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    process_struct = alloc.alloc_astruct(ProcessStruct)
    stack = Stack.alloc(alloc, 4096)
    process_struct.pr_Task.tc_SPLower.aptr = stack.get_lower()
    process_struct.pr_Task.tc_SPUpper.aptr = stack.get_upper()
    ctx = SimpleNamespace(alloc=alloc, odg_base=0)
    process = SimpleNamespace(ctx=ctx, this_task=process_struct)
    yield SimpleNamespace(
        process=process,
        ctx=ctx,
        alloc=alloc,
        machine=machine,
        mem=machine.get_mem(),
        stack=stack,
    )
    process_struct.free()
    stack.free()
    assert alloc.is_all_free()
    machine.cleanup()


def bounds(context):
    task = context.process.this_task.pr_Task
    return task.tc_SPLower.aptr, task.tc_SPUpper.aptr


def dos_run_stack_bounds_test(context):
    before = context.alloc.get_free_bytes()
    original = bounds(context)

    def runner(code):
        lower, upper = bounds(context)
        assert upper - lower == 8192
        assert code.sp == upper - 4
        assert context.mem.r32(upper - 4) == 8192
        assert code.set_regs[REG_D0] == 3
        assert code.set_regs[REG_D1] == 17
        assert code.set_regs[REG_D2] == 8192
        assert code.set_regs[REG_A0] == 0x100
        return SimpleNamespace(regs={REG_D0: 42})

    context.ctx.runner = runner
    assert run_command(context.process, 0x200, 0x100, 3, 8192, 17) == 42
    assert bounds(context) == original
    assert context.alloc.get_free_bytes() == before


def dos_run_exception_restores_stack_test(context):
    before = context.alloc.get_free_bytes()
    original = bounds(context)

    def runner(code):
        raise RuntimeError("command failed")

    context.ctx.runner = runner
    with pytest.raises(RuntimeError, match="command failed"):
        run_command(context.process, 0x200, 0, 0, 8192)
    assert bounds(context) == original
    assert context.alloc.get_free_bytes() == before


def dos_run_nested_stack_test(context):
    before = context.alloc.get_free_bytes()
    original = bounds(context)
    calls = []

    def runner(code):
        calls.append(bounds(context))
        if len(calls) == 1:
            outer = bounds(context)
            assert outer[1] - outer[0] == 8192
            assert run_command(context.process, 0x400, 0, 0, 16384) == 23
            assert bounds(context) == outer
        else:
            inner = bounds(context)
            assert inner[1] - inner[0] == 16384
            assert inner != calls[0]
        return SimpleNamespace(regs={REG_D0: 23})

    context.ctx.runner = runner
    assert run_command(context.process, 0x200, 0, 0, 8192) == 23
    assert len(calls) == 2
    assert bounds(context) == original
    assert context.alloc.get_free_bytes() == before


def dos_run_native_stack_bounds_test(context):
    code = context.alloc.alloc_memory(32)
    record = context.alloc.alloc_memory(12)
    original = bounds(context)
    runtime = Runtime(context.machine)
    context.ctx.runner = runtime.run
    # Record the public tc_SPLower/tc_SPUpper fields and the live SP.
    program = bytes.fromhex("2028003a23c0") + struct.pack(">I", record.addr)
    program += bytes.fromhex("2028003e23c0") + struct.pack(">I", record.addr + 4)
    program += struct.pack(">HI", 0x23CF, record.addr + 8)
    program += bytes.fromhex("702a4e75")
    context.mem.w_block(code.addr, program)
    before = context.alloc.get_free_bytes()
    try:
        task_addr = context.process.this_task.pr_Task.addr
        assert run_command(context.process, code.addr, task_addr, 0, 8192) == 42
        lower = context.mem.r32(record.addr)
        upper = context.mem.r32(record.addr + 4)
        sp = context.mem.r32(record.addr + 8)
        assert upper - lower == 8192
        assert lower <= sp < upper
        assert bounds(context) == original
        assert context.alloc.get_free_bytes() == before
    finally:
        context.alloc.free_memory(code)
        context.alloc.free_memory(record)
