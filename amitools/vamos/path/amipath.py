class AmiPathError(Exception):
  def __init__(self, path, reason):
    self.path = path
    self.reason = reason

  def __str__(self):
    return "AmiPathError: %s: %s" % (self.path, self.reason)


class AmiPath(object):
  """holds a single Amiga path either in relative or absolute format.

  A path is considered 'absolute' if it starts with a volume: or
  assign: prefix.

  A relative path can only be resolved with the current directory stored
  in the associated path environment.

  A colon prefixed path is also considered relative, e.g. ':bla'.
  It is local to the prefix of the current directory.

  The empty string '' represents the current directory of the associated
  environment.

  In a 'volume path' all assigns are resolved and it
  always starts with a valid volume: prefix.

  Valid path syntax is:

  (prefix:)?(name)?(/name)+/?

  prefix: all but '/:', may be empty
  name: all but '/:', non-empty

  ':/', '//' is invalid
  """

  def __init__(self, pstr=""):
    self.pstr = pstr

  def __str__(self):
    return self.pstr

  def __repr__(self):
    return "AmiPath('{}')".format(self.pstr)

  def is_local(self):
    """is it a local path?"""
    return self.pstr.find(':') <= 0

  def is_absolute(self):
    """is it an absolute path starting with a volume/assign prefix?"""
    return self.pstr.find(':') > 0

  def is_parent_local(self):
    """check if the path is relative to parent"""
    p = self.pstr
    return len(p) > 0 and p[0] == '/'

  def is_prefix_local(self):
    """check if the path is relative to the prefix"""
    p = self.pstr
    return len(p) > 0 and p[0] == ':'

  def is_name_only(self):
    """check if the relative path is a single name only"""
    p = self.pstr
    if len(p) == 0:
      return False
    ps = p.find('/')
    pc = p.find(':')
    return ps == -1 and pc == -1

  def ends_with_name(self):
    """make sure the path ends with a name

    A path ending with / or : is not valid.
    """
    p = self.pstr
    # empty is invalid
    if len(p) == 0:
      return False
    # last char must not be colon or slash
    lc = p[-1]
    if lc == '/' or lc == ':':
      return False
    return True

  def prefix(self, lower=False):
    """if the path is absolute then a prefix string is returned.

    The prefix in a valid abs path is either an assign or volume name.

    A relative path has a None prefix.
    """
    pos = self.pstr.find(':')
    if pos <= 0:
      return None
    else:
      res = self.pstr[:pos]
      if lower:
        res = res.lower()
      return res

  def postfix(self, skip_leading=False, lower=False):
    """the postfix string of the path.

    A relative path is returned as is.
    The postifx of an absolute path is starting with the colon ':'
    """
    p = self.pstr
    pos = p.find(':')
    # skip prefix
    if pos > 0:
      p = p[pos+1:]
    # strip trailing slash if any
    if len(p) > 1 and p[-1] == '/':
      p = p[:-1]
    # strip parent local
    if skip_leading and len(p) > 0 and p[0] in ('/', ':'):
      p = p[1:]
    if lower:
      p = p.lower()
    return p

  @classmethod
  def build(cls, prefix=None, postfix=""):
    """rebuild a path from prefix and postfix"""
    if prefix is None:
      pstr = postfix
    else:
      pstr = prefix + ":" + postfix
    return cls(pstr)

  def rebuild(self, prefix, postfix):
    return AmiPath.build(prefix, postfix)

  def __eq__(self, other):
    if type(other) is str:
      other = AmiPath(other)
    elif not isinstance(other, AmiPath):
      return False
    # case insensitive
    return self.prefix(lower=True) == other.prefix(lower=True) and \
        self.postfix(lower=True) == other.postfix(lower=True)

  def __ne__(self, other):
    if type(other) is str:
      other = AmiPath(other)
    elif not isinstance(other, AmiPath):
      return True
    return self.prefix(lower=True) != other.prefix(lower=True) or \
        self.postfix(lower=True) != other.postfix(lower=True)

  def is_valid(self):
    if not self.is_syntax_valid():
      return False
    if self.is_absolute():
      return self.is_prefix_valid()
    else:
      return True

  def is_syntax_valid(self):
    """check if a path has valid syntax.

    Returns True if all checks passed otherwise False
    """
    # valid cases
    s = self.pstr
    if s in (':', '', '/'):
      return True
    # invalid cases
    if s.find('//') != -1:
      return False
    # colon/slash check
    colon_pos = self.pstr.find(':')
    slash_pos = self.pstr.find('/')
    # a slash before the colon is not allowed
    if slash_pos > -1 and slash_pos < colon_pos:
      return False
    # slash follows colon
    if colon_pos > -1 and colon_pos + 1 == slash_pos:
      return False
    # is there a second colon?
    if colon_pos != -1:
      other_pos = self.pstr.find(':', colon_pos+1)
      if other_pos != -1:
        return False
    # all checks passed
    return True

  def parent(self):
    """return a new path with the last path component removed.

    Returns None if stripping is not possible.

    The path is not expanded (to a absolute or even volume path)!

    Example:
        bar -> ''
        foo/bar -> foo
        baz:foo/bar -> baz:foo
        baz:foo -> ''
        /bar -> /
        / -> None
        :foo -> foo
        foo: -> None
    """
    p = self.postfix()
    if p in ('/', ':'):
      return None
    last_pos = p.rfind('/')
    if last_pos == -1:
      col_pos = p.find(':')
      # special case: ":foo" -> ":"
      if col_pos == 0:
        postfix = ':'
      # "foo:"
      elif col_pos == len(p) - 1:
        return None
      else:
        postfix = ''
    elif last_pos == 0:
      postfix = '/'
    else:
      postfix = p[:last_pos]
    return self.rebuild(self.prefix(), postfix)

  def get_names(self, with_special_name=False):
    """return a list of strings with the names contained in postfix

    Note if skip_leading is False then a parent or prefix local path
    gets a special name prefixed: '/' or ':'
    """
    p = self.postfix(not with_special_name)
    n = len(p)
    if n == 0:
      return []
    # add leading char as a special name
    if n > 0 and p[0] in ('/', ':'):
      res = [p[0]]
      if n == 1:
        return res
      else:
        return res + p[1:].split('/')
    else:
      return p.split("/")

  def join(self, opath):
    """join this path with the given path.

    If expand is True then this path can be made absolute if necessary.

    Note:May return None if join is not possible.
    """
    # if other is absolute then replace my path
    if opath.is_absolute():
      return opath
    # other is parent relative?
    elif opath.is_parent_local():
      if self.is_parent_local():
        raise AmiPathError(
            self, "can't join two parent relative paths")
      # try to strip last name of my path
      my = self.parent()
      if my is not None:
        prefix = self.prefix()
        my_post = my.postfix()
        if my_post == '':
          postfix = opath.postfix(True)
        elif my_post == ':':
          postfix = ':' + opath.postfix(True)
        else:
          postfix = my_post + opath.postfix()
        return self.rebuild(prefix, postfix)
      else:
        raise AmiPathError(self, "can't join parent relative path")
    # other is prefix local: ':bla'
    elif opath.is_prefix_local():
      prefix = self.prefix()
      skip = False if prefix is None else True
      postfix = opath.postfix(skip)
      return self.rebuild(prefix, postfix)
    # other is local
    else:
      prefix = self.prefix()
      my_post = self.postfix()
      o_post = opath.postfix()
      if my_post == '':
        postfix = o_post
      elif my_post in ('/', ':'):
        postfix = my_post + o_post
      else:
        postfix = my_post + '/' + o_post
      return self.rebuild(prefix, postfix)
