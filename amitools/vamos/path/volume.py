import os
import os.path
from amitools.vamos.log import log_path
import logging


def resolve_sys_path(sys_path):
  """replace ~ (home) or environment variables in path and
     make path absolute

     return resolved path
  """
  # expand system path
  sys_path = os.path.expanduser(sys_path)
  sys_path = os.path.expandvars(sys_path)
  abs_path = os.path.abspath(sys_path)
  return abs_path


class Volume(object):
  def __init__(self, name, path):
    self.name = name
    self.path = path
    self.lo_name = name.lower()
    self.res_path = None
    self.local_flag = False

  def __str__(self):
    return "Volume(%s(%s):%s->%s)" % \
        (self.name, self.lo_name, self.path, self.res_path)

  def get_name(self):
    """return volume name in original lo/up case writing"""
    return self.name

  def get_path(self):
    """return mapped volume path in original format"""
    return self.path

  def get_lo_name(self):
    """return normalized volume name in lower case"""
    return self.lo_name

  def get_res_path(self):
    """return resolved volume path"""
    return self.res_path

  def is_local(self):
    """is the volume a local volume, e.g. reside in vols_base_dir"""
    return self.local_flag

  def setup(self, base_dir=None, create_local=False):
    path = self.path
    # local volume?
    if path is None or path == "" or path == self.name:
      self.path = self.name
      res_path = self._setup_local_sys_path(base_dir, create_local)
      if not res_path:
        return False
      self.local_flag = True
    else:
      res_path = resolve_sys_path(path)
      # check for existing dir
      if not os.path.isdir(res_path):
        log_path.error("invalid volume path: '%s': %s -> %s",
                       self.name, path, res_path)
        return False
    # ok!
    self.res_path = res_path
    return True

  def shutdown(self):
    pass

  def _setup_local_sys_path(self, base_dir, create_local=False):
    """create a local sys path by appending vol_name to vols_base_dir

       if path is missing you may allow to create it

       return resulting sys_path or None on error
    """
    # first ensure that vols_base_dir exists
    base_dir = resolve_sys_path(base_dir)
    if not os.path.isdir(base_dir):
      try:
        log_path.info("creating volume base dir: %s", base_dir)
        os.makedirs(base_dir)
      except OSError as e:
        log_path.error("error creating volume base dir: %s -> %s",
                       base_dir, e)
        return None
    else:
      log_path.debug("found base dir: %s", base_dir)
    # build volume sys path
    vol_name = self.name
    sys_path = os.path.join(base_dir, vol_name)
    # path already exists
    if os.path.isdir(sys_path):
      log_path.info("found local volume dir: %s", sys_path)
      return sys_path
    if not create_local:
      log_path.error("local volume dir does not exist: %s", sys_path)
      return None
    # try to create path
    try:
      log_path.info("creating local volume dir: %s", sys_path)
      os.mkdir(sys_path)
      return sys_path
    except OSError as e:
      log_path.error("error creating local volume dir: %s -> %s", sys_path, e)
      return None

  def create_rel_sys_path(self, rel_path):
    if type(rel_path) in (list, tuple):
      rel_path = os.path.join(*rel_path)
    dir_path = os.path.join(self.res_path, rel_path)
    try:
      log_path.debug("creating rel sys path in volume '%s' + %s -> %s",
                     self.name, rel_path, dir_path)
      os.makedirs(dir_path)
      return dir_path
    except OSError as e:
      log_path.error("error creating rel sys path in volume '%s' + %s -> %s",
                     self.name, rel_path, dir_path)
      return None


