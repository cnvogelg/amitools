class FileName:
  def __init__(self, name, is_intl=False):
    self.name = name
    self.is_intl = is_intl
  
  def __str__(self):
    return name
  
  def to_upper(self):
    result = self.name.upper();
    if self.is_intl:
      for i in xrange(len(result)):
        o = ord(result[i])
        if o >= 224 and o <= 254 and o != 247:
          result[i] = chr(o - (ord('a')-ord('A')))
    return result
  
  def is_valid(self):
    for c in self.name:
      o = ord(c)
      if o == ':' or o == '/':
        return False
      if not self.is_intl and o > 127:
        return False
    return True
  
  def hash(self, hash_size=72):
    up = self.to_upper();
    h = len(up)
    for c in up:
      h = h * 13;
      h += ord(c)
      h &= 0x7ff
    h = h % hash_size
    return h
