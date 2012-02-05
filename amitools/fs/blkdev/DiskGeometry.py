import amitools.util.ByteSize as ByteSize

class DiskGeometry:
  def __init__(self, cyls=0, heads=0, secs=0):
    self.cyls = cyls
    self.heads = heads
    self.secs = secs
  
  def __str__(self):
    size = self.get_num_bytes()
    return "chs=%d,%d,%d size=%d/%s" % (self.cyls, self.heads, self.secs, size, ByteSize.to_byte_size_str(size))
  
  def get_num_blocks(self):
    """return the number of block allocated by geometry"""
    return self.cyls * self.heads * self.secs
    
  def get_num_bytes(self, block_bytes=512):
    """return the number of bytes allocated by geometry"""
    return self.get_num_blocks() * block_bytes
  
  def detect(self, byte_size, options=None, block_bytes=512):
    """detect a geometry from a given image size and optional options.
       return bytes required by geometry or None if geomtry is invalid
    """
    c = None
    h = None
    s = None
    num_blocks = byte_size / block_bytes
    algo = None
    if options != None:
      (c, h, s) = self._parse_chs(options)
      if options.has_key('algo'):
        algo = int(options['algo'])
    # chs if fully specified then take this one
    if c != None and h != None and s != None:
      self.cyls = c
      self.heads = h
      self.secs = s
      size = self.get_num_bytes()
      if size == byte_size:
        return size
      else:
        return None 
    else:
      return self._guess_for_size(byte_size, algo=algo, secs=s, heads=h)
    
  def setup(self, options, block_bytes=512):
    """setup a new geometry by giving options
       return bytes required by geometry or None if geometry is invalid
    """
    if options == None:
      return False
    c = None
    h = None
    s = None
    (c, h, s) = self._parse_chs(options)
    # chs is fully specified
    if c != None and h != None and s != None:
      self.cyls = c
      self.heads = h
      self.secs = s
      return self.get_num_bytes()
    else:
      # we require a size
      if not options.has_key('size'):
        return None
      # parse size
      size = options['size']
      if type(size) != int:
        size = ByteSize.parse_byte_size_str(size)
        if size == None:
          return None
      # select guess algo
      algo = None
      if options.has_key('algo'):
        algo = int(options['algo'])
      # guess size
      return self._guess_for_size(size, approx=True, algo=algo, secs=s, heads=h)  
  
  def _parse_chs(self, options):
    c = None
    h = None
    s = None
    # chs=<n>,<n>,<n>
    if options.has_key('chs'):
      comp = options['chs'].split(',')
      if len(comp) == 3:
        return map(lambda x: int(x), comp)
    else:
      if options.has_key('s'):
        s = int(options['s'])
      if options.has_key('h'):
        h = int(options['h'])
      if options.has_key('c'):
        c = int(options['c'])
    return (c,h,s)
  
  def _guess_for_size1(self, size, approx=True, block_bytes=512, secs=None, heads=None):
    mb = size / 1024
    if secs == None:
      secs = 63
    if heads == None:  
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

  def _guess_for_size2(self, size, approx=True, block_bytes=512, secs=None, heads=None):
    if heads == None:
      heads = 1
    if secs == None:
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
  
  def _guess_for_size(self, size, approx=True, block_bytes=512, algo=None, secs=None, heads=None):
    if algo == 1:
      return self._guess_for_size1(size, approx, block_bytes, secs, heads)
    elif algo == 2:
      return self._guess_for_size2(size, approx, block_bytes, secs, heads)
    else:
      algos = [self._guess_for_size1, self._guess_for_size2]
      if approx:
        # find min diff to real size
        min_diff = size
        min_algo = None
        for a in algos:
          s = a(size, True, block_bytes, secs, heads)
          if s != None:
            delta = abs(size - s)
            if delta < min_diff:
              min_diff = delta
              min_algo = a
        if min_algo != None:
          return min_algo(size, True, block_bytes, secs, heads)
        else:
          return None
      else: # exact match
        for a in algos:
          s = a(size, True, block_bytes, secs, heads)
          if s == size:
            return size
        return None
