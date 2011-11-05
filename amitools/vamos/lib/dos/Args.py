"""generate an internal representation of an AmigaDOS ReadArgs compatible arg parse template
"""
def gen_dos_args(template):
  targs = []
  ps = template.split(',')
  for p in ps:
    flags = p.split('/')
    keys = map(lambda x : x.lower(), flags[0].split('='))
    targ = { 'keys' : keys,
             's' : False, 'k' : False, 'n' : False, 't' : False, 
             'a' : False, 'f' : False, 'm' : False, 'n' : False }

    # get keys
    for flag in flags[1:]:
      flag = flag.lower()[0]
      if targ.has_key(flag):
        targ[flag] = True

    # n = normal switch = not s,t,k,f
    targ['n'] = not (targ['s'] or targ['t'] or targ['k'] or targ['f'])

    targs.append(targ)
  
  return targs

def _find_remove_key(keys, in_list, extra):
  n = len(in_list)
  for key in keys:
    pos = 0
    for i in in_list:
      if i.lower() == key:
        break
      pos = pos + 1
    if pos != n:
      in_list.pop(pos)
      # extra arg?
      if extra:
        # last one? -> failed to get extra arg
        if pos == n-1:
          return None
        val = in_list[pos]
        in_list.pop(pos)
        return val
      else:
        return True
  return False

"""apply an internal template to a given argument array
"""
def parse_dos_args(targs, in_args, in_result=[]):
  # get args and split = into args, too
  args = []
  for a in in_args:
    b = a.split('=')
    args += b
  
  # prepare result array
  result = in_result[:]
  while len(result) < len(targs):
    result.append(None)
  
  # scan through args and look for keyword named entries
  pos = 0
  for targ in targs:
    req = targ['a']
    # switch
    if targ['s']:
      val = _find_remove_key(targ['keys'], args, False)
      if val:
        result[pos] = True
      else:
        result[pos] = False
        if req:
          return None # sensible? switch with a ??
    # toggle
    elif targ['t']:
      val = _find_remove_key(targ['keys'], args, False)
      if val:
        result[pos] = not result[pos]
      elif req:
        return None
    # keyword
    elif targ['k']:
      val = _find_remove_key(targ['keys'], args, True)
      if val == None:
        return None
      if val != False:
        if targ['n']:
          val = int(val)
        result[pos] = val
    # full line
    elif targ['f']:
      result[pos] = args
      args = []
    pos = pos + 1
    
  # scan for multi and non-key args
  multi_pos = None
  multi_targ = None
  pos = 0
  for targ in targs:  
    # multi 
    if targ['m']:
      multi_pos = pos
      multi_targ = targ
      result[pos] = args
      args = []
    # normal entry
    elif targ['n']:
      # take from arraay
      if len(args)>0:
        val = args[0]
        del args[0]
      # no more value in arg
      else:
        val = None
        if req: # try to get from multi
          if multi_pos != None and len(result[multi_pos]>0):
            val = result[multi_pos][-1]
            result[multi_pos] = result[multi_pos][:-1]
            # oops multi is empty!
            if multi_targ['a'] and len(result[multi_pos]==0):
              return None
          else: # failed!
            return None
      result[pos] = val
    pos = pos + 1
  
  # something left?
  if len(args)>0:
    return None
  
  return result
