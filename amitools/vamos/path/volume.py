import os
import os.path
from amitools.vamos.log import log_path
import logging


class VolumeManager():
  def __init__(self):
    # build map of volumes to sys_paths and vice versa
    self.volume2sys = {}
    self.sys2volume = {}
    self.orig_names = {}

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
    for vol in sorted(self.volume2sys):
      sys_path = self.volume2sys[vol]
      orig_name = self.orig_names[vol]
      log_path.info("%s: sys_path=%s (%s)", vol, sys_path, orig_name)

  def add_volumes(self, volumes, force=False):
    if not volumes:
      return True
    for volume in volumes:
      sys_path = volumes[volume]
      exists = self.is_volume(volume)
      if force or not exists:
        if not self.add_volume(volume, sys_path):
          return False
    return True

  def add_volume(self, name, sys_path):
    # ensure volume name is lower case
    lo_name = name.lower()
    # check path and name
    sys_path = self.resolve_sys_path(sys_path)
    if not os.path.isdir(sys_path):
      log_path.error("invalid volume path: '%s' -> %s" %
                     (name, sys_path))
      return False
    elif sys_path in self.sys2volume:
      log_path.error("duplicate volume mapping: '%s' -> %s" %
                     (name, sys_path))
      return False
    elif lo_name in self.volume2sys:
      log_path.error("duplicate volume name: '%s'", name)
      return False
    else:
      log_path.info("add volume: '%s:' -> %s", name, sys_path)
      self.volume2sys[lo_name] = sys_path
      self.sys2volume[sys_path] = lo_name
      self.orig_names[lo_name] = name
      return True

  def resolve_sys_path(self, sys_path):
    """replace ~ (home) or environment variables in path and
       make path absolute

       return resolved path
    """
    # expand system path
    sys_path = os.path.expanduser(sys_path)
    sys_path = os.path.expandvars(sys_path)
    abs_path = os.path.abspath(sys_path)
    return abs_path

  def del_volume(self, name):
    lo_name = name.lower()
    if lo_name not in self.volume2sys:
      return False
    sys_path = self.volume2sys[lo_name]
    del self.volume2sys[lo_name]
    del self.sys2volume[sys_path]
    del self.orig_names[lo_name]
    log_path.info("del volume: '%s:' -> %s", name, sys_path)
    return True

  def is_volume(self, name):
    return name.lower() in self.volume2sys

  def get_volume_sys_path(self, name):
    return self.volume2sys[name.lower()]

  def get_all_names(self):
    return self.orig_names.values()

  def is_sys_path_abs(self, sys_path):
    return os.path.isabs(sys_path)

  def sys_to_ami_path(self, sys_path):
    """try to map an absolute system path back to an amiga path

       if multiple volumes overlap then take the shortest amiga path

       return ami_path or None if sys_path can't be mapped
    """
    if not os.path.isabs(sys_path):
      log_path.error("vol: sys_to_ami_path: no abs path: '%s'", sys_path)
      return None
    res_len = None
    result = None
    for vol_sys_path in self.sys2volume:
      cp = os.path.commonprefix([vol_sys_path, sys_path])
      if cp == vol_sys_path:
        remainder = sys_path[len(vol_sys_path):]
        n = len(remainder)
        if n > 0 and remainder[0] == '/':
          remainder = remainder[1:]
          n -= 1
        # get volume name and build amiga path
        vol_name = self.sys2volume[vol_sys_path]
        vol_name = self.orig_names[vol_name]
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
    if vol_name in self.volume2sys:
      vol_sys_path = self.volume2sys[vol_name]
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
