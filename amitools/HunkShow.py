from amitools import Hunk
import subprocess
import tempfile
import os

class HunkShow:
  
  def __init__(self, hunk_file, show_relocs=False, show_debug=False, disassemble=False, hexdump=False):
    self.hunk_file = hunk_file
    
    # clone file refs
    self.header = hunk_file.header
    self.segments = hunk_file.segments
    self.overlay = hunk_file.overlay
    self.overlay_headers = hunk_file.overlay_headers
    self.overlay_segments = hunk_file.overlay_segments
    self.lib_indexes = hunk_file.lib_indexes
    self.lib_segments = hunk_file.lib_segments
    self.units = hunk_file.units
    
    self.show_relocs=show_relocs
    self.show_debug=show_debug
    self.disassemble=disassemble
    self.hexdump=hexdump
  
  def show_segments(self):
    hunk_type = self.hunk_file.type
    if hunk_type == Hunk.TYPE_LOADSEG:
      self.show_loadseg_segments()
    elif hunk_type == Hunk.TYPE_UNIT:
      self.show_unit_segments()
    elif hunk_type == Hunk.TYPE_LIB:
      self.show_lib_segments()
    print
      
  def show_lib_segments(self):
    num_lib = len(self.lib_indexes)
    for l in xrange(num_lib):
      print "Library #%d" % l
      # Main Hunks of Lib
      for segment in self.lib_segments[l]:
        self.show_segment(segment)
      
      # Index
      print  
      print "Index"
      index = self.lib_indexes[l]
      units = index['units']
      for unit in units:
        print "  Unit '%s' starting at Hunk #%d" % (unit['name'], unit['hunk_begin_no'])
        for hunk in unit['hunks']:
          print "    %s '%s' %08x" % (hunk['type_name'], hunk['name'], hunk['size']*4)
          if hunk.has_key('refs'):
            print "      References:"
            for ref in hunk['refs']:
              print "                 %s (%d bits)" % (ref['name'],ref['bits'])
          if hunk.has_key('defs'):
            print "      Definitions:"
            for d in hunk['defs']:
              print "      @%08x  %s (type %d)" % (d['value'],d['name'],d['type'])
          print
      
  def show_unit_segments(self):
    u = 0
    for unit in self.units:
      print
      print "Unit #%d" %  u
      u += 1
      for hunk in unit:
        self.show_segment(hunk)
  
  def show_loadseg_segments(self):
    # header + segments
    self.show_header(self.header)
    for segment in self.segments:
      self.show_segment(segment)
    
    # overlay
    if self.overlay != None:
      print
      print "Overlay"
      num_ov = len(self.overlay_headers)
      for o in xrange(num_ov):
        print
        self.show_header(self.overlay_headers[o])
        for segment in self.overlay_segments[o]:
          self.show_segment(segment)
    
  def show_header(self, hdr):
    print "Header (first=%d, last=%d, table size=%d)" % (hdr['first_hunk'], hdr['last_hunk'], hdr['table_size'])
    
  def show_segment(self, hunk):
    main = hunk[0]
    # unit hunks are named
    title = ""
    if hunk[0].has_key('name'):
      title = "'%s'" % main['name']
    type_name = main['type_name'].replace("HUNK_","")
    print
    print "Segment #%d %s %s" % (main['hunk_no'], type_name, title)
    size = main['size']
    print "       %08x / %d bytes" % (size,size)

    if self.hexdump:
      self.show_hex(main['data'])

    for extra in hunk[1:]:
      self.show_extra_hunk(extra)

    if main['type'] == Hunk.HUNK_CODE and self.disassemble:
      self.show_disassembly(hunk)

  def show_extra_hunk(self, hunk):
    hunk_type = hunk['type']
    if hunk_type in Hunk.reloc_hunks:
      self.show_reloc_hunk(hunk)
    elif hunk_type == Hunk.HUNK_DEBUG:
      self.show_debug_hunk(hunk)
    elif hunk_type == Hunk.HUNK_SYMBOL:
      self.show_symbol_hunk(hunk)
    elif hunk_type == Hunk.HUNK_EXT:
      self.show_ext_hunk(hunk)
    else:
      print "  ",hunk['type_name'],"(unknown)"
      print hunk

  def show_reloc_hunk(self, hunk):
    reloc = hunk['reloc']
    type_name = hunk['type_name'].replace("HUNK_","")
    print "  relocations (%s)" % type_name
    for hunk_num in reloc:
      offsets = reloc[hunk_num]
      if self.show_relocs:
        print "    To Hunk #%d: " % (hunk_num)
        for offset in offsets:
          print "      @%08x" % (offset)
      else:
        print "    To Hunk #%d: %4d entries" % (hunk_num, len(offsets))

  def show_debug_hunk(self, hunk):
    debug_type = hunk['debug_type']
    if debug_type == 'LINE':
      print "  debug info: line for '%s' (offset=@%08x)" % (hunk['src_file'],hunk['debug_offset'])
      if self.show_debug:
        for src_off in hunk['src_map']:
          print "      @%08x  line %d" % (src_off[1],src_off[0])
    else:
      print "  debug info: %s (offset=@%08x,size=%08x)" % (debug_type, hunk['debug_offset'], len(hunk['data']))
      if self.show_debug:
        self.show_hex(hunk['data'])
    
  def show_symbol_hunk(self, hunk):
    print "  symbols:"
    for symbol in hunk['symbols']:
      print "      @%08x  %s" % (symbol[1],symbol[0])
      
  def show_ext_hunk(self, hunk):
    print "  externals:"
    exts = hunk['exts']
    for ext in exts:
      # definition
      if ext.has_key('def'):
        print "      @%08x  %16s  %s" % (ext['def'],ext['type_name'],ext['name'])
      # references
      elif ext.has_key('refs'):
        refs = ext['refs']
        num = len(refs)
        print "      @%08x  %16s  %s" % (refs[0],ext['type_name'],ext['name'])
        if num > 1:
          for ref in refs[1:]:
            print "      @%08x" % ref
      # common_base
      elif ext.has_key('common_size'):
        print "      @%08x  %16s  %s" % (ext['common_size'],ext['type_name'],ext['name'])
      else:
        print "      unknown ext"
        
  def show_hex_line(self, addr, line):
    l = len(line)
    skip = 16 - l
    out = "       %08x: " % addr
    for d in line:
      out += "%02x " % ord(d)
    for d in xrange(skip):
      out += "   "
    out += " "
    for d in line:
      v = ord(d)
      if v >= 32 and v < 256:
        out += "%c" % d
      else:
        out += "."
    print out

  def show_hex(self, data):
    l = len(data)
    o = 0
    while o < l:
      if l < 16:
        line_size = l
      else:
        line_size = 16
      line = data[o:o+line_size]
      self.show_hex_line(o, line)
      o += line_size

  # ----- disassembler -----
 
  def gen_disassembly(self, data):
    # write to temp file
    tmpname = tempfile.mktemp()
    out = file(tmpname,"wb")
    out.write(data)
    out.close()
    # call external disassembler
    p = subprocess.Popen(["vda68k",tmpname], stdout=subprocess.PIPE)
    output = p.communicate()[0]
    os.remove(tmpname)
    lines = output.splitlines()
    # parse output: split addr and code
    result = []
    for l in lines:
      addr = int(l[0:8],16)
      code = l[10:]
      result.append((addr,code))
    return result

  def get_symtab(self, hunk):
    for h in hunk[1:]:
      if h['type'] == Hunk.HUNK_SYMBOL:
        return h['symbols']
    return None

  def find_src_line(self, hunk, addr):
    for h in hunk[1:]:
      if h['type'] == Hunk.HUNK_DEBUG and h['debug_type'] == 'LINE':
        src_map = h['src_map']
        for e in src_map:
          src_line = e[0]
          src_addr = e[1] + h['debug_offset']
          if src_addr == addr:
            return h['src_file'] + ":" + str(src_line)
    return None
    
  def show_disassembly(self, hunk):
    print "  disassembly"
    main = hunk[0]
    lines = self.gen_disassembly(main['data'])
    # get a symbol table for this hunk
    symtab = self.get_symtab(hunk)    
    # show line by line
    for l in lines:
      addr = l[0]
      code = l[1]
      
      # try to find a symbol for this addr
      if symtab != None:
        for s in symtab:
          if s[1] == addr:
            print "%s%s:" % (' ' * 30,s[0])
      
      # find source line info
      line = self.find_src_line(hunk,addr)
      if line == None:
        line = ""
      else:
        line = "; "+line
      
      print "       %08x  %-60s %s" % (addr,code,line)




      