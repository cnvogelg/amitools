# amitools utility functions

def print_hex_line(addr, line, indent=0):
  l = len(line)
  skip = 16 - l
  out = " " * indent
  out += "%08x: " % addr
  for d in line:
    out += "%02x " % ord(d)
  for d in xrange(skip):
    out += "   "
  out += " "
  for d in line:
    v = ord(d)
    if v >= 32 and v < 128:
      out += "%c" % d
    else:
      out += "."
  print out

def print_hex(data, indent=0):
  l = len(data)
  o = 0
  while o < l:
    if l < 16:
      line_size = l
    else:
      line_size = 16
    line = data[o:o+line_size]
    print_hex_line(o, line, indent)
    o += line_size
