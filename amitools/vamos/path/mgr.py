from amitools.vamos.log import log_path
from .amipath import AmiPath, AmiPathError
from .env import AmiPathEnv
from .volume import VolumeManager
from .assign import AssignManager


class PathManager:

  def __init__(self, vol_mgr=None, assign_mgr=None, env=None):
    if vol_mgr is None:
      vol_mgr = VolumeManager()
    if assign_mgr is None:
      assign_mgr = AssignManager(vol_mgr)
    if env is None:
      env = AmiPathEnv()
    self.vol_mgr = vol_mgr
    self.assign_mgr = assign_mgr
    self.default_env = env

  def get_vol_mgr(self):
    return self.vol_mgr

  def get_assign_mgr(self):
    return self.assign_mgr

  def get_default_env(self):
    return self.default_env

  def parse_config(self, cfg):
    if not self.vol_mgr.parse_config(cfg):
      return False
    if not self.assign_mgr.parse_config(cfg):
      return False
    if not self.default_env.parse_config(cfg):
      return False
    if not self.validate():
      return False
    return True

  def validate(self):
    return self.validate_assigns() and self.validate_env(self.default_env)

  def validate_assigns(self):
    assigns = self.assign_mgr.get_all_names()
    for a in assigns:
      try:
        paths = self.assign_mgr.get_assign(a)
        for path in paths:
          self.volpaths(path)
      except AmiPathError as e:
        log_path.error("invalid assign: '%s': %s", a, e)
        return False
    return True

  def validate_env(self, env):
    # check work dir
    cwd = env.get_cwd()
    try:
      self.volpath(cwd)
    except AmiPathError:
      log_path.error("invalid cwd: '%s'", cwd)
      return False
    # check cmd paths
    cmd_paths = env.get_cmd_paths()
    for p in cmd_paths:
      try:
        self.volpaths(p)
      except AmiPathError as e:
        log_path.error("invalid command path: '%s': %s", p, e)
        return False
    return True

  def get_all_volume_names(self):
    return self.vol_mgr.get_all_names()

  def get_all_assign_names(self):
    return self.assign_mgr.get_all_names()

  def get_cmd_paths(self):
    return self.default_env.get_cmd_paths()

  def get_cwd(self):
    return self.default_env.get_cwd()

  def is_prefix_valid(self, ami_path):
    """check if prefix is either a volume or assign name"""
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    p = ami_path.prefix()
    if p is None:
      raise AmiPathError(ami_path, "no prefix in path")
    # check for volume name
    if self.vol_mgr.is_volume(p):
      return True
    # check for assign name
    if self.assign_mgr.is_assign(p):
      return True
    return False

  def is_volume_path(self, ami_path):
    """check if the prefix is a valid volume name.

    A relative path always returns False
    """
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    p = ami_path.prefix()
    if p is None:
      raise AmiPathError(ami_path, "no prefix in path")
    # check for volume name
    if self.vol_mgr.is_volume(p):
      return True
    return False

  def is_assign_path(self, ami_path):
    """check if the prefix is a valid assign name.

    A relative path always returns False
    """
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    p = ami_path.prefix()
    if p is None:
      raise AmiPathError(ami_path, "no prefix in path")
    # check for assign name
    if self.assign_mgr.is_assign(p):
      return True
    return False

  def is_valid(self, ami_path):
    """check if given path has valid syntax and if its absolute then
       also check prefix"""
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    if not ami_path.is_syntax_valid():
      return False
    if ami_path.is_absolute():
      return self.is_prefix_valid(ami_path)
    else:
      return True

  def is_multi_assign_path(self, ami_path):
    """check if path resolves to multiple paths"""
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    # expand along assigns until a multi assign or a volume is found
    while True:
      p = ami_path.prefix()
      if p is None:
        raise AmiPathError(ami_path, "no prefix in path")
      # get assign list or None
      alist = self.assign_mgr.get_assign(p)
      # no more assign: is volume
      if alist is None:
        return False
      # already a multi assign. stop
      elif len(alist) > 1:
        return True
      # resolve single assign as it might ref a multi assign
      else:
        ami_path = AmiPath(alist[0])

  def abspath(self, ami_path, env=None):
    """return an absolute path

    If the path is already absolute then return path itself.
    Otherwise create a new AmiPath object with the absolute path
    by joining this path with the current directory of the path env.
    """
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    # already absolute?
    if ami_path.is_absolute():
      return ami_path
    # get current directory and join cur dir with my path
    if env is None:
      env = self.default_env
      cwd = env.get_cwd()
    else:
      # make sure its a volume path
      cwd = env.get_cwd()
      if not self.is_volume_path(cwd):
        raise AmiPathError(cwd, "cwd is not volpath!")
    return cwd.join(ami_path)

  def volpath(self, ami_path, env=None):
    """return a volume path.

    If its not a multi path then return the one and only resolved
    volume path for this path.

    For a multi path a AmiPathError is raised!
    """
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    # if its a local path then simply append cwd
    if ami_path.is_local():
      return self.abspath(ami_path, env)
    # if its already a volume path then keep it
    elif self.is_volume_path(ami_path):
      return ami_path
    else:
      # resolve assigns
      res = self.assign_mgr.resolve_assigns(str(ami_path), True)
      if res is None:
        raise AmiPathError(ami_path, "invalid prefix!")
      elif type(res) is str:
        return AmiPath(res)
      else:
        raise AmiPathError(
            ami_path, "volpath() encountered multi assigns!")

  def volpaths(self, ami_path, env=None):
    """return a list of volume paths for this path.

    If the path resolves to multiple paths then all resulting paths
    are generated by recursevily applying multi-assigns.
    """
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    if ami_path.is_local():
      return [self.abspath(ami_path, env)]
    elif self.is_volume_path(ami_path):
      return [ami_path]
    else:
      # assigns
      res = self.assign_mgr.resolve_assigns(str(ami_path))
      if res is None:
        raise AmiPathError(ami_path, "invalid prefix!")
      elif type(res) is str:
        return [AmiPath(res)]
      else:
        return [AmiPath(x) for x in res]

  def resolve_assigns(self, ami_path, recursive=False):
    """if path is prefixed by an assign name then resolve the assign.

    return a list of AmiPaths if mutliple assigns are involved
    or return a single path
    """
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    if ami_path.is_absolute() and self.is_assign_path(ami_path):
      res = self.assign_mgr.resolve_assigns(str(ami_path), recursive)
      if res is None:
        raise AmiPathError(ami_path, "invalid prefix!")
      elif type(res) is str:
        return AmiPath(res)
      else:
        return [AmiPath(x) for x in res]
    else:
      return ami_path

  def cmdpaths(self, ami_path, env=None, prepend_cur_dir=True,
               make_volpaths=True):
    """return a list of command paths derived from this path.

    If the path contains a name only then a list containing the
    current cmd paths form the path env are returned. If
    with_cur_dir is enabled then the current dir is added as well.

    If this path is not a name only then it is converted to a
    volpath and returned in a single item list.

    Path that do not end with name raise an AmiPathError
    """
    if type(ami_path) is str:
      ami_path = AmiPath(ami_path)
    if ami_path.is_name_only():
      if env is None:
        env = self.default_env
      # get cmd paths
      cmd_paths = env.get_cmd_paths()
      if make_volpaths:
        res = []
        for cp in cmd_paths:
          res += self.volpaths(cp)
      else:
        res = cmd_paths
      # join our name
      res = list(map(lambda x: x.join(ami_path), res))
      # add current dir
      if prepend_cur_dir:
        cur_dir = env.get_cwd()
        res.insert(0, cur_dir.join(ami_path))
      return res
    elif ami_path.ends_with_name():
      # use my path only
      if make_volpaths:
        return self.volpaths(ami_path)
      else:
        return [ami_path]
    else:
      raise AmiPathError(ami_path, "can't derive cmdpaths")
