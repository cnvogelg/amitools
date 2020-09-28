import pytest
import traceback
import sys
from musashi import emu
from musashi.m68k import *


def musashi_traps_trigger_test():
    traps = emu.Traps()
    a = []

    def my_func(opcode, pc):
        a.append(opcode)
        a.append(pc)

    tid = traps.setup(my_func)
    assert tid >= 0
    traps.trigger(tid, 23)
    assert a == [tid, 23]
    traps.free(tid)


def musashi_traps_raise_test():
    traps = emu.Traps()
    a = []
    b = []

    def exc_func(opcode, pc):
        a.append(opcode)
        a.append(pc)
        b.append(sys.exc_info())

    traps.set_exc_func(exc_func)

    def my_func(opcode, pc):
        raise ValueError("bla")

    tid = traps.setup(my_func)
    assert tid >= 0
    traps.trigger(tid, 23)
    assert a == [tid, 23]
    assert b[0][0] == ValueError
    traps.free(tid)
