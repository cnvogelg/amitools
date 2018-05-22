import pytest
from amitools.vamos.libmgr import LibCfg, LibMgrCfg


def libmgr_cfg_lib_default_test():
  lc = LibCfg()
  assert lc.get_create_mode() == LibCfg.CREATE_MODE_AUTO
  assert not lc.get_do_profile()
  assert lc.get_force_version() is None
  assert lc.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
  txt = str(lc)
  assert txt == "LibCfg(create_mode=auto, do_profile=False, force_version=None, expunge_mode=last_close)"


def libmgr_cfg_lib_custom_test():
  lc = LibCfg(LibCfg.CREATE_MODE_OFF, True, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
  assert lc.get_create_mode() == LibCfg.CREATE_MODE_OFF
  assert lc.get_do_profile()
  assert lc.get_force_version() is 1
  assert lc.get_expunge_mode() == LibCfg.EXPUNGE_MODE_NO_MEM
  txt = str(lc)
  assert txt == "LibCfg(create_mode=off, do_profile=True, force_version=1, expunge_mode=no_mem)"


def libmgr_cfg_lib_fail_test():
  with pytest.raises(ValueError):
    lc = LibCfg(create_mode="bla")
  with pytest.raises(ValueError):
    lc = LibCfg(expunge_mode="foo")


def libmgr_cfg_lib_eq_test():
  lc1 = LibCfg()
  lc2 = LibCfg()
  assert lc1 == lc2
  lc3 = LibCfg(force_version=1)
  assert lc1 != lc3


def libmgr_cfg_mgr_default_test():
  lmc = LibMgrCfg()
  assert not lmc.get_do_profile_all()
  assert not lmc.get_profile_add_samples()
  assert lmc.get_def_cfg() == LibCfg()
  assert lmc.get_all_names() == []
  assert lmc.get_cfg("bla.library") == LibCfg()
  lc = LibCfg(LibCfg.CREATE_MODE_OFF, True, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
  lmc.add_cfg("bla.library", lc)
  assert lmc.get_cfg("bla.library") == lc
  assert lmc.get_all_names() == ["bla.library"]
  assert lmc.get_cfg("foo.library") == LibCfg()
  lc2 = LibCfg(LibCfg.CREATE_MODE_AMIGA, False, 11, LibCfg.EXPUNGE_MODE_NO_MEM)
  lmc.add_cfg("foo.library", lc2)
  assert lmc.get_cfg("foo.library") == lc2
  assert lmc.get_all_names() == ["bla.library", "foo.library"]


def libmgr_cfg_mgr_custom_test():
  lcd = LibCfg(LibCfg.CREATE_MODE_OFF, True, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
  lmc = LibMgrCfg(do_profile_all=True, profile_add_samples=True, def_cfg=lcd)
  assert lmc.get_do_profile_all()
  assert lmc.get_profile_add_samples()
  assert lmc.get_def_cfg() == lcd
  assert lmc.get_all_names() == []
  assert lmc.get_cfg("bla.library") == lcd
  lc = LibCfg(LibCfg.CREATE_MODE_OFF, True, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
  lmc.add_cfg("bla.library", lc)
  assert lmc.get_cfg("bla.library") == lc
  assert lmc.get_all_names() == ["bla.library"]
