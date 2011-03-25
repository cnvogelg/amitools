"""A class for reading and writing ELF format binaries (esp. Amiga m68k ones)"""

import struct
import os

ELFCLASS32 = 1
ELFDATA2MSB = 2
ELFOSABI_SYSV = 0

EM_68K = 4

ET_names = {
  0: "NONE",
  1: "REL",
  2: "EXEC",
  3: "DYN",
  4: "CORE"
}

SHN_UNDEF = 0
SHT_NOBITS = 8
SHT_STRTAB = 3

SHT_names = {
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
    
  def parse_header(self,data):
    hdr = self.elf['hdr']
    names = ['type','machine','version','entry','phoff','shoff','flags','ehsize','phentsize','phnum','shentsize','shnum','shstrndx']
    fmt = "HHIIIIIHHHHHH"
    if not self.parse_data(fmt,data,hdr,names):
      return False
    if not hdr['type'] in ET_names:
      self.error_string = "Unknown ELF type: "+hdr['type']
      return False
    hdr['type_name'] = ET_names[hdr['type']]
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
           
  def parse_seghdr_entry(self, data, seghdr):
    fmt = "IIIIIIIIII"
    names = ['name','type','flags','addr','offset','size','link','info','addralign','entsize']
    seg = {}
    if not self.parse_data(fmt, data, seg, names):
      self.error_string = "Error parsing segment header entry"
      return False
    seghdr.append(seg)
    return True

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
      if not self.parse_seghdr_entry(sh_data,seghdr):
        return False
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
      
    return True
    
  def dump_segment_headers(self):
    print "    name             type       flags"
    seghdr = self.elf['seghdr']
    num = 0
    for seg in seghdr:
      print "%2d  %-16s %-10s" % (num,seg['name_str'],SHT_names[seg['type']])
      num += 1
      
    
    