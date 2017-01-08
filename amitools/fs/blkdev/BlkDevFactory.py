from __future__ import absolute_import
from __future__ import print_function

import os
import os.path
import stat
import struct
from .ADFBlockDevice import ADFBlockDevice
from .HDFBlockDevice import HDFBlockDevice
from .RawBlockDevice import RawBlockDevice
from .DiskGeometry import DiskGeometry
from amitools.fs.rdb.RDisk import RDisk
import amitools.util.BlkDevTools as BlkDevTools

class BlkDevFactory:
  """the block device factory opens or creates image files suitable as a block device for file system access."""

  valid_extensions = ('.adf','.adz','.adf.gz','.hdf','.rdisk')

  TYPE_ADF = 1
  TYPE_HDF = 2
  TYPE_RDISK = 3

  def detect_type(self, img_file, fobj, options=None):
    """try to detect the type of a given img_file name"""
    # 1. take type from options
    t = self.type_from_options(options)
    if t == None:
      # 2. look in file
      t = self.type_from_contents(img_file, fobj)
      if t == None:
        # 3. from extension
        t = self.type_from_extension(img_file)
    return t

  def type_from_options(self, options):
    """look in options for type"""
    if options != None:
      if 'type' in options:
        t = options['type'].lower()
        if t in ('adf','adz'):
          return self.TYPE_ADF
        elif t == 'hdf':
          return self.TYPE_HDF
        elif t == 'rdisk':
          return self.TYPE_RDISK
    return None

  def type_from_contents(self, img_file, fobj):
    """look in first 4 bytes for type of image"""
    # load 4 bytes
    if fobj is None:
      # make sure file exists
      if not os.path.exists(img_file):
        return None
      f = open(img_file, "rb")
      hdr = f.read(4)
      f.close()
    else:
      hdr = fobj.read(4)
      fobj.seek(0,0)
    # check for 'RDISK':
    if hdr == 'RDSK':
      return self.TYPE_RDISK
    return None

  def type_from_extension(self, img_file):
    """look at file extension for type of image"""
    ext = img_file.lower()
    if ext.endswith('.adf') or ext.endswith('.adz') or ext.endswith('.adf.gz'):
      return self.TYPE_ADF
    elif ext.endswith(".hdf"):
      return self.TYPE_HDF
    elif ext.endswith(".rdsk"):
      return self.TYPE_RDISK
    else:
      return None

  def open(self, img_file, read_only=False, options=None, fobj=None):
    """open an existing image file"""
    # file base check
    if fobj is None:
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
      st = os.stat(img_file)
      mode = st.st_mode
      if stat.S_ISBLK(mode) or stat.S_ISCHR(mode):
        size = BlkDevTools.getblkdevsize(img_file)
      else:
        size = os.path.getsize(img_file)
      if size == 0:
        raise IOError("image file is empty")
    # fobj
    else:
      fobj.seek(0,2)
      size = fobj.tell()
      fobj.seek(0,0)
    # detect type
    t = self.detect_type(img_file, fobj, options)
    if t == None:
      raise IOError("can't detect type of image file")
    # create blkdev
    if t == self.TYPE_ADF:
      blkdev = ADFBlockDevice(img_file, read_only, fobj=fobj)
      blkdev.open()
    elif t == self.TYPE_HDF:
      # detect geometry
      geo = DiskGeometry()
      if not geo.detect(size, options):
        raise IOError("can't detect geometry of HDF image file")
      blkdev = HDFBlockDevice(img_file, read_only, fobj=fobj)
      blkdev.open(geo)
    else:
      rawdev = RawBlockDevice(img_file, read_only, fobj=fobj)
      rawdev.open()
      # create rdisk instance
      rdisk = RDisk(rawdev)
      if not rdisk.open():
        raise IOError("can't open rdisk of image file")
      # determine partition
      p = "0"
      if options != None and options.has_key('part'):
        p = str(options['part'])
      part = rdisk.find_partition_by_string(p)
      if part == None:
        raise IOError("can't find partition in image file")
      blkdev = part.create_blkdev(True) # auto_close rdisk
      blkdev.open()
    return blkdev

  def create(self, img_file, force=True, options=None, fobj=None):
    if fobj is None:
      # make sure we are allowed to overwrite existing file
      if os.path.exists(img_file):
        if not force:
          raise IOError("can't overwrite existing image file")
        # not writeable?
        if not os.access(img_file, os.W_OK):
          raise IOError("can't write image file")
    # detect type
    t = self.detect_type(img_file, fobj, options)
    if t == None:
      raise IOError("can't detect type of image file")
    if t == self.TYPE_RDISK:
      raise IOError("can't create rdisk. use rdbtool first")
    # create blkdev
    if t == self.TYPE_ADF:
      blkdev = ADFBlockDevice(img_file, fobj=fobj)
      blkdev.create()
    else:
      # determine geometry from size or chs
      geo = DiskGeometry()
      if not geo.setup(options):
        raise IOError("can't determine geometry of HDF image file")
      blkdev = HDFBlockDevice(img_file, fobj=fobj)
      blkdev.create(geo)
    return blkdev


# --- mini test ---
if __name__ == '__main__':
  import sys
  import StringIO
  bdf = BlkDevFactory()
  for a in sys.argv[1:]:
    # open by file
    blkdev = bdf.open(a)
    print(a, blkdev.__class__.__name__)
    blkdev.close()
    # open via fobj
    fobj = file(a,"rb")
    data = fobj.read()
    nobj = StringIO.StringIO(data)
    blkdev = bdf.open("bluna"+a, fobj=nobj)
    print(a, blkdev.__class__.__name__)
    blkdev.close()
