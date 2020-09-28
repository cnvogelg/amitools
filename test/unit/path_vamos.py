from amitools.vamos.path import VamosPathManager


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
