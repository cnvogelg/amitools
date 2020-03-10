from amitools.vamos.machine import MockTraps


def mock_traps_base_test():
    t = MockTraps()
    a = []

    def my_func(op, pc):
        assert op == 0xA000
        assert pc == 0x42
        a.append("huhu")

    assert t.get_num_traps() == 0
    tid = t.setup(my_func)
    assert t.get_num_traps() == 1
    assert t.get_func(tid) == my_func
    assert not t.is_auto_rts(tid)
    assert not t.is_one_shot(tid)
    t.trigger(tid, pc=0x42)
    assert a == ["huhu"]
    t.free(tid)
    assert t.get_num_traps() == 0


def mock_traps_one_shot_test():
    t = MockTraps()
    a = []

    def my_func(op, pc):
        assert op == 0xA000
        assert pc == 0x42
        a.append("huhu")

    assert t.get_num_traps() == 0
    tid = t.setup(my_func, one_shot=True)
    assert t.get_num_traps() == 1
    assert t.get_func(tid) == my_func
    assert not t.is_auto_rts(tid)
    assert t.is_one_shot(tid)
    t.trigger(tid, pc=0x42)
    assert a == ["huhu"]
    assert t.get_num_traps() == 0
