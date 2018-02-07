import types
from Error import *


class TemplateArg:
  """a parsed description of a template argument"""
  TYPE_STRING = 0
  TYPE_NUMBER = 1
  TYPE_SWITCH = 2
  TYPE_TOGGLE = 3

  def __init__(self, keys, ktype, is_keyword=False, is_required=False,
               is_multi=False, is_full=False):
    self.keys = keys
    self.ktype = ktype
    self.is_keyword = is_keyword
    self.is_required = is_required
    self.is_multi = is_multi
    self.is_full = is_full
    self.pos = 0

  def __str__(self):
    return "(#%d:%s,%d,k=%s,r=%s,m=%s,f=%s)" % (
      self.pos, ",".join(self.keys), self.ktype,
      self.is_keyword, self.is_required,
      self.is_multi, self.is_full)

  def has_key(self, name):
    key = name.upper()
    return key in self.keys

  @classmethod
  def parse_string(cls, template):
    """parse a template string keya=keyb/n/k"""
    p = filter(lambda x: x!='', template.split("/"))
    if len(p) == 0:
      return None
    keys_all = p[0]
    flags_all = p[1:]
    if keys_all == '':
      return None
    # keys
    keys = map(lambda x: x.upper(), filter(lambda x: x!='', keys_all.split('=')))
    if len(keys) == 0:
      return None
    # flags
    flags = map(lambda x: x[0].upper(), flags_all)
    ktype = cls.TYPE_STRING
    is_keyword = False
    is_required = False
    is_multi = False
    is_full = False
    for ch in flags:
      if ch == 'N':
        ktype = cls.TYPE_NUMBER
      elif ch == 'S':
        ktype = cls.TYPE_SWITCH
        is_keyword = True
      elif ch == 'T':
        ktype = cls.TYPE_TOGGLE
        is_keyword = True
      elif ch == 'A':
        is_required = True
      elif ch == 'K':
        is_keyword = True
      elif ch == 'M':
        is_multi = True
      elif ch == 'F':
        is_full = True
    return TemplateArg(keys, ktype, is_keyword, is_required, is_multi, is_full)


class TemplateArgList:
  """a parsed list of TemplateArg"""
  def __init__(self):
    self.targs = []

  def __str__(self):
    return "[#%d:%s]" % (self.len(), ",".join(map(str, self.targs)))

  def append(self, targ):
    targ.pos = len(self.targs)
    self.targs.append(targ)

  def len(self):
    return len(self.targs)

  def get_arg(self, pos):
    if pos < 0 or pos >= len(self.targs):
      return None
    else:
      return self.targs[pos]

  def find_arg(self, name):
    for t in self.targs:
      if t.has_key(name):
        return t

  @staticmethod
  def parse_string(template):
    tal = TemplateArgList()
    ps = template.split(',')
    for p in ps:
      if p != '':
        targ = TemplateArg.parse_string(p)
        if targ is None:
          return None
        tal.append(targ)
    return tal


