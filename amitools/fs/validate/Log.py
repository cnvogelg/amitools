class LogEntry:
  """A class for a log entry"""
  names = ('debug','info ','WARN ','ERROR','FATAL')
  
  def __init__(self, level, msg, blk_num=-1):
    self.blk_num = blk_num
    self.level = level
    self.msg = msg
  def __str__(self):
    if self.blk_num == -1:
      return "%s%s:%s" % (" "*8, self.names[self.level], self.msg)
    else:
      return "@%06d:%s:%s" % (self.blk_num, self.names[self.level], self.msg)

class Log:
  """Store a log of entries"""

  DEBUG = 0
  INFO = 1
  WARN = 2
  ERROR = 3
  FATAL = 4

  def __init__(self, debug=False):
    self.entries = []
    self.debug = debug
  
  def msg(self, level, msg, blk_num = -1):
    if not self.debug and level == self.DEBUG:
      return
    e = LogEntry(level, msg, blk_num)
    self.entries.append(e)
  
  def dump(self):
    for e in self.entries:
      print e
  