import os
import os.path
import struct
from ADFBlockDevice import ADFBlockDevice
from HDFBlockDevice import HDFBlockDevice
from RawBlockDevice import RawBlockDevice
from DiskGeometry import DiskGeometry
from amitools.fs.rdb.RDisk import RDisk

class BlkDevFactory:
  """the block device factory opens or creates image files suitable as a block device for file system access."""

  TYPE_ADF = 1
  TYPE_HDF = 2
  TYPE_RDISK = 3
  
  def detect_type(self, img_file, options=None):
    """try to detect the type of a given img_file name"""
    # 1. take type from options
    t = self.type_from_options(options)
    if t == None:
      # 2. look in file
      t = self.type_from_contents(img_file)
      if t == None:
        # 3. from extension
        t = self.type_from_extension(img_file)
    return t

  def type_from_options(self, options):
    """look in options for type"""
    if options != None:
      if options.has_key('type'):
        t = options['type'].lower()
        if t == 'adf':
          return self.TYPE_ADF
        elif t == 'hdf':
          return self.TYPE_HDF
        elif t == 'rdisk':
          return self.TYPE_RDISK
    return None
    
  def type_from_contents(self, img_file):
    """look in first 4 bytes for type of image"""
    # make sure file exists
    if not os.path.exists(img_file):
      return None
    # load 4 bytes
    f = open(img_file, "rb")
    hdr = f.read(4)
    f.close()
    # check for 'RDISK':
    if hdr == 'RDSK':
      return self.TYPE_RDISK
    return None
      
  def type_from_extension(self, img_file):
    """look at file extension for type of image"""
    ext = img_file.lower()
    if ext.endswith('.adf'):
      return self.TYPE_ADF
    elif ext.endswith(".hdf"):
      return self.TYPE_HDF
    elif ext.endswith(".rdsk"):
      return self.TYPE_RDISK
    else:
      return None
    
  def open(self, img_file, read_only=False, options=None):
    """open an existing image file"""
    # make sure image file exists
    if not os.path.exists(img_file):
      raise IOError("image file not found")
    # is readable?
    if not os.access(img_file, os.R_OK):
      raise IOError("can't read from image file")
    # is writeable? -> no: enforce read_only
    if not os.access(img_file, os.W_OK):
      read_only = True
    # check size
    size = os.path.getsize(img_file)
    if size == 0:
      raise IOErrro("image file is empty")
    # detect type
    t = self.detect_type(img_file, options)
    if t == None:
      raise IOError("can't detect type of image file")
    # create blkdev
    if t == self.TYPE_ADF:
      blkdev = ADFBlockDevice(img_file, read_only)
      blkdev.open()
    elif t == self.TYPE_HDF:
      # detect geometry
      geo = DiskGeometry()
      if not geo.detect(size, options):
        raise IOError("can't detect geometry of HDF image file")
      blkdev = HDFBlockDevice(img_file, read_only)
      blkdev.open(geo)
    else:
      rawdev = RawBlockDevice(img_file, read_only)
      rawdev.open()
      # create rdisk instance
      rdisk = RDisk(rawdev)
      if not rdisk.open():
        raise IOError("can't open rdisk of image file")
      # determine partition
      p = "0"
      if options != None and options.has_key('part'):
        p = options['part']
      part = rdisk.find_partition_by_string(p)
      if part == None:
        raise IOError("can't find partition in image file")
      blkdev = part.create_blkdev(True) # auto_close rdisk
      blkdev.open()
    return blkdev

  def create(self, img_file, force=True, options=None):
    # make sure we are allowed to overwrite existing file
    if os.path.exists(img_file):
      if not force:
        raise IOError("can't overwrite existing image file")
      # not writeable?
      if not os.access(img_file, os.W_OK):
        raise IOError("can't write image file")
    # detect type
    t = self.detect_type(img_file, options)
    if t == None:
      raise IOError("can't detect type of image file")
    if t == self.TYPE_RDISK:
      raise IOError("can't create rdisk. use rdbtool first")
    # create blkdev
    if t == self.TYPE_ADF:
      blkdev = ADFBlockDevice(img_file)
      blkdev.create()
    else:
      # determine geometry from size or chs
      geo = DiskGeometry()
      if not geo.setup(options):
        raise IOError("can't determine geometry of HDF image file")
      blkdev = HDFBlockDevice(img_file)
      blkdev.create(geo)
    return blkdev