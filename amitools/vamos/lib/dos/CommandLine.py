class CommandLine:
  def __init__(self):
    self.reset()
    
  def __str__(self):
    return "[args=%s, in=%s, out=%s, append=%s]" % (self.args, self.redir_in, self.redir_out, self.append_out)

  def reset(self):
    self.args = []
    self.redir_in = None
    self.redir_out = None
    self.append_out = False

  def parse_string(self, in_str):
    ok = self._split(in_str)
    if not ok:
      return False
    self._build()
    return True
  
  def parse_args(self, args):
    self.raw_args = args
    # determine redir pos
    self.redir_pos = []
    pos = 0
    for a in args:
      if len(a)>0 and a[0] in ('>','<'):
        self.redir_pos.append(pos)
      pos += 1
    self._build()
  
  def _split(self, in_str):
    arg_begin = True
    in_quote = False
    quote_next = False
    is_redir = False
    arg = ""
    redir_pos = []
    args = []
    for c in in_str:
      # handle quoted string
      if in_quote:
        # end of quote
        if c == '"' and not quote_next:
          in_quote = False
          args.append(arg)
          arg = ""
          arg_begin = True
        # quote next 
        elif c == '*' and not quote_next:
          quote_next = True
        # any other char
        else:
          quote_next = False
          arg += c
    
      # non quoting range
      else:
        # white space
        if c in ('\t',' '):
          # store last
          if arg != "":
            args.append(arg)
            arg = ""
          arg_begin = True
        # quote begin
        elif c == '"' and arg_begin:
          # if an arg was begun add that first
          if arg != "":
            args.append(arg)
            arg = ""
          arg = ""
          in_quote = True
          arg_begin = False
        # start of redir?
        elif c in ('<', '>'):
          if arg_begin:
            redir_pos.append(len(args))
          arg += c
        # any other char
        else:
          arg += c
          arg_begin = False
  
    # add last
    if arg != "":
      args.append(arg)
  
    # check state
    if in_quote or quote_next:
      return False
      
    self.raw_args = args
    self.redir_pos = redir_pos
    return True
  
  def _setup_redir(self, prefix, redir):
    if prefix == '<': 
      # none redir yet -> use it
      if self.redir_in == None:
        self.redir_in = redir
      # redir already active -> next could be redir
      else:
        self.args.append(redir)
    else:
      # none redir yet -> use it
      if self.redir_out == None:
        # check for append
        if prefix == '>>':
          self.append_out = True
        self.redir_out = redir
      # redir already active -> keep as arg
      else:
        self.args.append(prefix + redir)
  
  def _build(self):
    self.reset()
    pos = 0
    next_is_redir = None    
    for a in self.raw_args:
      # is a potential redirection
      if pos in self.redir_pos and next_is_redir == None:
        # only the redir char '<' or '>' -> next arg is redir
        if len(a) == 1:
          next_is_redir = a
        elif a == '>>':
          next_is_redir = a
        elif len(a) == 2 and a[0:2] == '>>':
          self._setup_redir('>>',a[2:])
        else:
          self._setup_redir(a[0],a[1:])
      # no redir arg
      else:
        if next_is_redir != None:
          self._setup_redir(next_is_redir,a)
          next_is_redir = None
        else:
          self.args.append(a)
      pos += 1

    # last was potential redir -> add it plain
    if next_is_redir != None:
      self.args.append(next_is_redir)

# test
if __name__ == '__main__':
  import sys
  cl = CommandLine()
  # one argument: interpret as command line
  if len(sys.argv) == 2:
    cl.parse_string(sys.argv[1])
  # multiple args
  else:
    cl.parse_args(sys.argv[1:])
  print cl
  