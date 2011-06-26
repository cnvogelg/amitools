from amitools import Hunk
from amitools import HunkDisassembler

class HunkShow:
  
  def __init__(self, hunk_file, show_relocs=False, show_debug=False, \
                     disassemble=False, hexdump=False, brief=False):
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
    self.brief=brief
  
  def show_segments(self):
    hunk_type = self.hunk_file.type
    if hunk_type == Hunk.TYPE_LOADSEG:
      self.show_loadseg_segments()
    elif hunk_type == Hunk.TYPE_UNIT:
      self.show_unit_segments()
    elif hunk_type == Hunk.TYPE_LIB:
      self.show_lib_segments()
      
  def show_lib_segments(self):
    num_lib = len(self.lib_indexes)
    for l in xrange(num_lib):
      print "Library #%d" % l

      # print lib contents only if not in brief mode
      if not self.brief:
        # segments of Lib
        for segment in self.lib_segments[l]:
          self.show_segment(segment, self.lib_segments[l])
      
        # Index
        print "Index #%d" % l
      
      index = self.lib_indexes[l]
      units = index['units']
      for unit in units:
        unit_name = unit['name']
        hunk_no_begin = unit['hunk_begin_no']        
        self.print_unit(unit['unit_no'], unit_name)
        
        for hunk in unit['hunks']:

          type_name = hunk['type_name'].replace("HUNK_","")
          name = hunk['name']
          byte_size = hunk['size'] * 4
          self.print_segment_header(hunk['hunk_no'], type_name, byte_size, name)

          if hunk.has_key('refs'):
            self.print_extra("refs","#%d" % len(hunk['refs']))
            if not self.brief:
              for ref in hunk['refs']:
                self.print_symbol(-1,ref['name'],"(%d bits)" % ref['bits'])
          
          if hunk.has_key('defs'):
            self.print_extra("defs","#%d" % len(hunk['defs']))
            if not self.brief:
              for d in hunk['defs']:
                self.print_symbol(d['value'],d['name'],"(type %d)" % d['type'])
      
  def show_unit_segments(self):
    for unit in self.units:
      unit_hunk = unit[0]
      self.print_unit(unit_hunk['unit_no'], unit_hunk['name'])
      for hunk in unit[1:]:
        self.show_segment(hunk, unit[1:])
  
  def show_loadseg_segments(self):
    # header + segments
    if not self.brief:
      self.print_header(self.header)
    for segment in self.segments:
      self.show_segment(segment, self.segments)
    
    # overlay
    if self.overlay != None:
      print "Overlay"
      num_ov = len(self.overlay_headers)
      for o in xrange(num_ov):
        if not self.brief:
          self.print_header(self.overlay_headers[o])
        for segment in self.overlay_segments[o]:
          self.show_segment(segment, self.overlay_segments[o])
    
  def show_segment(self, hunk, seg_list):
    main = hunk[0]

    # unit hunks are named
    name = ""
    if hunk[0].has_key('name'):
      name = "'%s'" % main['name']

    type_name = main['type_name'].replace("HUNK_","")
    size = main['size']
    hunk_no = main['hunk_no']
    
    self.print_segment_header(hunk_no, type_name, size, name)
    if self.hexdump:
      self.show_hex(main['data'])

    for extra in hunk[1:]:
      self.show_extra_hunk(extra)

    if main['type'] == Hunk.HUNK_CODE and self.disassemble:
      disas = HunkDisassembler.HunkDisassembler()
      print "\tdisassembly"
      disas.show_disassembly(hunk, seg_list)
      print

  def show_extra_hunk(self, hunk):
    hunk_type = hunk['type']
    if hunk_type in Hunk.reloc_hunks:
      type_name = hunk['type_name'].replace("HUNK_","").lower()
      self.print_extra("reloc","%s #%d" % (type_name, len(hunk['reloc'])))
      if not self.brief:
        self.show_reloc_hunk(hunk)
        
    elif hunk_type == Hunk.HUNK_DEBUG:
      self.print_extra("debug","%s" % (hunk['debug_type']))
      if not self.brief:
        self.show_debug_hunk(hunk)
    
    elif hunk_type == Hunk.HUNK_SYMBOL:
      self.print_extra("symbol","#%d" % (len(hunk['symbols'])))
      if not self.brief:
        self.show_symbol_hunk(hunk)
    
    elif hunk_type == Hunk.HUNK_EXT:
      self.print_extra("ext","def #%d  ref #%d  common #%d" % (len(hunk['ext_def']),len(hunk['ext_ref']),len(hunk['ext_common'])))
      if not self.brief:
        self.show_ext_hunk(hunk)
    
    else:
      self.print_extra("extra","%s" % hunk['type_name'])

  def show_reloc_hunk(self, hunk):
    reloc = hunk['reloc']
    for hunk_num in reloc:
      offsets = reloc[hunk_num]
      if self.show_relocs:
        for offset in offsets:
          self.print_symbol(offset,"Segment #%d" % hunk_num,"")
      else:
        self.print_extra_sub("To Segment #%d: %4d entries" % (hunk_num, len(offsets)))

  def show_debug_hunk(self, hunk):
    debug_type = hunk['debug_type']
    if debug_type == 'LINE':
      self.print_extra_sub("line for '%s' (offset=@%08x)" % (hunk['src_file'],hunk['debug_offset']))
      if self.show_debug:
        for src_off in hunk['src_map']:
          addr = src_off[1]
          line = src_off[0]
          self.print_symbol(addr,"line %d" % line)
    else:
      self.print_extra_sub("%s (offset=@%08x,size=%08x)" % (debug_type, hunk['debug_offset'], len(hunk['data'])))
      if self.show_debug:
        self.show_hex(hunk['data'])
    
  def show_symbol_hunk(self, hunk):
    for symbol in hunk['symbols']:
      self.print_symbol(symbol[1],symbol[0],"")
      
  def show_ext_hunk(self, hunk):
    # definition
    for ext in hunk['ext_def']:
      tname = ext['type_name'].replace("EXT_","").lower()
      self.print_symbol(ext['def'],ext['name'],tname)
    # references
    for ext in hunk['ext_ref']:
      refs = ext['refs']
      tname = ext['type_name'].replace("EXT_","").lower()
      for ref in refs:
        self.print_symbol(ref,ext['name'],tname)

    # common_base
    for ext in hunk['ext_common']:
      tname = ext['type_name'].replace("EXT_","").lower()
      self.print_symbol(ext['common_size'],ext['name'],tname)

  # ----- printing -----

  def print_header(self, hdr):
    print "\t      header (segments: first=%d, last=%d, table size=%d)" % (hdr['first_hunk'], hdr['last_hunk'], hdr['table_size'])

  def print_extra(self, type_name, info):
    print "\t\t%8s  %s" % (type_name, info)
    
  def print_extra_sub(self, text):
    print "\t\t\t%s" % text

  def print_segment_header(self, hunk_no, type_name, size, name):
    print "\t#%03d  %-5s %08x  %s" % (hunk_no, type_name, size, name)

  def print_symbol(self,addr,name,extra):
    if addr == -1:
      a = "xxxxxxxx"
    else:
      a = "%08x" % addr
    print "\t\t\t%s  %-32s  %s" % (a,name,extra)

  def print_unit(self, no, name):
    print "  #%03d  UNIT  %s" % (no, name)

  # ----- hex dump -----
        
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



      