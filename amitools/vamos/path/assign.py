from amitools.vamos.log import log_path


class AssignManager:
  def __init__(self, vol_mgr):
    self.vol_mgr = vol_mgr
    self.assigns = {}
    self.orig_names = {}

  def parse_config(self, cfg):
    if cfg is None:
      return False
    assigns = cfg.assigns
    if assigns is None:
      return False
    for assign in assigns:
      paths = assigns[assign]
      if not self.add_assign(assign, paths):
        return False
    return True

  def get_all_names(self):
    return self.orig_names.values()

  def get_assign(self, name):
    lo_name = name.lower()
    if lo_name in self.assigns:
      return self.assigns[lo_name]

  def is_assign(self, name):
    return name.lower() in self.assigns

  def add_assign(self, name, path_list, append=False):
    # also allow path string instead of list
    if type(path_list) is str:
      path_list = [path_list]

    # check name: empty?
    if len(name) == 0:
      log_path.error("empty assign added!")
      return False
    # check name: is volume?
    lo_name = name.lower()
    if self.vol_mgr.is_volume(lo_name):
      log_path.error(
          "assign with a volume name: %s", name)
      return False
    # check name: duplicate assign
    elif lo_name in self.assigns:
      log_path.error(
          "duplicate assign: %s", name)
      return False

    # check path_list
    alist = []
    for path_name in path_list:
      if not self._ensure_volume_or_assign(path_name):
        return False
      # ensure trailing slash
      if path_name[-1] != '/' and path_name[-1] != ':':
        path_name += '/'
      alist.append(path_name)

    # setup assign list
    if append and self.assigns.has_key(lo_name):
      self.assigns[lo_name] += alist
    else:
      self.assigns[lo_name] = alist
    # save exact cased name
    self.orig_names[lo_name] = name

    log_path.info("add assign: name='%s' -> paths=%s", name, alist)
    return True

  def del_assign(self, name):
    lo_name = name.lower()
    if self.assigns.has_key(lo_name):
      alist = self.assigns[lo_name]
      log_path.info("del assign: name='%s' -> paths=%s", name, alist)
      del self.assigns[lo_name]
      del self.orig_names[lo_name]
      return True
    else:
      log_path.error("assign not found: %s", name)
      return False

  def _ensure_volume_or_assign(self, path_name):
    if len(path_name) == 0:
      log_path.error("invalid empty assign: %s", path_name)
      return False
    # make sure it maps to a volume or another assign
    split = self._split_volume_remainder(path_name)
    if split is None:
      log_path.error(
          "assign has to map to volume or another assign: %s", path_name)
      return False
    return True

  def _split_volume_remainder(self, ami_path):
    """return (volume, remainder) or none if no volume found"""
    pos = ami_path.find(':')
    # no assign expansion
    if pos <= 0:
      return None
    else:
      name = ami_path[:pos].lower()
      if ami_path[-1] == ':':
        remainder = ''
      else:
        remainder = ami_path[pos+1:]
      return (name, remainder)

  def resolve_assigns(self, ami_path, recursive=True):
    """replace all assigns found in path until only a volume path exists.
       do not touch relative paths.

        return: original path if path is not absolute
        or: string if no multi assigns are involved
        or: list of string if multi assigns were encountered
        or: None if neither assign nor volume is given
    """
    log_path.info("resolve_assign: ami_path='%s'", ami_path)
    split = self._split_volume_remainder(ami_path)
    if split is None:
      # relative path
      log_path.debug("resolve_assign: ami_path='%s' is rel_path!",
                     ami_path)
      return ami_path
    else:
      # is assign
      name = split[0].lower()
      if self.assigns.has_key(name):
        aname_list = self.assigns[name]
        # single assign
        if len(aname_list) == 1:
          aname = aname_list[0]
          new_path = aname + split[1]
          log_path.info("resolve_assign: ami_path='%s' -> single assign: '%s'",
                        ami_path, new_path)
          if recursive:
            return self.resolve_assigns(new_path)
          else:
            return new_path
        # multi assign
        else:
          result = []
          for aname in aname_list:
            new_path = aname + split[1]
            log_path.info(
                "resolve_assign: ami_path='%s' -> multi assign: '%s'",
                ami_path, new_path)
            if recursive:
              new_path = self.resolve_assigns(new_path)
              if new_path is None:
                return None
            if type(new_path) is str:
              result.append(new_path)
            else:
              result += new_path
          return result
      # is volume path
      elif self.vol_mgr.is_volume(name):
        log_path.debug("resolve_assign: ami_path='%s' is vol_path!",
                       ami_path)
        return ami_path
      # invalid assign/volume
      else:
        log_path.error("resolve_assign: ami_path='%s' has invalid prefix!",
                       ami_path)
        return None
