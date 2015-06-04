import os
import os.path
from amitools.vamos.Log import *
from amitools.vamos.Exceptions import *

class VolumeManager():
  def __init__(self):
    # build map of volumes to sys_paths and vice versa
    self.volume2sys = {}
    self.sys2volume = {}
    # ensure to define sys: volume
    self.set_volume('root','/')

  def parse_config(self, cfg):
    if cfg == None:
      return
    sect = 'volumes'
    if cfg.has_section(sect):
      opts = cfg.options(sect)
      for vol_name in opts:
        sys_path = cfg.get(sect, vol_name)
        self.set_volume(vol_name, sys_path)

  def parse_strings(self, strs):
    if strs == None:
      return
    for s in strs:
      pos = s.find(':')
      if pos == -1:
        raise VamosConfigError('No colon in volume define: %s' % s)
      vol_name = s[:pos]
      sys_path = s[pos+1:]
      self.set_volume(vol_name, sys_path)

  def set_volume(self, name, sys_path):
    # ensure volume name is lower case
    name = name.lower()
    # expand system path
    sys_path = os.path.expanduser( sys_path )
    sys_path = os.path.expandvars( sys_path )
    abs_path = os.path.abspath( sys_path )
    # remove trailing slash
    if len(abs_path) > 1 and abs_path[-1] == '/':
      abs_path = abs_path[:-1]
    # check if volume is not already defined and the map is valid
    if not os.path.exists(abs_path):
      log_path.error("ignoring invalid volume path: '%s' -> %s" % (name, abs_path))
    elif self.sys2volume.has_key(abs_path):
      log_path.error("ignoring duplicate volume: '%s' -> %s" % (name, abs_path))
    else:
      # clear old mapping first
      if self.volume2sys.has_key(name):
        self.del_volume(name)
      log_path.info("set_volume: '%s:' -> %s" % (name, abs_path))
      self.volume2sys[name] = abs_path
      self.sys2volume[abs_path] = name

  def del_volume(self, name):
    if not self.volume2sys.has_key(name):
      return
    sys_path = self.volume2sys[name]
    del self.volume2sys[name]
    del self.sys2volume[sys_path]

  def config_done(self):
    # sort volume list by length
    self.vol_list = self.sys2volume.keys()
    self.vol_list.sort(reverse=True)
    log_path.debug("vol_list=%s",self.vol_list)

  def _is_path_begin(self, begin, path):
    pl = len(path)
    bl = len(begin)
    if bl <= pl:
      part = path[:bl]
      if pl > bl:
        remainder = path[bl:]
      else:
        remainder = ""
      if part == begin:
        return remainder
    return None

  def is_ami_volume(self, vol_name):
    name = vol_name.lower()
    return self.volume2sys.has_key(name)

  # in: ami path
  # out: sys_path if it exists and None if not
  def valid_volume_ami_to_sys_path(self, ami_path):
    # make sure it contains a volume name
    pos = ami_path.find(':')
    if pos == -1:
      return None
    sys_path = self.ami_to_sys_path(ami_path, True)
    if sys_path == None:
      return None
    if not os.path.exists(sys_path):
      return None
    return sys_path

  # in: system path
  # out: None or "ami_volume:ami_path"
  def sys_to_ami_path_pair(self, sys_path):
    for vol_sys_path in self.vol_list:
      remainder = self._is_path_begin(vol_sys_path, sys_path)
      if remainder != None:
        # remove leading slash
        if len(remainder)>0 and remainder[0] == '/':
          remainder = remainder[1:]
        # get volume name and build amiga path
        vol_name = self.sys2volume[vol_sys_path]
        ami_path = vol_name + ":" + remainder
        log_path.debug("vol: sys_to_ami_path: sys='%s' -> ami='%s'", sys_path, ami_path)
        return (vol_name, remainder)
    return None

  def sys_to_ami_path(self, sys_path):
    vol_path = self.sys_to_ami_path_pair(sys_path)
    if vol_path == None:
      return None
    return "%s:%s" % vol_path

  # in: amiga path with optional volume prefix
  # out: sys_path or None if volume not found
  # Note: if no volume is found then the path is returned as is
  # The method automatically matches to case of sys path
  def ami_to_sys_path(self, ami_path, mustExist=False):
    # find volume
    pos = ami_path.find(':')
    if pos == -1:
      return ami_path
    vol_name = ami_path[:pos].lower()
    # check volume name
    if self.volume2sys.has_key(vol_name):
      remainder = ami_path[pos+1:]
      dirs = remainder.split('/')
      vol_sys_path = self.volume2sys[vol_name]
      sys_path = self._follow_path_no_case(vol_sys_path, dirs, mustExist)
      if sys_path == None:
        log_path.debug("vol: ami_to_sys_path: ami='%s' -> sys='%s' not found!", ami_path, sys_path)
        return None
      else:
        log_path.debug("vol: ami_to_sys_path: ami='%s' -> sys='%s' mustExit=%s", ami_path, sys_path, mustExist)
        return sys_path
    else:
      log_path.error("vol: ami_to_sys_path: volume='%s' not found!", vol_name )
      return None

  def _follow_path_no_case(self, base, dirs, mustExist):
    # base is the name (no more dirs)
    if len(dirs) == 0:
      if mustExist:
        if os.path.exists(base):
          return base
        else:
          return None
      else:
        return base
    # make sure base is a dir
    if not os.path.isdir(base):
      return None
    # dir component to search
    d = dirs[0]
    dl = len(d)
    # check for direct match first
    dp = os.path.join(base,d)
    if os.path.exists(dp):
      return self._follow_path_no_case(dp, dirs[1:], mustExist)
    # read dir and check for no case variant
    dlow = d.lower()
    files = os.listdir(base)
    for f in files:
      if len(f) == dl:
        flow = f.lower()
        if flow == dlow:
          res = os.path.join(base, f)
          return self._follow_path_no_case(res, dirs[1:], mustExist)
    # can't find it -> we assume rest of path is new
    if mustExist:
      return None
    else:
      return os.path.join(base, os.path.join(*dirs))

  def get_all_names(self):
    return self.volume2sys.keys()
