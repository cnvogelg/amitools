from amitools.vamos.Log import *
from amitools.vamos.Exceptions import *
import os

class AssignManager:
  def __init__(self, vol_mgr):
    self.vol_mgr = vol_mgr
    self.assigns = {}
    self.auto_assign = None

  def parse_config(self, cfg):
    if cfg == None:
      return
    sect = 'assigns'
    if cfg.has_section(sect):
      opts = cfg.options(sect)
      for name in opts:
        paths = cfg.get(sect, name)
        self.set_assign(name, paths)

    # check for [path] -> auto_assign
    sect = 'path'
    if cfg.has_option(sect, 'auto_assign'):
      aa = cfg.get(sect, 'auto_assign')
      if aa != None:
        self.set_auto_assign(aa)

  def parse_strings(self, strs):
    if strs == None:
      return
    for s in strs:
      pos = s.find(':')
      if pos == -1:
        raise VamosConfigError("invalid assign: %s" % s)
      name = s[:pos]
      paths = s[pos+1:]
      self.set_assign(name, paths)

  def set_auto_assign(self, val):
    if val == None:
      return
    val,is_vol = self._ensure_volume_or_assign(val)
    if not is_vol:
      raise VamosConfigError("auto assign must map to volume!")
    self.auto_assign = val

  def set_assign(self, name, paths):
    if len(paths) == 0:
      raise VamosConfigError("invalid assign: %s" % name)
    # append assign or clear first?
    if paths[0] == '+':
      paths = paths[1:]
    else:
      self.clear_assign(name)
    # split multi assign
    path_list = paths.split(',')
    if path_list == None:
      raise VamosConfigError("invalid assign: %s" % name)
    # add assign
    if len(path_list) > 0:
      self.add_assign(name, path_list)

  def _ensure_volume_or_assign(self, path_name):
    if len(path_name) == 0:
      raise VamosConfigError("invalid empty assign: %s",path_name)
    # make sure it maps to a volume or another assign
    split = self.ami_path_split_volume(path_name)
    if split == None:
      raise VamosConfigError("assign has to map to volume or another assign: %s" % path_name)
    # ensure trailing slash
    if path_name[-1] != '/' and path_name[-1] != ':':
      path_name += '/'
    # check if its a volume
    is_vol = self.vol_mgr.is_ami_volume(split[0])
    return path_name, is_vol

  def add_assign(self, name, path_list):
    if self.assigns.has_key(name):
      alist = self.assigns[name]
    else:
      alist = []
      self.assigns[name] = alist
    # check path_list
    for p in path_list:
      p,is_vol = self._ensure_volume_or_assign(p)
      alist.append(p)
    log_path.info("add_assign: name='%s' -> paths=%s", name, alist)

  def clear_assign(self, name):
    if self.assigns.has_key(name):
      del self.assigns[name]

  # return (volume,remainder) or none if no volume found
  def ami_path_split_volume(self, ami_path):
    pos = ami_path.find(':')
    # no assign expansion
    if pos == -1:
      return None
    else:
      name = ami_path[:pos].lower()
      if ami_path[-1] == ':':
        remainder = ''
      else:
        remainder = ami_path[pos+1:]
      return (name,remainder)

  # check if path contains assign prefix
  # returns: list of reachable paths
  # Note: this follows recursive assigns, too
  def ami_path_resolve_assigns(self, ami_path):
    result = []
    log_path.info("resolve_assign: ami_path='%s'", ami_path)
    split = self.ami_path_split_volume(ami_path)
    if split == None:
      return ami_path
    else:
      name = split[0]
      if self.assigns.has_key(name):
        aname_list = self.assigns[name]
        for aname in aname_list:
          new_path = aname + split[1]
          log_path.info("resolve_assign: ami_path='%s' potential targets='%s' resulting path='%s'", ami_path, aname, new_path)
          result += self.ami_path_resolve_assigns(new_path)
      # no assign
      else:
        result.append(ami_path)

    log_path.debug("resolve_assign: ami_path='%s' -> paths=%s", ami_path, result)
    return result

  # in: ami_path with optional volume/assign
  # out: assign replaced by auto_assign or None if no auto_assign defined
  def ami_path_resolve_auto_assigns(self, ami_path):
    # get volume name -> if none found then return input
    split = self.ami_path_split_volume(ami_path)
    if split == None:
      return ami_path
    # do not resolve volume names!
    vol_name = split[0]
    if self.vol_mgr.is_ami_volume(vol_name):
      return ami_path
    # no auto assign defined
    if self.auto_assign == None:
      return None
    # apply auto assign
    new_path = self.auto_assign + split[0] + '/' + split[1]
    log_path.debug("resolve_auto_assign: ami_path='%s' -> new_path='%s'", ami_path, new_path)
    return new_path

  # full resolve: assigns + auto assigns
  def ami_path_resolve(self, ami_path):
    ami_path = self.ami_path_resolve_assigns(ami_path)
    result = []
    for p in ami_path:
      p = self.ami_path_resolve_auto_assigns(p)
      if p != None:
        result.append(p)
    return result

  def get_all_assigns(self):
    return (self.assigns,self.auto_assign)

