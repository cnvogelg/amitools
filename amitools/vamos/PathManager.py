import os.path
import os
from Log import log_path

class PathManager:
  
  def read_assigns(self):
    assigns = {}
    if os.path.isdir(self.assign_path):
      files = os.listdir(self.assign_path)
      for f in files:
        p = os.path.join(self.assign_path,f)
        result = None
        # its a link, ok
        if os.path.islink(p):
          tgt = os.readlink(p)
          tgt = os.path.abspath(tgt)
          result = [tgt]
          log_path.info("set assign %s: -> %s",f,tgt)
        # dir is ok, too -> read links from dir
        elif os.path.isdir(p):
          result = []
          dir_files = os.listdir(p)
          for df in dir_files:
            dfp = os.path.join(p,df)
            # link in dir is added to assign
            if os.path.islink(dfp):
              d_tgt = os.readlink(dfp)
              d_tgt = os.path.abspath(d_tgt)
              result.append(d_tgt)
              log_path.info("add assign %s: -> %s",f,d_tgt)
            else:
              log_path.warn("invalid assign contents: %s",dfp)
        else:
          log_path.warn("invalid assign contents: %s",p)
          
        # valid assign?
        if result != None:
          if f == 'sys':
            if len(result) > 1:
              log_path.error("'sys' assign must be a single one! %s",result)
            else:
              self.sys = result[0]
          else:
            assigns[f] = result        
    self.assigns = assigns
  
  def __init__(self, prefix):
    self.prefix = prefix
    self.assign_path = os.path.join(prefix,"assign")
    # build map of assigns
    self.read_assigns()
    # ensure to set sys: path
    if not self.assigns.has_key('sys'):
      self.sys = ['/']
      self.assigns['sys'] = self.sys
    else:
      self.sys = self.assigns['']
  
    # set current device and path name
    cur_ami = self._find_assign(os.getcwd())
    self.cur_dev  = cur_ami[0]
    self.cur_path = cur_ami[1]
    log_path.info("current: dev='%s' path='%s'" % (self.cur_dev, self.cur_path))

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

  def _find_assign(self, name):
    name = os.path.abspath(name)
    nl = len(name)
    # search through assigns
    for a in self.assigns:
      for p in self.assigns[a]:
        rem = self._is_path_begin(p, name)
        if rem != None:
          return (a,rem)
    # search in sys
    rem = self._is_path_begin(self.sys, name)
    if rem != None:
      return ('sys',rem)
    else:
      raise ValueError("Invalid Amiga Path: %s" % name)
  
  def _follow_path_no_case(self, base, dirs, always=False):
    if len(dirs) == 0:
      return base
    d = dirs[0]
    dl = len(d)
    # check for direct match first
    dp = os.path.join(base,d)
    if os.path.exists(dp):
      return self._follow_path_no_case(dp, dirs[1:])
    # read dir and check for no case variant
    dlow = d.lower()
    files = os.listdir(base)
    for f in files:
      if len(f) == dl:
        flow = f.lower()
        if flow == dlow:
          res = os.path.join(base, f)
          return self._follow_path_no_case(res, dirs[1:])
    # can't find it -> we assume rest of path is new
    if always:
      return os.path.join(base, os.path.join(*dirs))
    else:
      return None
  
  def ami_to_sys_path(self, name):
    # does it contain a ':' ?
    colon_pos = name.find(':')
    if colon_pos != -1:
      dev = name[:colon_pos]
      if len(dev) < len(name)-1:
        path = name[colon_pos+1:]
      else:
        path = ""
    else:
      dev = self.cur_dev
      path = os.path.join(self.cur_path,name)
    pdirs = path.split('/')
    # now search assign
    if not self.assigns.has_key(dev):
      raise ValueError("Invalid Amiga Device: %s" % dev)
    dirs = self.assigns[dev]
    for d in dirs:
      p = self._follow_path_no_case(d, pdirs)
      if p != None:
        return p
    # use first dir
    return self._follow_path_no_case(dirs[0], pdirs, always=True)

  def sys_to_ami_path(self, name):
    (dev, path) = self._find_assign(name)
    if path != "" and path[0] == '/':
      path = path[1:]
    return "%s:%s" % (dev, path)
    
