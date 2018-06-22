from .amipath import AmiPath, AmiPathError
from amitools.vamos.log import log_path


class AmiPathEnv(object):
  def __init__(self, cwd=None, cmd_paths=None):
    if cwd is None:
      cwd = "sys:"
    if cmd_paths is None:
      cmd_paths = ["c:"]
    self.set_cwd(cwd)
    self.set_cmd_paths(cmd_paths)

  def parse_config(self, cfg):
    if cfg is None:
      return False
    path = cfg.path
    if path is None:
      return False
    if path.cwd:
      if not self.set_cwd(path.cwd):
        return False
    if path.command:
      if not self.set_cmd_paths(path.command):
        return False
    return True

  def get_cwd(self):
    """get the current working dir as AmiPath"""
    return self.cwd

  def set_cwd(self, cwd):
    """set the current working dir as AmiPath or str"""
    if type(cwd) is str:
      cwd = AmiPath(cwd)
    if not self._check_cwd(cwd):
      return False
    self.cwd = cwd
    return True

  def get_cmd_paths(self):
    """return list of command paths"""
    return self.cmd_paths

  def set_cmd_paths(self, cmd_paths):
    cps = []
    for cp in cmd_paths:
      if type(cp) is str:
        cp = AmiPath(cp)
      if not self._check_cmd_path(cp):
        return False
      cps.append(cp)
    self.cmd_paths = cps
    return True

  def add_cmd_path(self, cp, prepend=False):
    if type(cp) is str:
      cp = AmiPath(cp)
    if not self._check_cmd_path(cp):
      return False
    if prepend:
      self.cmd_paths.insert(0, cp)
    else:
      self.cmd_paths.append(cp)
    return True

  def del_cmd_path(self, cp):
    if cp in self.cmd_paths:
      self.cmd_paths.remove(cp)
      return True
    else:
      return False

  def _check_cwd(self, cwd):
    if not isinstance(cwd, AmiPath):
      log_path.error("invalid cwd path: %s", cwd)
      return False
    if not cwd.is_absolute():
      log_path.error("current work dir is not absolute: %s", cwd)
      return False
    return True

  def _check_cmd_path(self, cp):
    if not isinstance(cp, AmiPath):
      log_path.error("inavlid command path: %s", cp)
    if not cp.is_absolute():
      log_path.error("command path is not absolute: %s", cp)
      return False
    return True
