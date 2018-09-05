from amitools.vamos.path import VamosPathManager


def path_vamos_mgr_test(tmpdir):
  path = str(tmpdir)
  vpm = VamosPathManager(path)
  assert vpm.setup()
  vm = vpm.get_vol_mgr()
  assert vm.is_volume('system')
  assert vm.is_volume('root')
  am = vpm.get_assign_mgr()
  assert am.is_assign('sys')
  assert am.is_assign('c')
  assert am.is_assign('devs')
  assert am.is_assign('libs')
  vpm.shutdown()