class ParseResultList:
  """the class holds the parsing results. each template arg gets assigned
     a single item (or not)"""

  def __init__(self, targ_list):
    """create with a template arg list"""
    self.targ_list = targ_list
    self.len = targ_list.len()
    self.result = [None] * self.len

  def __str__(self):
    return ",".join(map(str, self.result))

  def get_result(self, pos):
    return self.result[pos]

  def set_result(self, pos, val):
    self.result[pos] = val

  def calc_extra_result_size(self):
    """return size of extra result in bytes.
       we count the longs and chars that do not fit into the
       result long array passed into ReadArgs()

       return size in bytes, number of longs
    """
    num = self.len
    num_longs = 0
    num_chars = 0
    for pos in xrange(num):
      r = self.result[pos]
      if r is not None:
        targ = self.targ_list.get_arg(pos)
        ktype = targ.ktype
        if targ.is_multi:
          # account list itself + null long
          n = len(r)
          if n > 0:
            num_longs += n + 1
            if ktype == TemplateArg.TYPE_STRING:
              # reserve string + null byte
              for s in r:
                num_chars += len(s) + 1
            elif ktype == TemplateArg.TYPE_NUMBER:
              # reserve longs
              num_longs += n
        elif ktype == TemplateArg.TYPE_STRING or targ.is_full:
          # store string + null byte
          num_chars += len(r) + 1
        elif ktype == TemplateArg.TYPE_NUMBER:
          num_longs += 1

    # calc total size
    size = num_longs * 4 + num_chars
    return size, num_longs

  def generate_result(self, mem_access, array_ptr, extra_ptr, num_longs):
    """now convert the values into memory array and extra array"""
    num = self.len
    char_ptr = extra_ptr + num_longs * 4
    long_ptr = extra_ptr
    for pos in xrange(num):
      targ = self.targ_list.get_arg(pos)
      ktype = targ.ktype
      r = self.result[pos]
      base_val = None
      if r is None:
        if targ.is_multi:
          # always set array pointer to 0
          base_val = 0
      else:
        if targ.is_multi:
          n = len(r)
          if n == 0:
            base_val = 0
          else:
            if ktype == TemplateArg.TYPE_STRING:
              # pointer to array
              base_val = long_ptr
              for s in r:
                mem_access.w32(long_ptr, char_ptr)
                mem_access.w_cstr(char_ptr, s)
                long_ptr += 4
                char_ptr += len(s) + 1
            elif ktype == TemplateArg.TYPE_NUMBER:
              # first the values
              val_ptr = long_ptr
              # then the pointers to the values
              long_ptr += n * 4
              base_val = long_ptr
              for i in r:
                mem_access.w32(long_ptr, val_ptr)
                mem_access.w32(val_ptr, i)
                long_ptr += 4
                val_ptr += 4
            # terminate pointer list
            mem_access.w32(long_ptr,0)
            long_ptr += 4
        elif ktype == TemplateArg.TYPE_STRING or targ.is_full:
          # store string + null byte
          base_val = char_ptr
          # append string
          mem_access.w_cstr(char_ptr, r)
          char_ptr += len(r) + 1
        elif ktype == TemplateArg.TYPE_NUMBER:
          # pointer to long
          base_val = long_ptr
          # write long
          mem_access.w32(long_ptr,r)
          long_ptr += 4
        elif ktype == TemplateArg.TYPE_SWITCH:
          base_val = -1
        elif ktype == TemplateArg.TYPE_TOGGLE:
          old_val = mem_access.r32(array_ptr)
          base_val = 0 if old_val else -1

      # update array pointer
      if base_val is not None:
        mem_access.w32(array_ptr, base_val)
      array_ptr += 4


