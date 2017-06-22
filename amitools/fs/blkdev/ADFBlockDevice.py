from __future__ import absolute_import
from __future__ import print_function

from .BlockDevice import BlockDevice
import ctypes
import gzip
import io

class ADFBlockDevice(BlockDevice):
  def __init__(self, adf_file, read_only=False, fobj=None):
    self.adf_file = adf_file
    self.read_only = read_only
    self.fobj = fobj
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
    close = True
    # open adf file via fobj
    if self.fobj is not None:
      if self.gzipped:
        fh = gzip.GzipFile(self.adf_file, "rb", fileobj=self.fobj)
      else:
        fh = self.fobj
        close = False
    # open adf file
    else:
      if self.gzipped:
        fh = gzip.open(self.adf_file,"rb")
      else:
        fh = io.open(self.adf_file, "rb")
    # read image
    data = fh.read(self.num_bytes)
    # close input file
    if close:
      fh.close()
    # check size
    if len(data) != self.num_bytes:
      raise IOError("Invalid ADF Size: got %d but expected %d" % (len(data), self.num_bytes))
    # create modifyable data
    if self.read_only:
      self.data = data
    else:
      self.data = ctypes.create_string_buffer(self.num_bytes)
      self.data[:] = data

  def flush(self):
    # write dirty adf
    if self.dirty and not self.read_only:
      close = True
      if self.fobj is not None:
        # seek fobj to beginning
        self.fobj.seek(0,0)
        if self.gzipped:
          fh = gzip.GzipFile(self.adf_file, "wb", fileobj=self.fobj)
        else:
          fh = self.fobj
          close = False
      else:
        if self.gzipped:
          fh = gzip.open(self.adf_file,"wb")
        else:
          fh = io.open(self.adf_file, "wb")
      # write image
      fh.write(self.data)
      # close file
      if close:
        fh.close()
      self.dirty = False

  def close(self):
    self.flush()
    self.data = None
    # now close fobj
    if self.fobj is not None:
      self.fobj.close()

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


# --- mini test ---
if __name__ == '__main__':
  import sys
  for a in sys.argv[1:]:
    # write to file device
    adf = ADFBlockDevice(a)
    adf.open()
    d = adf.read_block(0)
    adf.write_block(0, d)
    adf.close()
    # write via fobj
    fobj = open(a, "rb")
    adf = ADFBlockDevice(a, fobj=fobj)
    adf.open()
    d = adf.read_block(0)
    adf.write_block(0, d)
    adf.close()