class VolumeManager(object):
  def __init__(self, vols_base_dir=None):
    # build map of volumes to sys_paths and vice versa
    self.vols_by_name = {}
    self.vols_base_dir = vols_base_dir

  def set_vols_base_dir(self, dir):
    self.vols_base_dir = dir

  def parse_config(self, cfg):
    if cfg is None:
      return True
    vols = cfg.volumes
    if vols is None:
      return True
    for vol_name in vols:
      sys_path = vols[vol_name]
      if not self.add_volume(vol_name, sys_path):
        return False
    return True

  def dump(self):
    log_path.info("--- volume config ---")
    for vol_name in sorted(self.vols_by_name):
      volume = self.vols_by_name[vol_name]
      log_path.info("%s", volume)

  def add_volumes(self, volumes, force=False, create_local=False):
    if not volumes:
      return []
    res = []
    for volume in volumes:
      sys_path = volumes[volume]
      exists = self.is_volume(volume)
      if force or not exists:
        vol = self.add_volume(volume, sys_path, create_local)
        if not vol:
          return False
        res.append(vol)
    return res

  def add_volume(self, name, path=None, create_local=False):
    # create a new volume
    volume = Volume(name, path)
    lo_name = volume.get_lo_name()

    # check if volume name already exists?
    if lo_name in self.vols_by_name:
      log_path.error("duplicate volume name: '%s'", name)
      return None
    # check if volume path already exists?
    for dup_vol in self.vols_by_name.values():
      dup_path = dup_vol.get_path()
      if dup_path == path:
        log_path.error("duplicate volume mapping: '%s' and '%s' -> %s" %
                       (name, dup_vol.get_name(), path))
        return None

    # try to setup volume
    if not volume.setup(self.vols_base_dir, create_local):
      log_path.error("error setting up volume: '%s' -> '%s'", name, path)
      return None

    # finally add volume
    log_path.info("add volume: %s", volume)
    self.vols_by_name[lo_name] = volume
    return volume

  def del_volume(self, name):
    lo_name = name.lower()
    if lo_name not in self.vols_by_name:
      return False
    volume = self.vols_by_name[lo_name]
    del self.vols_by_name[lo_name]
    log_path.info("del volume: %s", volume)
    return True

  def is_volume(self, name):
    return name.lower() in self.vols_by_name

  def get_volume(self, name):
    lo_name = name.lower()
    if lo_name in self.vols_by_name:
      return self.vols_by_name[lo_name]

  def get_all_names(self):
    return map(lambda x: x.get_name(), self.vols_by_name.values())

  def sys_to_ami_path(self, sys_path):
    """try to map an absolute system path back to an amiga path

       if multiple volumes overlap then take the shortest amiga path

       return ami_path or None if sys_path can't be mapped
    """
    if not os.path.isabs(sys_path):
      sys_path = resolve_sys_path(sys_path)
      log_path.debug("vol: sys_to_ami_path: resolved rel path: %s", sys_path)
    res_len = None
    result = None
    for volume in self.vols_by_name.values():
      vol_sys_path = volume.get_res_path()
      cp = os.path.commonprefix([vol_sys_path, sys_path])
      if cp == vol_sys_path:
        remainder = sys_path[len(vol_sys_path):]
        n = len(remainder)
        if n > 0 and remainder[0] == '/':
          remainder = remainder[1:]
          n -= 1
        # get volume name and build amiga path
        vol_name = volume.get_name()
        ami_path = vol_name + ":" + remainder
        log_path.debug(
            "vol: sys_to_ami_path: sys='%s' -> ami='%s'", sys_path, ami_path)
        if result is None or n < res_len:
          result = ami_path
          res_len = n
    # return best result
    log_path.info(
        "vol: sys_to_ami_path: sys='%s' -> ami=%s", sys_path, result)
    return result

  def ami_to_sys_path(self, ami_path, fast=False):
    """Map an Amiga path to a system path.

       An absolute Amiga path with volume prefix is expected.
       Any other path returns None.

       If volume does not exist also return None.

       It replaces the volume with the sys_path prefix.
       Furthermore, the remaining Amiga path is mapped to
       the system file system and case corrected if a
       corresponding entry is found.

       If 'fast' mode is enabled then the original case
       of the path elements is kept if the underlying FS
       is case insensitive.

       Return None on error or system path
    """
    # find volume
    pos = ami_path.find(':')
    if pos <= 0:
      log_path.debug("vol: ami_to_sys_path: empty volume: %s", ami_path)
      return None
    vol_name = ami_path[:pos].lower()
    # check volume name
    if vol_name in self.vols_by_name:
      volume = self.vols_by_name[vol_name]
      vol_sys_path = volume.get_res_path()
      remainder = ami_path[pos+1:]

      # only volume name given
      if len(remainder) == 0:
        log_path.info("vol: direct volume: ami='%s' -> sys='%s'",
                      ami_path, vol_sys_path)
        return vol_sys_path

      # invalid volume:/... path
      if remainder[0] == '/':
        log_path.error("vol: ami_to_sys_path: invalid :/ path: %s", ami_path)
        return None

      # follow ami path along in sys world
      dirs = remainder.split('/')
      sys_path = self._follow_path_no_case(vol_sys_path, dirs, fast)
      log_path.info("vol: ami_to_sys_path: ami='%s' -> sys='%s'",
                    ami_path, sys_path)
      return sys_path
    else:
      log_path.error("vol: ami_to_sys_path: volume='%s' not found: %s",
                     vol_name, ami_path)
      return None

  def _follow_path_no_case(self, base, dirs, fast):
    # base is the name (no more dirs)
    if len(dirs) == 0:
      return base
    # make sure base is a dir
    if not os.path.isdir(base):
      # assume remainder is new
      return os.path.join(base, os.path.join(*dirs))
    # dir component to search
    d = dirs[0]
    # check for direct match first
    if fast:
      dp = os.path.join(base, d)
      if os.path.exists(dp):
        return self._follow_path_no_case(dp, dirs[1:], fast)
    # read dir and check for no case variant
    dlow = d.lower()
    files = os.listdir(base)
    dl = len(d)
    for f in files:
      if len(f) == dl:
        flow = f.lower()
        if flow == dlow:
          res = os.path.join(base, f)
          return self._follow_path_no_case(res, dirs[1:], fast)
    # can't find it -> we assume rest of path is new
    return os.path.join(base, os.path.join(*dirs))
