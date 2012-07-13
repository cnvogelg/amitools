"""A class for reading and writing ELF format binaries (esp. Amiga m68k ones)"""

import struct
import os
from ELF import *

class ELFReader:
  
  def __init__(self):
    self.elf = {}
    self.text = None
    self.rodata = None
    self.data = None
    self.bss = None
    self.segments = []
  
  def parse_ident(self, ident_data):
    # magic
    magic = ident_data[0:4]
    if magic != "\177ELF":
      self.error_string = "No ELF magic found!"
      return False
    
    self.elf['hdr'] = {}
    ident = {}
    self.elf['hdr']['ident'] = ident
    ident['class'] = ord(ident_data[4])
    ident['data'] = ord(ident_data[5])
    ident['version'] = ord(ident_data[6])
    ident['osabi'] = ord(ident_data[7])
    ident['abiversion'] = ord(ident_data[8])
    return True
    
  def parse_data(self, fmt, data, tgt, names):
    flen = len(fmt)
    nlen = len(names)
    if flen != nlen:
      self.error_string = "parse_data call error!!"
      return False
    decoded = struct.unpack(">"+fmt, data)
    if len(decoded) != nlen:
      self.error_string = "parse_data decode error!!"
    for i in xrange(nlen):
      tgt[names[i]] = decoded[i]
    return True
  
  def decode_flags(self, value, names):
    result = []
    for mask in names:
      if mask & value == mask:
        result.append(names[mask])
    return result

  def decode_value(self, value, names):
    if names.has_key(value):
      return names[value]
    else:
      return None
    
  def parse_header(self,data):
    hdr = self.elf['hdr']
    names = ['type','machine','version','entry','phoff','shoff','flags','ehsize','phentsize','phnum','shentsize','shnum','shstrndx']
    fmt = "HHIIIIIHHHHHH"
    if not self.parse_data(fmt,data,hdr,names):
      return False
    hdr['type_str'] = self.decode_value(hdr['type'],ET_values)
    return True
  
  def check_m68k(self):
    hdr = self.elf['hdr']
    ident = hdr['ident']
    return ident['class'] == ELFCLASS32 and \
           ident['data'] == ELFDATA2MSB and \
           ident['version'] == 1 and \
           ident['osabi'] == ELFOSABI_SYSV and \
           ident['abiversion'] == 0 and \
           hdr['machine'] == EM_68K
  
  def parse_seghdr_entry(self, data):
    fmt = "IIIIIIIIII"
    names = ['name','type','flags','addr','offset','size','link','info','addralign','entsize']
    seg = {}
    if not self.parse_data(fmt, data, seg, names):
      self.error_string = "Error parsing segment header entry"
      return None
      
    # decode flags
    seg['flags_dec'] = self.decode_flags(seg['flags'], SHT_flags)
    # decode type
    seg['type_str'] = self.decode_value(seg['type'], SHT_values)
    return seg

  def load_segment_header(self, f):
    hdr = self.elf['hdr']
    shoff = hdr['shoff']
    shentsize = hdr['shentsize']
    f.seek(shoff, os.SEEK_SET)
    seghdr = []
    self.elf['seghdr'] = seghdr
    shnum = hdr['shnum']
    for i in xrange(shnum):
      sh_data = f.read(shentsize)
      seg = self.parse_seghdr_entry(sh_data)
      if not seg:
        return False
      seghdr.append(seg)
    return True
  
  def decode_strtab(self, seg, data):
    l = len(data)
    o = 0
    strtab = []
    while o < l:
      n = data.find('\0',o)
      if n == -1:
        self.error_string = "Invalid strtab!"
        return False
      if n > 0:
        s = data[o:n]
      else:
        s = ""
      strtab.append((o,s))
      o = n+1
    
    seg['strtab'] = strtab
    return True
  
  def decode_string(self, strtab, off):
    old = (0,"")
    for e in strtab:
      if off < e[0]:
        delta = off - old[0]
        return old[1][delta:]
      old = e
    delta = off - strtab[-1][0]
    return strtab[-1][1][delta:]
  
  def decode_symtab(self, seg, data):
    entsize = seg['entsize']
    num = seg['size'] / entsize
    symtab = []
    seg['symtab'] = symtab
    fmt = "IIIBBH"
    names = ['name','value','size','info','other','shndx']
    off = 0
    idx = 0
    for n in xrange(num):
      entry = {}
      entry['idx'] = idx
      idx += 1
      entry_data = data[off:off+entsize]
      if not self.parse_data(fmt, entry_data, entry, names):
         self.error_string = "Error parsing symtab entry"
         return False
         
      # decode bind and type from info
      info = entry['info']
      entry['bind'] = info >> 4
      entry['type'] = info & 0xf
      other = entry['other']
      entry['visibility'] = other & 0x3
      
      entry['bind_str'] = self.decode_value(entry['bind'], STB_values)
      entry['type_str'] = self.decode_value(entry['type'], STT_values)
      entry['visibility_str'] = self.decode_value(entry['visibility'], STV_values)
      entry['shndx_str'] = self.decode_value(entry['shndx'], SHN_values)
        
      symtab.append(entry)
      off += entsize
    return True
  
  def resolve_symtab_names(self, seg, seghdr):
    strtab_seg_num = seg['link']
    if strtab_seg_num < 1 or strtab_seg_num >= len(seghdr):
      self.error_string = "Invalid strtab for symtab: "+strtab_seg_num
      return False
    strtab_seg = seghdr[strtab_seg_num]
    if not strtab_seg.has_key('strtab'):
      self.error_string = "Invalid strtab segment for symtab"
      return False
    strtab = strtab_seg['strtab']
    
    for sym in seg['symtab']:
      sym['name_str'] = self.decode_string(strtab, sym['name'])
    
    return True
  
  def resolve_symtab_indices(self, seg):
    seghdr = self.elf['seghdr']
    for sym in seg['symtab']:
      if sym['shndx_str'] == None:
        idx = sym['shndx']
        sym['shndx_hdr'] = seghdr[idx]
        sym['shndx_str'] = seghdr[idx]['name_str']
      else:
        sym['shndx_hdr'] = None
    return True
  
  def assign_symbols_to_segments(self, seg):
    seghdr = self.elf['seghdr']
    src_file_sym = None
    all_symbols = []
    for sym in seg['symtab']:
      sym_type = sym['type_str']
      if sym_type == 'FILE':
        # store file symbol for following symbols
        src_file_sym = sym
      elif sym_type in ('OBJECT','FUNC','NOTYPE'):
        # add containing file symbol and its name
        if src_file_sym != None:
          sym['file_sym'] = src_file_sym
          sym['file_str'] = src_file_sym['name_str']
        
        # get segment
        if sym['shndx_str'] != 'ABS':
          idx = sym['shndx']
          seg = seghdr[idx]
          # create symbols arry
          if seg.has_key('symbols'):
            symbols = seg['symbols']
          else:
            symbols = []
            seg['symbols'] = symbols
            all_symbols.append(symbols)
          symbols.append(sym)
          
    # now sort all symbol lists
    for symbols in all_symbols:
      symbols.sort(key=lambda x : x['value'])
    return True
      
  def decode_rela(self, seg, data):
    entsize = seg['entsize']
    num = seg['size'] / entsize
    rela = []
    seg['rela'] = rela
    fmt = "IIi"
    names = ['offset','info','addend']
    off = 0
    for n in xrange(num):
      entry = {}
      entry_data = data[off:off+entsize]
      if not self.parse_data(fmt, entry_data, entry, names):
         self.error_string = "Error parsing rela entry"
         return False
         
      # decode sym and type
      info = entry['info']
      entry['sym'] = info >> 8
      entry['type'] = info & 0xff
      
      entry['type_str'] = self.decode_value(entry['type'], R_68K_values)
         
      rela.append(entry)
      off += entsize
    return True
  
  def resolve_rela_links(self, seg, seghdr):
    link = seg['link']
    info = seg['info']
    num_segs = len(seghdr)
    if link == 0 or link >= num_segs:
      self.error_string = "Invalid rela link!"
      return False
    if info == 0 or info >= num_segs:  
      self.error_string = "Invalid rela info!"
      return False

    # link_seg -> symbol table
    seg['link_seg'] = seghdr[link]

    # info_seg -> src segment we will apply rela on
    src_seg = seghdr[info]
    seg['info_seg'] = src_seg
    
    # store link in segment for this relocation and sort them
    src_seg['rela_seg'] = seg
    rela = sorted(seg['rela'], key=lambda x : x['offset'])
    src_seg['rela'] = rela
    
    # a map for rela by tgt segment
    by_seg = {}
    src_seg['rela_by_seg'] = by_seg
    
    # now process all rela entries
    symtab = seg['link_seg']['symtab']
    for entry in seg['rela']:
      sym_idx = entry['sym']
      sym = symtab[sym_idx]
      entry['sym_ref'] = sym
      entry['sym_str'] = sym['name_str']
      # relative to segment
      if entry['sym_str'] == "":
        entry['sym_str'] = sym['shndx_str']
      # copy segment info from symbol
      entry['shndx_hdr'] = sym['shndx_hdr']
      entry['shndx_str'] = sym['shndx_str']
      entry['shndx'] = sym['shndx']
      # calc addend in segment
      entry['shndx_addend'] = entry['addend'] + sym['value']
      
      # look up segment target
      tgt_idx = entry['shndx']
      tgt_seg = entry['shndx_hdr']
      if by_seg.has_key(tgt_idx):
        by_seg_list = by_seg[tgt_idx]
      else:
        by_seg_list = []
        by_seg[tgt_idx] = by_seg_list
      by_seg_list.append(entry)

    # sort all by_seg entries
    for tgt_idx in by_seg:
      by_seg_list = by_seg[tgt_idx]
      by_seg_list.sort(key=lambda x : x['offset'])

    return True
  
  def load_segment(self, f, seg):
    t = seg['type']
    size = seg['size']
    if t == SHT_NOBITS or size == 0:
      seg['data'] = None
    else:
      offset = seg['offset']
      f.seek(offset, os.SEEK_SET)
      data = f.read(size)
      
      # decode?
      if t == SHT_STRTAB:
        if not self.decode_strtab(seg, data):
          return False
      elif t == SHT_SYMTAB:
        if not self.decode_symtab(seg, data):
          return False
      elif t == SHT_RELA:
        if not self.decode_rela(seg, data):
          return False
      else:
        # store raw data
        seg['data'] = data
        
    return True

  def name_segment(self, seg, strtab):
    off = seg['name']
    seg['name_str'] = self.decode_string(strtab, off)
    return True

  def load(self, file_name):
    self.error_string = None
    self.elf = {}

    with file(file_name, "r") as f:
    
      # read ident and header
      ident_data = f.read(16)
      if not self.parse_ident(ident_data):
        return False
      hdr_data = f.read(36)
      if not self.parse_header(hdr_data):
        return False
      if not self.check_m68k():
        self.error_string = "No m68k_elf file!"
        return False
    
      # read section header
      hdr = self.elf['hdr']
      if hdr['shnum'] == 0:
        self.error_string = "No segment header defined!"
        return False
        
      # load segment header
      if not self.load_segment_header(f):
        return False
      
      # read segments
      seghdr = self.elf['seghdr']
      idx = 0
      for seg in seghdr:
        seg['idx'] = idx
        idx += 1
        if not self.load_segment(f,seg):
          return False
      
      # name segments in header
      name_seg = seghdr[hdr['shstrndx']]
      if not name_seg.has_key('strtab'):
        self.error_string = "No strtab for segment header found!"
        return False
      for seg in seghdr:
        if not self.name_segment(seg, name_seg['strtab']):
          return False
        # resolve symtab names
        if seg['type'] == SHT_SYMTAB:
          self.elf['symtab'] = seg['symtab']
          if not self.resolve_symtab_names(seg, seghdr):
            return False
          if not self.resolve_symtab_indices(seg):
            return False
          if not self.assign_symbols_to_segments(seg):
            return False
      
      # resolve rela links and symbols
      for seg in seghdr:  
        if seg['type'] == SHT_RELA:
          if not self.resolve_rela_links(seg, seghdr):
            return False
      
      # now extract useable segments
      self.extract()
      
    return True
  
  def extract(self):
    seghdr = self.elf['seghdr']
    for seg in seghdr:
      name = seg['name_str']
      if name == '.text':
        self.text = seg
        self.segments.append(seg)
      elif name == '.rodata':
        self.rodata = seg
        self.segments.append(seg)
      elif name == '.data':
        self.data = seg
        self.segments.append(seg)
      elif name == '.bss':
        self.bss = seg
        self.segments.append(seg)
        
  def get_segment_rela(self, seg):
    if seg.has_key('rela'):
      return seg['rela']
    else:
      return []
      
  def get_segment_rela_by_seg(self, seg):
    if seg.has_key('rela_by_seg'):
      return seg['rela_by_seg']
    else:
      return {}

  def get_segment_symbols(self, seg):
    if seg.has_key('symbols'):
      return seg['symbols']
    else:
      return []
  
  def dump_elf_segments(self, show_relocs=False, show_debug=False):
    print "ELF Segments"
    print "id  name             size      rela  syms  type       flags"
    for seg in self.segments:
      
      # determine number of relocations
      rela = self.get_segment_rela(seg)
      num_rela = len(rela)
      
      # determine number of symbols
      symbols = self.get_segment_symbols(seg)
      num_syms = len(symbols)
      
      print "%2d  %-16s %08x  %4d  %4d  %-10s %s" % (seg['idx'],seg['name_str'],seg['size'],num_rela,num_syms,seg['type_str'],",".join(seg['flags_dec']))
      
      # show relas
      if show_relocs and num_rela > 0:
        print "\t\tRelocations:"
        for rel in rela:
          seg_txt = "%s (%d) + %d" % (rel['shndx_str'],rel['shndx'],rel['shndx_addend'])
          print "\t\t\t%08x  %-10s  %s" % (rel['offset'], rel['type_str'], seg_txt)
        rela_by_seg = self.get_segment_rela_by_seg(seg)
        for tgt_idx in sorted(rela_by_seg.keys()):
          print "\t\tTo Target Segment #%d:" % tgt_idx
          for rel in rela_by_seg[tgt_idx]:
            seg_txt = "%s (%d) + %d" % (rel['shndx_str'],rel['shndx'],rel['shndx_addend'])
            print "\t\t\t%08x  %-10s  %s" % (rel['offset'], rel['type_str'], seg_txt)

      # show symbols
      if show_debug and num_syms > 0:
        print "\t\tSymbols:"
        for sym in symbols:
          print "\t\t\t%08x  %6d  %-8s  %-8s  %-16s" % (sym['value'],sym['size'],sym['type_str'],sym['bind_str'],sym['name_str'])

  def dump_elf_segment_headers(self):
    print "ELF Segment Headers"
    print "idx  name             size      type       flags"
    seghdr = self.elf['seghdr']
    for seg in seghdr:
      print "%3d  %-16s %08x  %-10s %s" % (seg['idx'],seg['name_str'],seg['size'],seg['type_str'],",".join(seg['flags_dec']))
      
  def dump_elf_symbols(self):
    print "ELF Symbol Table"
    if not self.elf.has_key('symtab'):
      print "no symbols"
      return
    
    print "idx   value     size    type      bind      visible   ndx              name"
    symtab = self.elf['symtab']
    for sym in symtab:
      print "%4d  %08x  %6d  %-8s  %-8s  %-8s  %-16s  %s" % \
            (sym['idx'],sym['value'],sym['size'],sym['type_str'], \
             sym['bind_str'],sym['visibility_str'],
             sym['shndx_str'],sym['name_str']) 
  
  def dump_elf_relas(self):
    print "ELF Relocations"
    for seg in self.elf['seghdr']:
      if seg['type'] == SHT_RELA:
        print seg['name_str'],"linked to",seg['info_seg']['name_str']
        print "      offset    type        segment + addend      symbol + addend"
        num = 0
        for rel in seg['rela']:
          sym_txt = "%s (%d) + %d" % (rel['sym_str'],rel['sym'],rel['addend'])
          seg_txt = "%s (%d) + %d" % (rel['shndx_str'],rel['shndx'],rel['shndx_addend'])
          print "%4d  %08x  %-10s  %-20s  %s" % (num,rel['offset'],rel['type_str'],seg_txt,sym_txt)
          num += 1
