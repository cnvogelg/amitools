import os.path
import os
from Log import log_path
from Exceptions import *
from VolumeManager import VolumeManager
from AssignManager import AssignManager

class PathManager:
  
  def __init__(self):
    self.vol_mgr = VolumeManager()
    self.assign_mgr = AssignManager(self.vol_mgr)
  
  def parse(self, cfg, volume_strs=None, assign_strs=None, auto_assign=None):
    # volumes
    self.vol_mgr.parse_config(cfg)
    self.vol_mgr.parse_strings(volume_strs)
    self.vol_mgr.config_done()
    # assign
    self.assign_mgr.parse_config(cfg)
    self.assign_mgr.parse_strings(assign_strs)
    self.assign_mgr.set_auto_assign(auto_assign)
    # done
    self.config_done()
  
  def config_done(self):    
    # set current device and path name
    cur_sys = os.getcwd()
    cur_ami = self.vol_mgr.sys_to_ami_path_pair(cur_sys)
    if cur_ami == None:
      raise VamosConfigError("Can't map current directory to amiga path: '%s'" % cur_sys)
    self.cur_vol  = cur_ami[0]
    self.cur_path = cur_ami[1]
    self.org_cur_vol = cur_ami[0]
    self.org_cur_path = cur_ami[1]
    log_path.info("current amiga dir: '%s:%s'" % (self.cur_vol, self.cur_path))
  
  # current path handling
  
  def set_cur_path(self, full_path):
    split = self.assign_mgr.ami_path_split_volume(full_path)
    if split == None:
      raise ValueError("set_cur_path needs a path with device name!")
    self.cur_vol = split[0]
    self.cur_path = split[1]
    log_path.info("set current: dev='%s' path='%s'" % (self.cur_vol, self.cur_path))
  
  def get_cur_path(self):
    return (self.cur_vol, self.cur_path)
  
  def set_default_cur_path(self):
    self.cur_vol  = self.org_cur_vol
    self.cur_path = self.org_cur_path
    log_path.info("reset current: dev='%s' path='%s'" % (self.cur_vol, self.cur_path))

  def ami_abs_cur_path(self):
    return self.cur_vol + ":" + self.cur_path

  # ----- API -----

  def get_all_volume_names(self):
    return self.vol_mgr.get_all_names()

  def ami_to_sys_path(self, ami_path, searchMulti=False):
    # first get an absolute amiga path
    abs_path = self.ami_abs_path(ami_path)
    # replace assigns
    norm_paths = self.assign_mgr.ami_path_resolve(abs_path)
    if len(norm_paths) == 0:
      log_path.warn("ami_to_sys_path: ami_path=%s -> abs_path=%s -> no resolved paths!" % (ami_path, abs_path))
      return None
    # now we have paths with volume:abs/path
    sys_path = None
    # search for existing multi assign
    if searchMulti:
      for npath in norm_paths:
        # first try to find existing path in all locations
        spath = self.vol_mgr.ami_to_sys_path(npath, mustExist=True)
        if spath != None:
          sys_path = spath
          break
    # nothing found -> try first path
    if sys_path == None:
      sys_path = self.vol_mgr.ami_to_sys_path(norm_paths[0], mustExist=False)
    log_path.info("ami_to_sys_path: ami_path=%s -> abs_path=%s -> norm_path=%s -> sys_path=%s" % (ami_path, abs_path, norm_paths, sys_path))
    return sys_path

  def sys_to_ami_path(self, sys_path):
    abs_path = os.path.abspath(sys_path)
    ami_path = self.vol_mgr.sys_to_ami_path(abs_path)
    log_path.info("sys_to_ami_path: sys_path=%s -> abs_path=%s -> ami_path=%s" % (sys_path, abs_path, ami_path))
    return ami_path
  
  def ami_abs_parent_path(self, path):
    """return absolute parent path of given path or same if already parent"""
    # can't strip from device prefix
    if path[-1] == ':':
      return path
    # skip trailing slash
    if path[-1] == '/':
      return self.ami_strip_name(self, path[:-2])
    # make absolute first
    if path.find(':') < 1:
      path = self.ami_abs_path(path)
    pos = path.rfind('/')
    # skip last part
    if pos != -1:
      return path[0:pos]
    # keep only device
    else:
      pos = path.find(':')
      return path[0:pos+1]
  
  def ami_abs_path(self, path):
    """return absolute amiga path from given path"""
    col_pos = path.find(':')
    # already with device name
    if col_pos > 0:
      return path
    # relative to cur device
    elif col_pos == 0:
      abs_prefix = self.cur_vol + ":"
      path = path[1:]
      # invalid parent path of root? -> remove
      if len(path)>0 and path[0] == '/':
        path = path[1:]
    # no path given -> return current path
    elif path == '':
      return self.cur_vol + ":" + self.cur_path      
    # a parent path is given
    elif path[0] == '/':
      abs_prefix = self.ami_abs_parent_path(self.cur_vol + ":" + self.cur_path)
    # cur path
    else:
      abs_prefix = self.cur_vol + ":" + self.cur_path
      if self.cur_path != '':
        abs_prefix += '/'
    return abs_prefix + path

  def ami_name_of_path(self, path):
    l = len(path)
    # no path given
    if l == 0:
      return path
    # ends with colon
    if path[-1] == ':':
      if l == 1:
        return self.cur_vol
      else:
        return path[:-1]
    # has slash?
    pos = path.rfind('/')
    if pos != -1:
      return path[pos+1:]
    # has colon?
    pos = path.rfind(':')
    if pos != -1:
      return path[pos+1:]
    # is relative
    return path

  def ami_volume_of_abspath(self, path):
    pos = path.find(':')
    return path[:pos]
