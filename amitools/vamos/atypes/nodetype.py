import inspect


class NodeType(object):
  """manage valid node type constants and conversions"""
  NT_UNKNOWN = 0
  NT_TASK = 1
  NT_INTERRUPT = 2
  NT_DEVICE = 3
  NT_MSGPORT = 4
  NT_MESSAGE = 5
  NT_FREEMSG = 6
  NT_REPLYMSG = 7
  NT_RESOURCE = 8
  NT_LIBRARY = 9
  NT_MEMORY = 10
  NT_SOFTINT = 11
  NT_FONT = 12
  NT_PROCESS = 13
  NT_SEMAPHORE = 14
  NT_SIGNALSEM = 15
  NT_BOOTNODE = 16
  NT_KICKMEM = 17
  NT_GRAPHICS = 18
  NT_DEATHMESSAGE = 19

  NT_USER = 254
  NT_EXTENDED = 255

  @classmethod
  def to_str(cls, nt):
    mem = inspect.getmembers(cls)
    for name, val in mem:
      if name.startswith('NT_') and type(val) is int:
        if nt == val:
          return name
    raise ValueError("%s is an unknown NodeTyp value" % nt)

  @classmethod
  def from_str(cls, ntstr):
    mem = inspect.getmembers(cls)
    for name, val in mem:
      if name.startswith('NT_') and type(val) is int:
        if name == ntstr:
          return val
    raise ValueError("'%s' is an unknown NodeTyp string" % ntstr)
