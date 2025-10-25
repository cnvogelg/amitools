from amitools.vamos.machine.mock import MockTraps


def mock_traps_base_test():
    t = MockTraps()
    a = []

    def my_func(op, pc):
        assert op == 0xA000
        assert pc == 0x42
        a.append("huhu")

    assert t.get_num_traps() == 0
    tid = t.alloc(my_func)
    assert t.get_num_traps() == 1
    assert t.get_func(tid) == my_func
    assert not t.is_old_pc(tid)
    t.trigger(tid, pc=0x42)
    assert a == ["huhu"]
    t.free(tid)
    assert t.get_num_traps() == 0


def mock_traps_old_pc_test():
    t = MockTraps()
    a = []

    def my_func(op, pc):
        assert op == 0xA000
        assert pc == 0x42
        a.append("huhu")

    assert t.get_num_traps() == 0
    tid = t.alloc(my_func, old_pc=True)
    assert t.get_num_traps() == 1
    assert t.get_func(tid) == my_func
    assert t.is_old_pc(tid)
    t.trigger(tid, pc=0x42)
    assert a == ["huhu"]
    t.free(tid)
    assert t.get_num_traps() == 0
