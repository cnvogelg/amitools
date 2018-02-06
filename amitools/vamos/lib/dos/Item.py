
class ItemParser:
  """parse items like AmigaDOS splits its argument list"""

  ITEM_EQUAL = -2
  ITEM_ERROR = -1
  ITEM_NOTHING = 0
  ITEM_UNQUOTED = 1
  ITEM_QUOTED = 2

  def __init__(self, csrc):
    """set character source csrc that supports getc() and ungetc()"""
    self.csrc = csrc

  def read_item(self, maxchars):
    """returns (ITEM_*, buf)"""
    null = chr(0)

    # skip leading whitespace
    while True:
      ch = self.csrc.getc()
      if ch not in (" ", "\t"):
        break

    # already a terminal char?
    if ch in (None, null, "\n", ";"):
      self.csrc.ungetc()
      return (self.ITEM_NOTHING, None)

    # equal sign?
    if ch == "=":
      return (self.ITEM_EQUAL, None)

    res = []
    status = self.ITEM_NOTHING

    # quoted string?
    if ch == "\"":
      while True:
        # no more room?
        if maxchars == 0:
          res.pop()
          status = self.ITEM_ERROR
          break
        # get next char
        maxchars -= 1
        ch = self.csrc.getc()
        # quoted char?
        if ch == "*":
          ch = self.csrc.getc()
          # early end?
          if ch in (None, null, "\n"):
            status = self.ITEM_ERROR
            self.csrc.ungetc()
            break
          elif ch in ("n", "N"):
            ch = "\n"
          elif ch in ("e", "E"):
            ch = chr(0x1b)
        # early end?
        elif ch in (None, null, "\n"):
          status = self.ITEM_ERROR
          self.csrc.ungetc()
          break
        elif ch == "\"":
          status = self.ITEM_QUOTED
          break
        res.append(ch)

    # unquoted string
    else:
      # store current char
      if maxchars == 0:
        status = self.ITEM_ERROR
      else:
        maxchars -= 1
        res.append(ch)
        while True:
          if maxchars == 0:
            res.pop()
            status = self.ITEM_ERROR
            break
          maxchars -= 1
          # get next char
          ch = self.csrc.getc()
          # terminate
          if ch in (None, null, "\n"):
            status = self.ITEM_UNQUOTED
            self.csrc.ungetc()
            break
          if ch in (" ", "\t", "="):
            # Know Bug: Don't UNGET for a space or equals sign
            status = self.ITEM_UNQUOTED
            break
          res.append(ch)

    # build final string
    res_str = ''.join(res)
    return status, res_str
