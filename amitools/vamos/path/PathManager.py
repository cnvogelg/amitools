import os.path
import os
from amitools.vamos.Log import log_path
from amitools.vamos.Exceptions import *
from VolumeManager import VolumeManager
from AssignManager import AssignManager
from amitools.vamos.lib.dos.LockManager import LockManager
from amitools.vamos.lib.dos.Lock import Lock

class PathManager:

  def __init__(self, cfg):
    self.vol_mgr = VolumeManager()
    self.assign_mgr = AssignManager(self.vol_mgr)
    self.paths = []
    self.lock_mgr = None
    args = cfg.get_args()
    self.parse(cfg, args.volume, args.assign, args.auto_assign, args.path)

  def parse(self, cfg, volume_strs=None, assign_strs=None, auto_assign=None, path_strs=None):
    # volumes
    self.vol_mgr.parse_config(cfg)
    self.vol_mgr.parse_strings(volume_strs)
    self.vol_mgr.config_done()
    # assign
    self.assign_mgr.parse_config(cfg)
    self.assign_mgr.parse_strings(assign_strs)
    self.assign_mgr.set_auto_assign(auto_assign)
    # done
    self._parse_config(cfg)
    self._parse_strings(path_strs)
    self._config_done()

  def setup(self, lock_mgr):
    self.lock_mgr = lock_mgr

  def _parse_config(self, cfg):
    if cfg == None:
      return
    sect = 'path'
    if cfg.has_option(sect, 'path'):
      p = cfg.get(sect, 'path')
      if p != None:
        self.add_path(p)

  def _parse_strings(self, path_strs):
    if path_strs == None:
      return
    for p in path_strs:
      self.add_path(p)

  def add_path(self, paths):
    # append assign or clear first?
    if len(paths)>0 and paths[0] == '+':
      paths = paths[1:]
    else:
      self.paths = []
    # split multi assign
    path_list = paths.split(',')
    if path_list == None:
      raise VamosConfigError("invalid path: %s" % paths)
    # add assign
    if len(path_list) > 0:
      for p in path_list:
        # ensure slash at end if not a colon
        if p[-1] != ':' and p[-1] != '/' and p != '.':
          p += '/'
        self.paths.append(p)

  def _config_done(self):
    # set current device and path name
    cur_sys = os.getcwd()
    cur_ami = self.vol_mgr.sys_to_ami_path_pair(cur_sys)
    if cur_ami == None:
      raise VamosConfigError("Can't map current directory to amiga path: '%s'" % cur_sys)
    # ensure path
    if len(self.paths)==0:
      self.paths = ['.','c:']
    log_path.info("path: %s" % map(str, self.paths))

  # ----- API -----

  def get_all_volume_names(self):
    return self.vol_mgr.get_all_names()

  def get_all_assigns(self):
    return self.assign_mgr.get_all_assigns()

  def get_paths(self):
    return self.paths

  def ami_command_to_sys_path(self, lock, ami_path):
    """lookup a command on path if it does not contain a relative or absolute path
       otherwise perform normal 'ami_to_sys_path' conversion"""
    sys_path = None
    # is not a command only
    if ami_path.find(':') != -1 or ami_path.find('/') != -1:
      check_path = self.ami_to_sys_path(lock, ami_path)
      # make sure its a file
      if check_path != None and os.path.isfile(check_path):
        sys_path = check_path
    else:
      # try all path
      for path in self.paths:
        # special case: current dir
        if path == '.':
          try_ami_path = ami_path
        else:
          try_ami_path = path + ami_path
        check_path = self.ami_to_sys_path(lock, try_ami_path, mustExist=True)
        log_path.info("ami_command_to_sys_path: try_ami_path='%s' -> sys_path='%s'" % (try_ami_path, check_path))
        # make sure its a file
        if check_path != None and os.path.isfile(check_path):
          sys_path = check_path
          break

    if sys_path != None:
      log_path.info("ami_command_to_sys_path: ami_path=%s -> sys_path=%s" % (ami_path, sys_path))
      return sys_path
    else:
      log_path.info("ami_command_to_sys_path: ami_path='%s' not found!" % (ami_path))
      return None

  def ami_to_sys_path(self, lock, ami_path, searchMulti=False, mustExist=False):
    # first get an absolute amiga path
    abs_path = self.ami_abs_path(lock, ami_path)
    # replace assigns
    norm_paths = self.assign_mgr.ami_path_resolve(abs_path)
    if len(norm_paths) == 0 or ami_path=="*":
      log_path.info("ami_to_sys_path: ami_path='%s' -> abs_path='%s' -> no resolved paths!" % (ami_path, abs_path))
      return None
    # now we have paths with volume:abs/path
    sys_path = None
    # search for existing multi assign
    if searchMulti or mustExist:
      for npath in norm_paths:
        # first try to find existing path in all locations
        spath = self.vol_mgr.ami_to_sys_path(npath, mustExist=True)
        if spath != None:
          sys_path = spath
          break
    # nothing found -> try first path
    if sys_path == None and not mustExist:
      sys_path = self.vol_mgr.ami_to_sys_path(norm_paths[0], mustExist=False)
    log_path.info("ami_to_sys_path: ami_path='%s' -> abs_path='%s' -> norm_path='%s' -> sys_path='%s'" % (ami_path, abs_path, norm_paths, sys_path))
    return sys_path

  def sys_to_ami_path(self, sys_path):
    abs_path = os.path.abspath(sys_path)
    ami_path = self.vol_mgr.sys_to_ami_path(abs_path)
    log_path.info("sys_to_ami_path: sys_path='%s' -> abs_path='%s' -> ami_path='%s'" % (sys_path, abs_path, ami_path))
    return ami_path

  def ami_abs_parent_path(self, path):
    """return absolute parent path of given path or same if already parent"""
    # can't strip from device prefix
    if len(path) > 0 and path[-1] == ':':
      return path
    # skip trailing slash, then recursively call self
    if len(path) > 0 and path[-1] == '/':
      return self.ami_abs_parent_path(path[:-1])
    pos = path.rfind('/')
    # skip last part if we have parts
    if pos > -1:
      return path[0:pos]
    # keep only device if we have it
    else:
      pos = path.find(':')
      if pos > 0:
        return path[0:pos+1]
      elif len(path) > 0:
        return ""
      else:
        return "/"

  def ami_abs_path(self, lock, path):
    """return absolute amiga path from given path"""
    # current dir
    if path == "":
      if lock == None:
        return "SYS:"
      else:
        return lock.ami_path
    col_pos = path.find(':')
    # already with device name, path is already
    # absolute
    if col_pos > 0:
      return path
    # relative to root of current lock
    elif col_pos == 0:
      abs_prefix = self.lock_mgr.volume_name_of_lock(lock)
      path = path[1:]
      # parent path of root? -> remove
      while len(path)>0 and path[0] == '/':
        path = path[1:]
    # a parent path is given
    elif path[0] == '/':
      if lock == None:
        return "SYS:"
      abs_prefix = lock.ami_path
      while len(path)>0 and path[0] == '/':
        abs_prefix = self.ami_abs_parent_path(abs_prefix)
        path = path[1:]
      if path != "":
        abs_prefix += "/"
    # cur path
    else:
      if lock == None:
        abs_prefix = "SYS:"
      else:
        abs_prefix = lock.ami_path
      if abs_prefix[-1] != ':' and abs_prefix[-1] != '/':
        abs_prefix += '/'
    return abs_prefix + path

  # ---- path components -----

  def ami_name_of_path(self, lock, path):
    l = len(path)
    # no path given
    if l == 0:
      return ""
    # ends with colon
    if path[-1] == ':':
      if l == 1:
        return self.lock_mgr.volume_name_of_lock(lock)
      else:
        return path[:-1]
    # has slash?
    pos = path.rfind('/')
    if pos != -1:
      if pos == len(path)-1:
        return ""
      else:
        return path[pos+1:]
    # has colon?
    pos = path.rfind(':')
    if pos != -1:
      return path[pos+1:]
    # is relative
    return path

  def ami_dir_of_path(self, lock, path):
    l = len(path)
    if l == 0:
      return ""
    # ends with volume
    p = path
    vol = ""
    if p[-1] == ':':
      return ""
    # skip volume
    col_pos = p.find(':')
    if col_pos >= 0:
      vol = p[:col_pos+1]
      p = p[col_pos+1:]
      l = len(path)
      if l > 0 and p[0] == '/':
        p = p[1:]
    # find slash, also add
    # the volume again.
    slash_pos = p.rfind('/')
    if slash_pos == -1:
      return vol+""
    else:
      if slash_pos == 0:
        return vol+"/"
      else:
        return vol+p[:slash_pos]

  def ami_volume_of_path(self, path):
    pos = path.find(':')
    if pos == 0:
      raise VamosConfigError("ami volume path is not absolute: %s" % paths)
    else:
      return path[:pos]

  def ami_voldir_of_path(self, lock, path):
    ami_volume = self.ami_volume_of_path(lock,path)
    ami_dir = self.ami_dir_of_path(lock,path)
    if ami_volume != "":
      return ami_volume + ':' + ami_dir
    else:
      return ami_dir

  # ----- list dir -----

  def ami_list_dir(self, lock, ami_path):
    sys_path = self.ami_to_sys_path(lock, ami_path, mustExist=True)
    if sys_path == None:
      return None
    if not os.path.isdir(sys_path):
      return None
    files = os.listdir(sys_path)
    return files

  def ami_path_exists(self, lock, ami_path):
    sys_path = self.ami_to_sys_path(lock, ami_path, mustExist=True)
    return sys_path != None

  def ami_path_join(self, a, b):
    if len(a) == 0:
      return b
    elif len(b) == 0:
      return a
    else:
      return a + b