#
# THOR: FIXME: /F arguments eat *all* arguments, not just
# the rest of the line. "set echo on" does not work due to
# this problem.
#
class Args:

  def __init__(self):
    self.targs = None
    self.in_val = None
    self.result = None

  def parse_template(self, template):
    """generate an internal representation of an AmigaDOS ReadArgs compatible arg parse template
    """
    self.targs = []
    ps = template.split(',')
    for p in ps:
      flags = p.split('/')
      keys = map(lambda x : x.lower(), flags[0].split('='))
      targ = { 'keys' : keys,
               's' : False, 'k' : False, 'n' : False, 't' : False,
               'a' : False, 'f' : False, 'm' : False, 'n' : False,
               'x' : False }

      # get keys
      for flag in flags[1:]:
        flag = flag.lower()[0]
        if targ.has_key(flag):
          targ[flag] = True

      # x = normal switch = not s,t,k,f
      targ['x'] = not (targ['s'] or targ['t'] or targ['k'] or targ['f'])

      self.targs.append(targ)

  def prepare_input(self,mem_access,ptr):
    # read org values
    self.in_val = []
    for t in self.targs:
      raw = mem_access.r32(ptr)
      # prefill toggle
      if t['t']:
        self.in_val.append(bool(raw))
      else:
        self.in_val.append(None)
      ptr += 4

  def split(self,argstring):
    args=[]
    # AmigaOs quoting rules are weird!
    # This is a simplified version of the shell
    # argument parsing.
    arg      = ""
    inquote  = False
    inspace  = True
    asterisk = False
    lastb    = None
    for b in argstring:
      if asterisk:
        if b == 'E' or b ==' e':
          arg += chr(27)
        elif b == 'N' or b == 'n':
          arg += chr(10)
        else:
          arg += b
        asterisk = False
      elif inspace:
        if not (b == ' ' or b == '\t' or b == '\n'):
          inspace = False
          arg     = ""
          if b == '"':
            inquote = True
          else:
            arg    += b
      elif inquote:
        if b == '*':
          asterisk = True
        elif b == '"':
          inquote = False
          inspace = True
          args   += [arg]
          arg     = ""
        else:
          arg += b
      else:
        if b == ' ' or b == '\t' or b == '\n':
          args += [arg]
          arg   = ""
          inspace = True
        elif b == '"' and lastb == '=':
          args += [arg[:-1]]
          arg   = ""
          inspace = False
          inquote = True
        else:
          arg  += b
      lastb=b
    if arg != "":
      args += [arg]
    return args

  def _find_remove_key(self, keys, in_list, extra):
    pos = self._find_key_pos_and_remove(keys, in_list)
    if pos != None:
      # extra arg?
      if extra:
        # last one? -> failed to get extra arg
        n = len(in_list)
        if pos == n: # THOR: off-by-one error, note that in_list is now one element shorter
          return None
        val = in_list[pos]
        in_list.pop(pos)
        return val
      else:
        return True
    else:
      return False

  def _find_key_pos_and_remove(self, keys, in_list, remove=True):
    for key in keys:
      pos = 0
      for i in in_list:
        if i.lower() == key and key != "":
          if remove:
            in_list.pop(pos)
          return pos
        pos = pos + 1
    return None

  def find_arg(self,keyword):
    pos = 0
    for targ in self.targs:
      for key in targ['keys']:
        if key != "" and keyword.lower() == key:
          return pos
      pos = pos + 1
    return -1

  """apply an internal template to a given argument array, this already expects an array of strings.
  """
  def parse_string(self, in_args):
    self.error = NO_ERROR

    # get args and split = into args, too
    args = []
    for a in in_args:
      b = a.split('=')
      args += b

    # prepare result array
    result = []
    targs = self.targs
    while len(result) < len(targs):
      result.append(None)

    # scan through args and look for keyword named entries
    pos = 0
    for targ in targs:
      req = targ['a']

      # switch
      if targ['s']:
        val = self._find_remove_key(targ['keys'], args, False)
        if val:
          result[pos] = True
        else:
          result[pos] = False
          if req:
            self.error = ERROR_REQUIRED_ARG_MISSING
            return False # sensible? switch with a ??

      # toggle
      elif targ['t']:
        val = self._find_remove_key(targ['keys'], args, False)
        if val:
          result[pos] = not result[pos]
        elif req:
          self.error = ERROR_REQUIRED_ARG_MISSING
          return False

      # keyword
      elif targ['k'] and not targ['m']:
        val = self._find_remove_key(targ['keys'], args, True)
        # keyword at end of line
        if val == None:
          self.error = ERROR_REQUIRED_ARG_MISSING
          return False
        else:
          # found a real value
          if val != False:
            if targ['n']:
              val = int(val)
            else:
              val = self.unquote(val)
            result[pos] = val
          # keyword not found
          else:
            if req:
              self.error = ERROR_REQUIRED_ARG_MISSING
              return False

      # normal key but not multi
      elif targ['x'] and not targ['m']:
        # Check whether this is the last keypos. If so, do not
        # match by key, but rather take this as a literal
        # argument.
        found = self._find_key_pos_and_remove(targ['keys'], args, False)
        if found != None and found < len(args)-1:
          val = self._find_remove_key(targ['keys'], args, True)
          # keyword at end of line does not match standard keywords.
          if val == None:
            self.error = ERROR_REQUIRED_ARG_MISSING
            return False
          else:
            # found a real value
            if val != False:
              if targ['n']:
                val = int(val)
              else:
                val = self.unquote(val)
              result[pos] = val
              targ['x'] = False # disable to reject auto fill
      elif targ['f']:
        fullPos = pos
      pos = pos + 1

    # scan for multi and non-key args
    multi_pos = None
    multi_targ = None

    pos = 0
    for targ in targs:
      # multi
      if targ['m']:
        # try to find multi keys
        fpos = self._find_key_pos_and_remove(targ['keys'], args)
        if fpos != None:
          # use args after found pos
          multi_pos = fpos
          multi_targ = targ
          result[pos] = args[fpos:]
        else:
          # use current args
          multi_pos = pos
          multi_targ = targ
          result[pos] = args
        args = []
        # multi arg required
        if targ['a'] and len(result[pos])==0:
          self.error = ERROR_REQUIRED_ARG_MISSING
          return False
      pos = pos + 1

    pos = 0
    for targ in targs:
      # normal entry that is not yet filled
      if targ['x'] and result[pos] == None:
        # take from arraay
        if len(args)>0:
          val = self.unquote(args[0])
          del args[0]
        # no more value in arg
        else:
          val = None
          if targ['a']: # required -> try to get from multi
            if multi_pos != None and result[multi_pos] != None and len(result[multi_pos])>0:
              val = result[multi_pos][-1]
              result[multi_pos] = result[multi_pos][:-1]
              # oops multi is empty!
              if multi_targ['a'] and len(result[multi_pos])==0:
                self.error = ERROR_REQUIRED_ARG_MISSING
                return False
            else: # failed!
              self.error = ERROR_REQUIRED_ARG_MISSING
              return False
        if targ['n'] and val != None:
          val = int(val)
        else:
          val = self.unquote(val)
        result[pos] = val
      elif targ['f']:
        res = None
        # THOR: Reconstruct the rest of the line. Actually
        # this is not a good algorithm - separation into
        # arguments should not happen before ReadArgs, but
        # within ReadArgs. The following algorithm may
        # add quotes where none are needed, and also forgets
        # to re-escape special characters.
        for arg in args:
          if res == None:
            res = ""
          else:
            res = res + " "
          if arg == "" or arg.find(" ") >= 0:
            res = res + '"'+arg+'"'
          else:
            res = res + arg
        if res == None:
          res = ""
        result[fullPos] = res
        args = []

      pos = pos + 1

    # something left?
    if len(args)>0:
      self.error = ERROR_TOO_MANY_ARGS
      return False

    self.result = result
    return True

  #
  # This should probably do much more....
  def unquote(self,val):
    if val != None:
      if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    return val

  def get_result(self):
    res = []
    for i in xrange(len(self.result)):
      k = self.targs[i]['keys']
      msg = "%s:%s" % (",".join(k),self.result[i])
      res.append(msg)
    return "  ".join(res)

  def calc_result_size(self):
    n = len(self.result)
    num_longs = 0
    num_chars = 0
    for i in xrange(n):
      r = self.result[i]
      if r == None: # null pointer
        pass
      elif type(r) is types.StringType: # string key 'k'
        num_chars += len(r) + 1
      elif type(r) is types.IntType: # numerical key 'kn'
        num_longs += 1
      elif type(r) is types.ListType: # string list 'm'
        # only if list is not empty
        if len(r)>0:
          num_longs += len(r) + 1
          for s in r:
            num_chars += len(s) + 1

    # calc total size
    size = num_longs * 4 + num_chars

    self.num_longs = num_longs
    self.num_chars = num_chars
    self.size = size
    return size

  def generate_result(self,mem_access,addr,array_ptr):
    n = len(self.result)
    char_ptr = addr + self.num_longs * 4
    long_ptr = addr
    base_ptr = array_ptr
    for i in xrange(n):
      r = self.result[i]
      if r == None: # optional value not set ('k')
        base_val = 0
      elif type(r) is types.StringType:
        # pointer to string
        base_val = char_ptr
        # append string
        mem_access.w_cstr(char_ptr, r)
        char_ptr += len(r) + 1
      elif type(r) is types.IntType:
        # pointer to long
        base_val = long_ptr
        # write long
        mem_access.w32(long_ptr,r)
        long_ptr += 4
      elif type(r) is types.ListType:
        # array with longs + strs
        if len(r) == 0:
          # empty multi array
          base_val = 0
        else:
          # pointer to array
          base_val = long_ptr
          for s in r:
            mem_access.w32(long_ptr,char_ptr)
            mem_access.w_cstr(char_ptr,s)
            long_ptr += 4
            char_ptr += len(s) + 1
          mem_access.w32(long_ptr,0)
          long_ptr += 4
      else:
        # direct value
        base_val = r

      mem_access.w32(base_ptr,base_val)
      base_ptr += 4
    return self.result
