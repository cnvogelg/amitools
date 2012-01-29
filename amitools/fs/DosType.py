"""Helper functions and constants useable with DosTypes"""

# raw dos types
DOS0 = 0x444f5300
DOS1 = 0x444f5301
DOS2 = 0x444f5302
DOS3 = 0x444f5303
DOS4 = 0x444f5304
DOS5 = 0x444f5305

# more convenient dos type
DOS_OFS = DOS0
DOS_FFS = DOS1
DOS_OFS_INTL = DOS2
DOS_FFS_INTL = DOS3
DOS_OFS_INTL_DIRCACHE = DOS4
DOS_FFS_INTL_DIRCACHE = DOS5

# string names for dos types
dos_type_names = [
    'DOS0:ofs',
    'DOS1:ffs',
    'DOS2:ofs+intl',
    'DOS3:ffs+intl',
    'DOS4:ofs+intl+dircache',
    'DOS5:ffs+intl+dircache',
    'N/A',
    'N/A'
]

# masks for modes  
DOS_MASK_FFS = 1
DOS_MASK_INTL = 2
DOS_MASK_DIRCACHE = 4

def num_to_tag_str(l):
  """Convert the DosType in a 32 bit value to its 4 letter tag string"""
  a = chr((l >> 24) & 0xff)
  b = chr((l >> 16) & 0xff)
  c = chr((l >> 8) & 0xff)
  last = (l & 0xff)
  if last < 32:
    last = "\\x%02x" % last
  else:
    last = chr(d)
  return a+b+c+last

def get_dos_type_str(dos_type):
  """return description of dos type as a string"""
  return self.dos_type_names[dos_type & 0x7]

def is_valid(dos_type):
  """check if its a valid dos type"""
  return (dos_type >= DOS0) and (dos_type <= DOS5)

def is_ffs(dos_type):
  """check if its a fast file system dostype"""
  return (dos_type & DOS_MASK_FFS) == DOS_MASK_FFS
  
def is_intl(dos_type):
  """check if international mode is enabled in dostype"""
  return is_dircache(dos_type) or (dos_type & DOS_MASK_INTL) == DOS_MASK_INTL
  
def is_dircache(dos_type):
  """check if dir cache mode is enabled in dostype"""
  return (dos_type & DOS_MASK_DIRCACHE) == DOS_MASK_DIRCACHE
