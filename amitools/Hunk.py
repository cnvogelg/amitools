"""A class for reading and writing Amiga executables in Hunk format"""

import struct
import StringIO

HUNK_MIN = 999
HUNK_MAX = 1022

HUNK_UNIT       = 999
HUNK_NAME       = 1000
HUNK_CODE       = 1001
HUNK_DATA       = 1002
HUNK_BSS        = 1003
HUNK_ABSRELOC32 = 1004
HUNK_RELRELOC16 = 1005
HUNK_RELRELOC8  = 1006
HUNK_EXT        = 1007
HUNK_SYMBOL     = 1008
HUNK_DEBUG      = 1009
HUNK_END        = 1010
HUNK_HEADER     = 1011

HUNK_OVERLAY    = 1013
HUNK_BREAK      = 1014
HUNK_DREL32     = 1015
HUNK_DREL16     = 1016
HUNK_DREL8      = 1017
HUNK_LIB        = 1018
HUNK_INDEX      = 1019
HUNK_RELOC32SHORT = 1020
HUNK_RELRELOC32 = 1021
HUNK_ABSRELOC16 = 1022

hunk_names = [
"HUNK_UNIT",
"HUNK_NAME",
"HUNK_CODE",
"HUNK_DATA",
"HUNK_BSS",
"HUNK_ABSRELOC32",
"HUNK_RELRELOC16",
"HUNK_RELRELOC8",
"HUNK_EXT",
"HUNK_SYMBOL",
"HUNK_DEBUG",
"HUNK_END",
"HUNK_HEADER",
"",
"HUNK_OVERLAY",
"HUNK_BREAK",
"HUNK_DREL32",
"HUNK_DREL16",
"HUNK_DREL8",
"HUNK_LIB",
"HUNK_INDEX",
"HUNK_RELOC32SHORT",
"HUNK_RELRELOC32",
"HUNK_ABSRELOC16"
]

EXT_SYMB        = 0
EXT_DEF         = 1
EXT_ABS         = 2
EXT_RES         = 3
EXT_ABSREF32    = 129
EXT_ABSCOMMON   = 130
EXT_RELREF16    = 131
EXT_RELREF8     = 132
EXT_DEXT32      = 133
EXT_DEXT16      = 134
EXT_DEXT8       = 135
EXT_RELREF32    = 136
EXT_RELCOMMON   = 137
EXT_ABSREF16    = 138
EXT_ABSREF8     = 139

ext_names = {
EXT_SYMB        : 'EXT_SYMB',
EXT_DEF         : 'EXT_DEF',
EXT_ABS         : 'EXT_ABS',
EXT_RES         : 'EXT_RES',
EXT_ABSREF32    : 'EXT_ABSREF32',
EXT_ABSCOMMON   : 'EXT_ABSCOMMON',
EXT_RELREF16    : 'EXT_RELREF16',
EXT_RELREF8     : 'EXT_RELREF8',
EXT_DEXT32      : 'EXT_DEXT32',
EXT_DEXT16      : 'EXT_DEXT16',
EXT_DEXT8       : 'EXT_DEXT8',
EXT_RELREF32    : 'EXT_RELREF32',
EXT_RELCOMMON   : 'EXT_RELCOMMON',
EXT_ABSREF16    : 'EXT_ABSREF16',
EXT_ABSREF8     : 'EXT_ABSREF8'
}

EXT_TYPE_SHIFT = 24
EXT_TYPE_SIZE_MASK = 0xffffff

RESULT_OK = 0
RESULT_NO_HUNK_FILE = 1
RESULT_INVALID_HUNK_FILE = 2
RESULT_UNSUPPORTED_HUNKS = 3

HUNKF_ADVISORY = 1<<29
HUNKF_CHIP     = 1<<30
HUNKF_FAST     = 1<<31
HUNKF_ALL      = (HUNKF_ADVISORY | HUNKF_CHIP | HUNKF_FAST)

HUNK_TYPE_MASK = 0xffff
HUNK_FLAGS_MASK = 0xffff0000

