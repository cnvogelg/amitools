"""tools to convert byte sizes into strings suitable for disk/file sizes"""

KIB_SIZE = 1024
MIB_SIZE = KIB_SIZE * 1024
GIB_SIZE = MIB_SIZE * 1024

def to_bi_str(size):
  if size < 1000:
    return "%3dBi" % size
  else:
    for unit in "KMGT":
      next = size / KIB_SIZE
      if next < 10:
        rem = size % KIB_SIZE
        return "%d.%d%si" % (next, rem * 10 / KIB_SIZE, unit)
      elif next < 1000:
        return "%3d%si" % (next, unit)
      size = next
    return "NaNBi"
