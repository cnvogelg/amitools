from amitools.vamos.path import VamosPathManager
from amitools.vamos.lib.dos.MatchFirstNext import MatchFirstNext


def path_vamos_mgr_test(tmpdir):
    path = str(tmpdir)
    vpm = VamosPathManager(vols_base_dir=path)
    assert vpm.setup()
    vm = vpm.get_vol_mgr()
    assert vm.is_volume("system")
    assert vm.is_volume("root")
    assert vm.is_volume("ram")
    am = vpm.get_assign_mgr()
    assert am.is_assign("sys")
    assert am.is_assign("c")
    assert am.is_assign("s")
    assert am.is_assign("t")
    assert am.is_assign("devs")
    assert am.is_assign("libs")
    vpm.shutdown()


def path_vamos_matchfirst_parent_lock_test(tmpdir):
    vpm = VamosPathManager(vols_base_dir=str(tmpdir), auto_volumes=[], auto_assigns=[])
    assert vpm.setup()

    class DummyLock:
        ami_path = "T:"

    class DummyLockMgr:
        def __init__(self):
            self.calls = []

        def create_lock(self, cur_dir, ami_path, exclusive):
            self.calls.append((cur_dir, ami_path, exclusive))

            class LockStub:
                mem = type("MemStub", (), {"addr": 0x1234})()

            return LockStub()

        def get_by_b_addr(self, baddr):
            return None

        def release_lock(self, lock):
            pass

    mfn = MatchFirstNext.__new__(MatchFirstNext)
    mfn.path_mgr = vpm
    mfn.lock = DummyLock()
    mfn.lock_mgr = DummyLockMgr()
    mfn.achain_dummy_struct = type(
        "DummyAChain",
        (),
        {"lock": type("DummyLockRef", (), {"bptr": 0, "aptr": 0})()},
    )()
    mfn.dir_lock = None

    mfn._fill_parent_lock("t_0_0.asm")

    assert mfn.lock_mgr.calls[-1][1] == "T:"
    vpm.shutdown()


def path_vamos_handler_list_dir_test(tmpdir):
    from amitools.vamos.handler import MODE_NEWFILE, build_handler_manager

    vpm = VamosPathManager(vols_base_dir=str(tmpdir), auto_volumes=[], auto_assigns=[])
    assert vpm.get_vol_mgr().add_volume("ram:?handler=ram")
    assert vpm.setup()
    mgr = build_handler_manager(vpm)
    assert vpm.handler_mgr is mgr
    # write a file through the handler of the path-less volume
    handler, fh = mgr.find_output("ram:f.txt", MODE_NEWFILE)
    handler.write(fh, b"x")
    handler.end(fh)
    # ami_list_dir / ami_path_exists fall back to the handler
    assert "f.txt" in vpm.ami_list_dir(None, "ram:")
    assert vpm.ami_path_exists(None, "ram:f.txt")
    assert not vpm.ami_path_exists(None, "ram:nope")
    vpm.shutdown()
