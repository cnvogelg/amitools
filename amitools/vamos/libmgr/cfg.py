from __future__ import print_function


class LibCfg(object):
  CREATE_MODE_OFF = 'off'
  CREATE_MODE_AUTO = 'auto'
  CREATE_MODE_VAMOS = 'vamos'
  CREATE_MODE_AMIGA = 'amiga'
  CREATE_MODE_FAKE = 'fake'

  EXPUNGE_MODE_LAST_CLOSE = 'last_close'
  EXPUNGE_MODE_NO_MEM = 'no_mem'
  EXPUNGE_MODE_SHUTDOWN = 'shutdown'

  valid_create_modes = (
      CREATE_MODE_OFF,
      CREATE_MODE_AUTO,
      CREATE_MODE_VAMOS,
      CREATE_MODE_AMIGA,
      CREATE_MODE_FAKE
  )

  valid_expunge_modes = (
      EXPUNGE_MODE_LAST_CLOSE,
      EXPUNGE_MODE_NO_MEM,
      EXPUNGE_MODE_SHUTDOWN
  )

  def __init__(self, create_mode=None, do_profile=False,
               force_version=None, expunge_mode=None):
    # set defaults
    if create_mode is None:
      create_mode = self.CREATE_MODE_AUTO
    if expunge_mode is None:
      expunge_mode = self.EXPUNGE_MODE_LAST_CLOSE
    if create_mode not in self.valid_create_modes:
      raise ValueError("invalid create_mode: " + create_mode)
    if expunge_mode not in self.valid_expunge_modes:
      raise ValueError("invalid expunge mode: " + expunge_mode)
    # store values
    self.create_mode = create_mode
    self.do_profile = do_profile
    self.force_version = force_version
    self.expunge_mode = expunge_mode

  def get_create_mode(self):
    return self.create_mode

  def get_do_profile(self):
    return self.do_profile

  def get_force_version(self):
    return self.force_version

  def get_expunge_mode(self):
    return self.expunge_mode

  def __eq__(self, other):
    return self.create_mode == other.create_mode and \
        self.do_profile == other.do_profile and \
        self.force_version == other.force_version and \
        self.expunge_mode == other.expunge_mode

  def __ne__(self, other):
    return self.create_mode != other.create_mode or \
        self.do_profile != other.do_profile or \
        self.force_version != other.force_version or \
        self.expunge_mode != other.expunge_mode

  def __repr__(self):
    return "LibCfg(create_mode=%s, do_profile=%s," \
        " force_version=%s, expunge_mode=%s)" % \
        (self.create_mode, self.do_profile,
         self.force_version, self.expunge_mode)


class LibMgrCfg(object):
  """hold config options of the lib manager"""

  def __init__(self, do_profile_all=False,
               profile_add_samples=False,
               def_cfg=None):
    if def_cfg is None:
      def_cfg = LibCfg()
    self.do_profile_all = do_profile_all
    self.profile_add_samples = profile_add_samples
    self.def_cfg = def_cfg
    self.cfg_map = {}

  def get_do_profile_all(self):
    return self.do_profile_all

  def get_profile_add_samples(self):
    return self.profile_add_samples

  def set_def_cfg(self, lib_cfg):
    self.def_cfg = lib_cfg

  def get_def_cfg(self):
    return self.def_cfg

  def add_cfg(self, name, lib_cfg):
    self.cfg_map[name] = lib_cfg

  def get_cfg(self, name, or_default=True):
    if name in self.cfg_map:
      return self.cfg_map[name]
    if or_default:
      return self.def_cfg

  def get_all_names(self):
    return sorted(self.cfg_map.keys())
