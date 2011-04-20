"""A class for reading and writing ELF format binaries (esp. Amiga m68k ones)"""

import struct
import os

ELFCLASS32 = 1
ELFDATA2MSB = 2
ELFOSABI_SYSV = 0

EM_68K = 4

ET_values = {
  0: "NONE",
  1: "REL",
  2: "EXEC",
  3: "DYN",
  4: "CORE"
}

SHN_UNDEF = 0
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_RELA = 4
SHT_NOBITS = 8

SHT_values = {
  0: "NULL",
  1: "PROGBITS",
  2: "SYMTAB",
  3: "STRTAB",
  4: "RELA",
  5: "HASH",
  6: "DYNAMIC",
  7: "NOTE",
  8: "NOBITS",
  9: "REL",
  10: "SHLIB",
  11: "DYNSYM",
  14: "INIT_ARRAY",
  15: "FINI_ARRAY",
  16: "PREINIT_ARRAY",
  17: "GROUP",
  18: "SYMTAB_SHNDX" 
}

SHT_flags = {
  1: "WRITE",
  2: "ALLOC",
  4: "EXECINSTR",
  8: "MERGE",
 16: "STRINGS",
 32: "INFO_LINK",
 64: "LINK_ORDER",
128: "OS_NONCONFORMING",
256: "GROUP",
512: "TLS"
}

SHN_values = {
0: "UND",
0xfff1: "ABS"
}

STB_values = {
  0: "LOCAL",
  1: "GLOBAL",
  2: "WEAK",
  3: "NUM"
}

STT_values = {
  0: "NOTYPE",
  1: "OBJECT",
  2: "FUNC",
  3: "SECTION",
  4: "FILE",
  5: "COMMON",
  6: "TLS",
  7: "NUM"
}

STV_values = {
 0: "DEFAULT",
 1: "INTERNAL",
 2: "HIDDEN",
 3: "PROTECTED"
}

R_68K_values = {
0: "68K_NONE",
1: "68K_32"
}

class ELF:
  
  def __init__(self):
    self.elf = {}
  
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
    for n in xrange(num):
      entry = {}
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
      if entry['shndx_str'] == None:
        entry['shndx_str'] = entry['shndx']
        
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
    seg['link_seg'] = seghdr[link]
    seg['info_seg'] = seghdr[info]
    
    symtab = seg['link_seg']['symtab']
    for entry in seg['rela']:
      entry['sym_ref'] = symtab[entry['sym']]
      entry['sym_str'] = entry['sym_ref']['name_str']
      # relative to segment
      if entry['sym_str'] == "":
        entry['sym_str'] = seg['info_seg']['name_str']
    
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
      for seg in seghdr:
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
      
      # resolve rela links
      for seg in seghdr:  
        if seg['type'] == SHT_RELA:
          if not self.resolve_rela_links(seg, seghdr):
            return False
        
    return True
    
  def dump_segment_headers(self):
    print "    name             type       flags"
    seghdr = self.elf['seghdr']
    num = 0
    for seg in seghdr:
      print "%2d  %-16s %-10s %s" % (num,seg['name_str'],seg['type_str'],",".join(seg['flags_dec']))
      num += 1
      
  def dump_symbols(self):
    if not self.elf.has_key('symtab'):
      print "no symbols"
      return
    
    print "      value     size    type        bind        visibility  ndx  name"
    symtab = self.elf['symtab']
    num = 0
    for sym in symtab:
      print "%4d  %08x  %6d  %-10s  %-10s  %-10s  %-3s  %s" % \
            (num,sym['value'],sym['size'],sym['type_str'], \
             sym['bind_str'],sym['visibility_str'],
             sym['shndx_str'],sym['name_str']) 
      num += 1
  
  def dump_relas(self):
    for seg in self.elf['seghdr']:
      if seg['type'] == SHT_RELA:
        print seg['name_str']
        print "      offset    type        symbol + addend"
        num = 0
        for rel in seg['rela']:
          print "%4d  %08x  %-10s  %s (%d) + %d" % (num,rel['offset'],rel['type_str'],\
                rel['sym_str'],rel['sym'],rel['addend'])
          num += 1