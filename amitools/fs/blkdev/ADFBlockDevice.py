from BlockDevice import BlockDevice
import ctypes
import gzip

class ADFBlockDevice(BlockDevice):
  def __init__(self, adf_file, read_only=False):
    self.adf_file = adf_file
    self.read_only = read_only
    self.dirty = False
    lo = adf_file.lower()
    self.gzipped = lo.endswith('.adz') or lo.endswith('.adf.gz')

  def create(self):
    if self.read_only:
      raise IOError("ADF creation not allowed in read-only mode!")    
    self._set_geometry() # set default geometry
    # allocate image in memory
    self.data = ctypes.create_string_buffer(self.num_bytes)
    self.dirty = True

  def open(self):
    self._set_geometry() # set default geometry
    # open adf file 
    if self.gzipped:
      fh = gzip.open(self.adf_file,"rb")
    else:
      fh = file(self.adf_file, "rb")
    data = fh.read(self.num_bytes)
    fh.close()
    # check size
    if len(data) != self.num_bytes:
      raise IOError("Invalid ADF Size: got %d but expected %d" % (len(self.data), self.num_bytes))
    # create modifyable data
    if self.read_only:
      self.data = data
    else:
      self.data = ctypes.create_string_buffer(data)
      
  def flush(self):
    # write dirty adf
    if self.dirty and not self.read_only:
      if self.gzipped:
        fh = gzip.open(self.adf_file,"wb")
      else:
        fh = file(self.adf_file, "wb")
      fh.write(self.data[:self.num_bytes])
      fh.close()
      self.dirty = False
        
  def close(self):
    self.flush()
    self.data = None

  def read_block(self, blk_num):
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid ADF block num: got %d but max is %d" % (blk_num, self.num_blocks))
    off = self._blk_to_offset(blk_num)
    return self.data[off:off+self.block_bytes]
  
  def write_block(self, blk_num, data):
    if self.read_only:
      raise IOError("ADF File is read-only!")
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid ADF block num: got %d but max is %d" % (blk_num, self.num_blocks))
    if len(data) != self.block_bytes:
      raise ValueError("Invalid ADF block size written: got %d but size is %d" % (len(data), self.block_bytes))
    off = self._blk_to_offset(blk_num)
    self.data[off:off+self.block_bytes] = data
    self.dirty = True
