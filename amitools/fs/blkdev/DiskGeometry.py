class DiskGeometry:
  def __init__(self, cyls=0, heads=0, secs=0):
    self.cyls = cyls
    self.heads = heads
    self.secs = secs
  
  def __str__(self):
    return "cyl=%d,heads=%d,secs=%d" % (self.cyls, self.heads, self.secs)
  
  def guess_for_size1(self, size, approx=True, block_bytes=512):
    mb = size / 1024
    secs = 63
    if mb <= 504 * 1024:
      heads = 16
    elif mb <= 1008 * 1024:
      heads = 32
    elif mb <= 2016 * 1024:
      heads = 64
    elif mb <= 4032 * 1024:
      heads = 128
    else:
      heads = 256
    cyls = (size / block_bytes) / (secs * heads)
    geo_size = cyls * secs * heads * block_bytes
    # keep approx values or match
    if approx or geo_size == size:
      self.cyls = cyls
      self.heads = heads
      self.secs = secs
      return geo_size
    else:
      return None

  def guess_for_size2(self, size, approx=True, block_bytes=512):
    heads = 1
    secs = 32
    cyls = (size / block_bytes) / (secs * heads)
    # keep approx values or match
    geo_size = cyls * secs * heads * block_bytes
    if approx or geo_size == size:
      self.cyls = cyls
      self.heads = heads
      self.secs = secs
      return geo_size
    else:
      return None
  
  def guess_for_size(self, size, approx=True, block_bytes=512, algo=None):
    if algo == 1:
      return self.guess_for_size1(size, approx, block_bytes)
    elif algo == 2:
      return self.guess_for_size2(size, approx, block_bytes)
    else:
      algos = [self.guess_for_size1, self.guess_for_size2]
      if approx:
        # find min diff to real size
        min_diff = size
        min_algo = None
        for a in algos:
          s = a(size, True, block_bytes)
          if s != None:
            delta = abs(size - s)
            if delta < min_diff:
              min_diff = delta
              min_algo = a
        if min_algo != None:
          return min_algo(size, True, block_bytes)
        else:
          return None
      else: # exact match
        for a in algos:
          s = a(size, True, block_bytes)
          if s == size:
            return size
        return None
        
  def parse_size_str(self, size_str):
    if len(size_str) == 0:
      return False
    unit = 1
    if size_str[-1] in "kKgGmM":
      unit = size_str[-1].lower()
      if unit == 'k':
        unit = 1024
      elif unit == 'm':
        unit = 1024 * 1024
      elif unit == 'g':
        unit = 1024 * 1024 * 1024
      else:
        return False
      size_str = size_str[:-1]
    try:
      size = int(size_str)
      return self.guess_for_size(size * unit)
    except ValueError:
      return False
  
  def parse_chs_str(self, chs_str):
    comp = chs_str.split(',')
    if len(comp) != 3:
      return False
    try:
      c,h,s = map(lambda x: int(x), comp)
      self.cyls = c
      self.heads = h
      self.secs = s
      return True
    except ValueError:
      return False

    
    