class HunkFile:
  """Load and save Amiga executable Hunk structures"""
  
  def __init__(self):
    self.hunks = []
    self.error_string = None
    self.v37_compat = True
  
  def read_long(self, f):
    data = f.read(4)
    if len(data) == 0:
      return -1
    elif len(data) != 4:
      return -42
    return struct.unpack(">I",data)[0]

  def read_word(self, f):
    data = f.read(2)
    if len(data) == 0:
      return -1
    elif len(data) != 2:
      return -42
    return struct.unpack(">H",data)[0]

  def read_name(self, f):
    num_longs = self.read_long(f)
    if num_longs < 0:
      return -1,None
    elif num_longs == 0:
      return 0,""
    else:
      return self.read_name_size(f, num_longs)

  def read_name_size(self, f, num_longs):
    size = num_longs * 4
    data = f.read(size)
    endpos = data.find('\0')
    if endpos == -1:
      return size,data
    elif endpos == 0:
      return 0,""
    else:
      return size,data[:endpos]
  
  def get_index_name(self, strtab, offset):
    end = strtab.find('\0',offset)
    if end == -1:
      return strtab[offset:]
    else:
      return strtab[offset:end]
  
  def is_valid_first_hunk_type(self, hunk_type):
    return hunk_type == HUNK_HEADER or hunk_type == HUNK_LIB or hunk_type == HUNK_UNIT \
          or hunk_type == HUNK_CODE # strange?
  
  def parse_header(self, f, hunk):
    names = []
    while True:
      l,s = self.read_name(f)
      if l < 0:
        self.error_string = "Error parsing HUNK_HEADER names"
        return RESULT_INVALID_HUNK_FILE
      elif l == 0:
        break
      names.append(s)
    hunk['names'] = names

    # table size and hunk range
    table_size = self.read_long(f)
    first_hunk = self.read_long(f)
    last_hunk  = self.read_long(f)
    if table_size < 0 or first_hunk < 0 or last_hunk < 0:
      self.error_string = "HUNK_HEADER invalid table_size or first_hunk or last_hunk"
      return RESULT_INVALID_HUNK_FILE
    
    hunk['table_size'] = table_size
    hunk['first_hunk'] = first_hunk
    hunk['last_hunk'] = last_hunk

    # determine number of hunks in size table
    num_hunks = last_hunk - first_hunk + 1
    hunk_table = []
    for a in xrange(num_hunks):
      hunk_info = {}
      hunk_size = self.read_long(f)
      if hunk_size < 0:
        self.error_string = "HUNK_HEADER contains invalid hunk_size"
        return RESULT_INVALID_HUNK_FILE
      
      hunk_info['size'] = hunk_size & ~HUNKF_ALL
      self.set_mem_flags(hunk_info, hunk_size & HUNKF_ALL, 30)      
      hunk_table.append(hunk_info)
    hunk['hunks'] = hunk_table
    return RESULT_OK
  
  def parse_code_or_data(self, f, hunk):
    num_longs = self.read_long(f)
    if num_longs < 0:
      self.error_string = "%s has invalid size" % (hunk['type_name'])
      return RESULT_INVALID_HUNK_FILE
    
    # read in hunk data
    size = num_longs * 4
    
    hunk['size'] = size & ~HUNKF_ALL
    flags = size & HUNKF_ALL
    self.set_mem_flags(hunk, flags, 30)
    hunk['file_offset'] = f.tell()
    data = f.read(hunk['size'])
    #hunk['data'] = data
    return RESULT_OK
  
  def parse_bss(self, f, hunk):
    num_longs = self.read_long(f)
    if num_longs < 0:
      self.error_string = "%s has invalid size" % (hunk['type_name'])
      return RESULT_INVALID_HUNK_FILE

    # read in hunk data
    size = num_longs * 4

    hunk['size'] = size & ~HUNKF_ALL
    flags = size & HUNKF_ALL
    self.set_mem_flags(hunk, flags, 30)
    return RESULT_OK
  
  def parse_reloc(self, f, hunk):
    num_relocs = 1
    reloc = {}
    hunk['reloc'] = reloc
    while num_relocs != 0:
      num_relocs = self.read_long(f)
      if num_relocs < 0:
        self.error_string = "%s has invalid number of relocations" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE
      elif num_relocs == 0:
        # last relocation found
        break
      
      # build reloc map
      hunk_num = self.read_long(f)
      if hunk_num < 0:
        self.error_string = "%s has invalid hunk num" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE

      offsets = []
      for a in xrange(num_relocs & 0xffff):
        offset = self.read_long(f)
        if offset < 0:
          self.error_string = "%s has invalid relocation #%d offset %d (num_relocs=%d hunk_num=%d, offset=%d)" \
            % (hunk['type_name'],a,offset,num_relocs,hunk_num,f.tell())
          return RESULT_INVALID_HUNK_FILE
        offsets.append(offset)
      reloc[hunk_num] = offsets
    return RESULT_OK
  
  def parse_reloc_short(self, f, hunk):
    num_relocs = 1
    reloc = {}
    hunk['reloc'] = reloc
    total_words = 0
    while num_relocs != 0:
      num_relocs = self.read_word(f)
      if num_relocs < 0:
        self.error_string = "%s has invalid number of relocations" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE
      elif num_relocs == 0:
        # last relocation found
        total_words += 1
        break
      
      # build reloc map
      hunk_num = self.read_word(f)
      if hunk_num < 0:
        self.error_string = "%s has invalid hunk num" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE

      offsets = []
      count = num_relocs & 0xffff
      total_words += count + 2
      for a in xrange(count):
        offset = self.read_word(f)
        if offset < 0:
          self.error_string = "%s has invalid relocation #%d offset %d (num_relocs=%d hunk_num=%d, offset=%d)" \
            % (hunk['type_name'],a,offset,num_relocs,hunk_num,f.tell())
          return RESULT_INVALID_HUNK_FILE
        offsets.append(offset)
      reloc[hunk_num] = offsets

    # padding
    if total_words & 1 == 1:
      self.read_word(f)
    return RESULT_OK
  
  def parse_symbol(self, f, hunk):
    name_len = 1
    symbols = []
    while name_len > 0:
      (name_len, name) = self.read_name(f)
      if name_len < 0:
        self.error_string = "%s has invalid symbol name" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE
      elif name_len == 0:
        # last name occurred
        break
      value = self.read_long(f)
      if value < 0:
        self.error_string = "%s has invalid symbol vlaue" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE
      symbols.append( (name,value) )
    hunk['symbols'] = symbols
    return RESULT_OK
  
  def parse_debug(self, f, hunk):
    num_longs = self.read_long(f)
    if num_longs < 0:
      self.error_string = "%s has invalid size" % (hunk['type_name'])
      return RESULT_INVALID_HUNK_FILE
    size = num_longs * 4
    hunk['data'] = f.read(size)
    return RESULT_OK
  
  def parse_overlay(self, f, hunk):
    tab_size = self.read_long(f)
    if tab_size < 0:
      self.error_string = "%s has invalid size" % (hunk['type_name'])
      return RESULT_INVALID_HUNK_FILE
    tab_size += 1
    size = tab_size * 4
    data = f.read(size)
    return RESULT_OK
  
  def parse_lib(self, f, hunk):
    lib_size = self.read_long(f)
    # TODO: mark the embedded hunk structure
    return RESULT_OK
  
  def parse_index(self, f, hunk):
    index_size = self.read_long(f)
    total_size = index_size * 4
    # first read string table
    strtab_size = self.read_word(f)
    strtab = f.read(strtab_size)
    total_size -= strtab_size
    
    # read units
    units = []
    hunk['units'] = units
    while total_size > 2:
      # read name of unit
      name_offset = self.read_word(f)
      total_size -= 2
      if name_offset == 0:
        break
    
      unit = {}
      units.append(unit)

      # generate unit name
      unit['name'] = self.get_index_name(strtab, name_offset)
      
      # hunks in unit
      hunk_begin = self.read_word(f)
      num_hunks = self.read_word(f)
      total_size -= 4
      unit['hunk_begin'] = hunk_begin
      unit['num_hunks'] = num_hunks

      # for all hunks in unit
      ihunks = []
      unit['hunks'] = ihunks
      for a in xrange(num_hunks):
        ihunk = {}
        ihunks.append(ihunk)
        
        # get hunk info
        name_offset = self.read_word(f)
        hunk_size   = self.read_word(f)
        hunk_type   = self.read_word(f)
        total_size -= 6
        ihunk['name'] = self.get_index_name(strtab, name_offset)
      
        # get references
        num_refs = self.read_word(f)
        total_size -= 2
        if num_refs > 0:
          refs = []
          ihunk['refs'] = refs
          for b in xrange(num_refs):
            name_offset = self.read_word(f)
            total_size -= 2
            name = self.get_index_name(strtab, name_offset)
            refs.append(name)
        
        # get definitions
        num_defs = self.read_word(f)
        total_size -= 2
        if num_defs > 0:
          defs = []
          ihunk['defs'] = defs
          for b in xrange(num_defs):
            name_offset = self.read_word(f)
            def_value = self.read_word(f)
            def_type_flags = self.read_word(f)
            def_type = def_type_flags & 0x3fff
            def_flags = def_type_flags & 0xc000
            total_size -= 6
            name = self.get_index_name(strtab, name_offset)
            d = { 'name':name, 'value':def_value,'type':def_type}
            set_mem_flags(d,def_flags,14)
            defs.append(d)
            
    # align hunk
    if total_size == 2:
      self.read_word(f) 
    elif total_size != 0:
      self.error_string = "%s has invalid padding" % (hunk['type_name'])
      return RESULT_INVALID_HUNK_FILE
    return RESULT_OK
  
  def parse_ext(self, f, hunk):
    exts = []
    hunk['exts'] = exts
    ext_type_size = 1
    while ext_type_size > 0:
      # ext type | size
      ext_type_size = self.read_long(f)
      if ext_type_size < 0:
        self.error_string = "%s has invalid size" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE
      ext_type = ext_type_size >> EXT_TYPE_SHIFT
      ext_size = ext_type_size & EXT_TYPE_SIZE_MASK
      
      # ext name
      l,ext_name = self.read_name_size(f, ext_size)
      if l < 0:
        self.error_string = "%s has invalid name" % (hunk['type_name'])
        return RESULT_INVALID_HUNK_FILE
      elif l == 0:
        break

      # create local ext object
      ext = { 'type' : ext_type, 'name' : ext_name }
      exts.append(ext)
      
      # check and setup type name
      if not ext_names.has_key(ext_type):
        self.error_string = "%s has unspported ext entry %d" % (hunk['type_name'],ext_type)
        return RESULT_INVALID_HUNK_FILE
      ext['type_name'] = ext_names[ext_type]
      
      # ext common
      if ext_type == EXT_ABSCOMMON or ext_type == EXT_RELCOMMON:
        ext['common_size'] = self.read_long(f)
      # ext def
      elif ext_type == EXT_DEF or ext_type == EXT_ABS or ext_type == EXT_RES:
        ext['def'] = self.read_long(f)
      # ext ref
      else:
        num_refs = self.read_long(f)
        if num_refs == 0:
          num_refs = 1
        refs = []
        for a in xrange(num_refs):
          ref = self.read_long(f)
          refs.append(ref)
        ext['refs'] = refs
        
    return RESULT_OK
  
  def parse_unit_or_name(self, f, hunk):
    l,n = self.read_name(f)
    if l < 0:
      self.error_string = "%s has invalid name" % (hunk['type_name'])
      return RESULT_INVALID_HUNK_FILE
    elif l > 0:
      hunk['name'] = n
    return RESULT_OK
    
  def set_mem_flags(self, hunk, flags, shift):
    f = flags >> shift
    if f & 1 == 1:
      hunk['memf'] = 'chip'
    elif f & 2 == 2:
      hunk['memf'] = 'fast'
    
  # ----- public functions -----
  
  """Read a hunk file and build internal hunk structure
     Return status and set self.error_string on failure
  """
  def read_file(self, hfile):
    with open(hfile) as f:
      return self.read_file_obj(hfile, f)

  """Read a hunk from memory"""
  def read_mem(self, name, data):
    fobj = StringIO.StringIO(data)
    return self.read_file_obj(name, fobj)

  def read_file_obj(self, hfile, f):
    self.hunks = []
    is_first_hunk = True
    was_end = False
    
    while True:
      # read hunk type
      hunk_raw_type = self.read_long(f)
      if hunk_raw_type == -1:
        # eof
        break
      elif hunk_raw_type < 0:
        if is_first_hunk:
          self.error_string = "No valid hunk file: '%s' is too short" % (hfile) 
          return RESULT_NO_HUNK_FILE            
        else:
          self.error_string = "Error reading hunk type @%08x" % (f.tell())
          return RESULT_INVALID_HUNK_FILE
      
      hunk_type = hunk_raw_type & HUNK_TYPE_MASK
      hunk_flags = hunk_raw_type & HUNK_FLAGS_MASK
      
      # check range of hunk type
      if hunk_type < HUNK_MIN or hunk_type > HUNK_MAX:
        # no hunk file?
        if is_first_hunk:
          self.error_string = "No valid hunk file: '%s' type was %d" % (hfile, hunk_type) 
          return RESULT_NO_HUNK_FILE
        elif was_end:
          # garbage after an end tag is ignored
          return RESULT_OK
        else:
          self.error_string = "Invalid hunk type %d found at @%08x" % (hunk_type,f.tell())
          return RESULT_INVALID_HUNK_FILE
      else:
        # check for valid first hunk type
        if is_first_hunk and not self.is_valid_first_hunk_type(hunk_type):
          self.error_string = "No valid hunk file: '%s' first hunk type was %d" % (hfile, hunk_type) 
          return RESULT_INVALID_HUNK_FILE
        
        is_first_hunk = False
        was_end = False
        
        hunk = { 'type' : hunk_type }
        self.hunks.append(hunk)
        hunk['type_name'] = hunk_names[hunk_type - HUNK_MIN]
        self.set_mem_flags(hunk, hunk_flags, 30)

        # V37 fix
        if self.v37_compat and hunk_type == HUNK_DREL32:
          hunk_type = HUNK_RELOC32SHORT

        # ----- HUNK_HEADER -----
        if hunk_type == HUNK_HEADER:
          result = self.parse_header(f,hunk)
        # ----- HUNK_CODE/HUNK_DATA ------
        elif hunk_type == HUNK_CODE or hunk_type == HUNK_DATA:
          result = self.parse_code_or_data(f,hunk)
        # ---- HUNK_BSS ----
        elif hunk_type == HUNK_BSS:
          result = self.parse_bss(f,hunk)
        # ----- HUNK_<reloc> -----
        elif hunk_type == HUNK_RELRELOC32 or hunk_type == HUNK_ABSRELOC16 \
          or hunk_type == HUNK_RELRELOC8 or hunk_type == HUNK_RELRELOC16 or hunk_type == HUNK_ABSRELOC32 \
          or hunk_type ==HUNK_DREL32 or hunk_type == HUNK_DREL16 or hunk_type == HUNK_DREL8:
          result = self.parse_reloc(f,hunk)
        # ---- HUNK_<reloc short> -----
        elif hunk_type == HUNK_RELOC32SHORT:
          result = self.parse_reloc_short(f,hunk)
        # ----- HUNK_SYMBOL -----
        elif hunk_type == HUNK_SYMBOL:
          result = self.parse_symbol(f,hunk)
        # ----- HUNK_DEBUG -----
        elif hunk_type == HUNK_DEBUG:
          result = self.parse_debug(f,hunk)
        # ----- HUNK_END -----
        elif hunk_type == HUNK_END:
          was_end = True
          result = RESULT_OK
        # ----- HUNK_OVERLAY -----
        elif hunk_type == HUNK_OVERLAY:
          result = self.parse_overlay(f,hunk)
        # ----- HUNK_BREAK -----
        elif hunk_type == HUNK_BREAK:
          result = RESULT_OK        
        # ----- HUNK_LIB -----
        elif hunk_type == HUNK_LIB:
          result = self.parse_lib(f,hunk)
        # ----- HUNK_INDEX -----
        elif hunk_type == HUNK_INDEX:
          result = self.parse_index(f,hunk)
        # ----- HUNK_EXT -----
        elif hunk_type == HUNK_EXT:
          result = self.parse_ext(f,hunk)
        # ----- HUNK_UNIT -----
        elif hunk_type == HUNK_UNIT or hunk_type == HUNK_NAME:
          result = self.parse_unit_or_name(f,hunk)
        # ----- oops! unsupported hunk -----
        else:
          self.error_string = "unsupported hunk %d" % (hunk_type)
          return RESULT_UNSUPPORTED_HUNKS

        # a parse error occurred
        if result != RESULT_OK:
          return result

      return RESULT_OK

