"""A class for reading Amiga executables and object files in Hunk format"""

import os
import struct
import io
from types import *
from .Hunk import *


class HunkReader:
    """Load Amiga executable Hunk structures"""

    def __init__(self):
        self.hunks = []
        self.error_string = None
        self.type = None
        self.header = None
        self.segments = []
        self.overlay = None
        self.overlay_headers = None
        self.overlay_segments = None
        self.libs = None
        self.units = None

    def get_struct_summary(self, obj):
        if type(obj) == ListType:
            result = []
            for a in obj:
                v = self.get_struct_summary(a)
                if v != None:
                    result.append(v)
            return "[" + ",".join(result) + "]"
        elif type(obj) == DictType:
            if "type_name" in obj:
                type_name = obj["type_name"]
                return type_name.replace("HUNK_", "")
            else:
                result = []
                for k in list(obj.keys()):
                    v = self.get_struct_summary(obj[k])
                    if v != None:
                        result.append(k + ":" + v)
                return "{" + ",".join(result) + "}"
        else:
            return None

    def get_long(self, data):
        return struct.unpack(">I", data)[0]

    def read_long(self, f):
        data = f.read(4)
        if len(data) == 0:
            return -1
        elif len(data) != 4:
            return -(len(data) + 1)
        return struct.unpack(">I", data)[0]

    def read_word(self, f):
        data = f.read(2)
        if len(data) == 0:
            return -1
        elif len(data) != 2:
            return -(len(data) + 1)
        return struct.unpack(">H", data)[0]

    def read_name(self, f):
        num_longs = self.read_long(f)
        if num_longs < 0:
            return -1, None
        elif num_longs == 0:
            return 0, ""
        else:
            return self.read_name_size(f, num_longs)

    def read_tag(self, f):
        data = f.read(4)
        if len(data) == 0:
            return -1
        elif len(data) != 4:
            return -(len(data) + 1)
        return data

    def read_name_size(self, f, num_longs):
        size = (num_longs & 0xFFFFFF) * 4
        data = f.read(size)
        if len(data) < size:
            return -1, None
        endpos = data.find(b"\0")
        if endpos == -1:
            return size, data.decode("latin-1")
        elif endpos == 0:
            return 0, ""
        else:
            return size, data[:endpos].decode("latin-1")

    def get_index_name(self, strtab, offset):
        end = strtab.find(b"\0", offset)
        if end == -1:
            return strtab[offset:].decode("latin-1")
        else:
            return strtab[offset:end].decode("latin-1")

    def is_valid_first_hunk_type(self, hunk_type):
        return (
            hunk_type == HUNK_HEADER or hunk_type == HUNK_LIB or hunk_type == HUNK_UNIT
        )

    def parse_header(self, f, hunk):
        names = []
        hunk["names"] = names
        while True:
            l, s = self.read_name(f)
            if l < 0:
                self.error_string = "Error parsing HUNK_HEADER names"
                return RESULT_INVALID_HUNK_FILE
            elif l == 0:
                break
            names.append(s)

        # table size and hunk range
        table_size = self.read_long(f)
        first_hunk = self.read_long(f)
        last_hunk = self.read_long(f)
        if table_size < 0 or first_hunk < 0 or last_hunk < 0:
            self.error_string = (
                "HUNK_HEADER invalid table_size or first_hunk or last_hunk"
            )
            return RESULT_INVALID_HUNK_FILE

        hunk["table_size"] = table_size
        hunk["first_hunk"] = first_hunk
        hunk["last_hunk"] = last_hunk

        # determine number of hunks in size table
        num_hunks = last_hunk - first_hunk + 1
        hunk_table = []
        for a in range(num_hunks):
            hunk_info = {}
            hunk_size = self.read_long(f)
            if hunk_size < 0:
                self.error_string = "HUNK_HEADER contains invalid hunk_size"
                return RESULT_INVALID_HUNK_FILE
            hunk_bytes = hunk_size & ~HUNKF_ALL
            hunk_bytes *= 4  # longs to bytes
            hunk_info["size"] = hunk_bytes
            self.set_mem_flags(hunk_info, hunk_size & HUNKF_ALL, 30)
            hunk_table.append(hunk_info)
        hunk["hunks"] = hunk_table
        return RESULT_OK

    def parse_code_or_data(self, f, hunk):
        num_longs = self.read_long(f)
        if num_longs < 0:
            self.error_string = "%s has invalid size" % (hunk["type_name"])
            return RESULT_INVALID_HUNK_FILE

        # read in hunk data
        size = num_longs * 4

        hunk["size"] = size & ~HUNKF_ALL
        flags = size & HUNKF_ALL
        self.set_mem_flags(hunk, flags, 30)
        hunk["data_file_offset"] = f.tell()
        data = f.read(hunk["size"])
        hunk["data"] = data
        return RESULT_OK

    def parse_bss(self, f, hunk):
        num_longs = self.read_long(f)
        if num_longs < 0:
            self.error_string = "%s has invalid size" % (hunk["type_name"])
            return RESULT_INVALID_HUNK_FILE

        # read in hunk data
        size = num_longs * 4

        hunk["size"] = size & ~HUNKF_ALL
        flags = size & HUNKF_ALL
        self.set_mem_flags(hunk, flags, 30)
        return RESULT_OK

    def parse_reloc(self, f, hunk):
        num_relocs = 1
        reloc = {}
        hunk["reloc"] = reloc
        while num_relocs != 0:
            num_relocs = self.read_long(f)
            if num_relocs < 0:
                self.error_string = "%s has invalid number of relocations" % (
                    hunk["type_name"]
                )
                return RESULT_INVALID_HUNK_FILE
            elif num_relocs == 0:
                # last relocation found
                break

            # build reloc map
            hunk_num = self.read_long(f)
            if hunk_num < 0:
                self.error_string = "%s has invalid hunk num" % (hunk["type_name"])
                return RESULT_INVALID_HUNK_FILE

            offsets = []
            for a in range(num_relocs & 0xFFFF):
                offset = self.read_long(f)
                if offset < 0:
                    self.error_string = (
                        "%s has invalid relocation #%d offset %d (num_relocs=%d hunk_num=%d, offset=%d)"
                        % (hunk["type_name"], a, offset, num_relocs, hunk_num, f.tell())
                    )
                    return RESULT_INVALID_HUNK_FILE
                offsets.append(offset)
            reloc[hunk_num] = offsets
        return RESULT_OK

    def parse_reloc_short(self, f, hunk):
        num_relocs = 1
        reloc = {}
        hunk["reloc"] = reloc
        total_words = 0
        while num_relocs != 0:
            num_relocs = self.read_word(f)
            if num_relocs < 0:
                self.error_string = "%s has invalid number of relocations" % (
                    hunk["type_name"]
                )
                return RESULT_INVALID_HUNK_FILE
            elif num_relocs == 0:
                # last relocation found
                total_words += 1
                break

            # build reloc map
            hunk_num = self.read_word(f)
            if hunk_num < 0:
                self.error_string = "%s has invalid hunk num" % (hunk["type_name"])
                return RESULT_INVALID_HUNK_FILE

            offsets = []
            count = num_relocs & 0xFFFF
            total_words += count + 2
            for a in range(count):
                offset = self.read_word(f)
                if offset < 0:
                    self.error_string = (
                        "%s has invalid relocation #%d offset %d (num_relocs=%d hunk_num=%d, offset=%d)"
                        % (hunk["type_name"], a, offset, num_relocs, hunk_num, f.tell())
                    )
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
        hunk["symbols"] = symbols
        while name_len > 0:
            (name_len, name) = self.read_name(f)
            if name_len < 0:
                self.error_string = "%s has invalid symbol name" % (hunk["type_name"])
                return RESULT_INVALID_HUNK_FILE
            elif name_len == 0:
                # last name occurred
                break
            value = self.read_long(f)
            if value < 0:
                self.error_string = "%s has invalid symbol value" % (hunk["type_name"])
                return RESULT_INVALID_HUNK_FILE
            symbols.append((name, value))
        return RESULT_OK

    def parse_debug(self, f, hunk):
        num_longs = self.read_long(f)
        if num_longs < 0:
            self.error_string = "%s has invalid size" % (hunk["type_name"])
            return RESULT_INVALID_HUNK_FILE
        size = num_longs * 4

        offset = self.read_long(f)
        hunk["debug_offset"] = offset
        tag = self.read_tag(f)
        hunk["debug_type"] = tag
        size -= 8

        if tag == "LINE":
            # parse LINE: source line -> code offset mapping
            l = self.read_long(f)
            size -= l * 4 + 4
            l, n = self.read_name_size(f, l)
            src_map = []
            hunk["src_file"] = n
            hunk["src_map"] = src_map
            while size > 0:
                line_no = self.read_long(f)
                offset = self.read_long(f)
                size -= 8
                src_map.append([line_no, offset])
        else:
            # read unknown DEBUG hunk
            hunk["data"] = f.read(size)
        return RESULT_OK

    def find_first_code_hunk(self):
        for hunk in self.hunks:
            if hunk["type"] == HUNK_CODE:
                return hunk
        return None

    def parse_overlay(self, f, hunk):
        # read size of overlay hunk
        ov_size = self.read_long(f)
        if ov_size < 0:
            self.error_string = "%s has invalid size" % (hunk["type_name"])
            return RESULT_INVALID_HUNK_FILE

        # read data of overlay
        byte_size = (ov_size + 1) * 4
        ov_data = f.read(byte_size)
        hunk["ov_data"] = ov_data

        # check: first get header hunk
        hdr_hunk = self.hunks[0]
        if hdr_hunk["type"] != HUNK_HEADER:
            self.error_string = "%s has no header hunk" % (hunk["type_name"])
            return RESULT_INVALID_HUNK_FILE

        # first find the code segment of the overlay manager
        overlay_mgr_hunk = self.find_first_code_hunk()
        if overlay_mgr_hunk == None:
            self.error_string = "%s has no overlay manager hunk" % (hunk["type_name"])
            return RESULT_INVALID_HUNK_FILE

        # check overlay manager
        overlay_mgr_data = overlay_mgr_hunk["data"]
        magic = self.get_long(overlay_mgr_data[4:8])
        if magic != 0xABCD:
            self.error_string = "no valid overlay manager magic found"
            return RESULT_INVALID_HUNK_FILE

        # check for standard overlay manager
        magic2 = self.get_long(overlay_mgr_data[24:28])
        magic3 = self.get_long(overlay_mgr_data[28:32])
        magic4 = self.get_long(overlay_mgr_data[32:36])
        std_overlay = (
            (magic2 == 0x5BA0) and (magic3 == 0x074F7665) and (magic4 == 0x726C6179)
        )
        hunk["ov_std"] = std_overlay

        return RESULT_OK

    def parse_lib(self, f, hunk):
        lib_size = self.read_long(f)
        hunk["lib_file_offset"] = f.tell()
        return RESULT_OK, lib_size * 4

    def parse_index(self, f, hunk):
        index_size = self.read_long(f)
        total_size = index_size * 4

        # first read string table
        strtab_size = self.read_word(f)
        strtab = f.read(strtab_size)
        total_size -= strtab_size + 2

        # read units
        units = []
        hunk["units"] = units
        unit_no = 0
        while total_size > 2:
            # read name of unit
            name_offset = self.read_word(f)
            total_size -= 2

            unit = {}
            units.append(unit)
            unit["unit_no"] = unit_no
            unit_no += 1

            # generate unit name
            unit["name"] = self.get_index_name(strtab, name_offset)

            # hunks in unit
            hunk_begin = self.read_word(f)
            num_hunks = self.read_word(f)
            total_size -= 4
            unit["hunk_begin_offset"] = hunk_begin

            # for all hunks in unit
            ihunks = []
            unit["hunk_infos"] = ihunks
            for a in range(num_hunks):
                ihunk = {}
                ihunks.append(ihunk)

                # get hunk info
                name_offset = self.read_word(f)
                hunk_size = self.read_word(f)
                hunk_type = self.read_word(f)
                total_size -= 6
                ihunk["name"] = self.get_index_name(strtab, name_offset)
                ihunk["size"] = hunk_size
                ihunk["type"] = hunk_type & 0x3FFF
                self.set_mem_flags(ihunk, hunk_type & 0xC000, 14)
                ihunk["type_name"] = hunk_names[hunk_type & 0x3FFF]

                # get references
                num_refs = self.read_word(f)
                total_size -= 2
                if num_refs > 0:
                    refs = []
                    ihunk["refs"] = refs
                    for b in range(num_refs):
                        ref = {}
                        name_offset = self.read_word(f)
                        total_size -= 2
                        name = self.get_index_name(strtab, name_offset)
                        if name == "":
                            # 16 bit refs point to the previous zero byte before the string entry...
                            name = self.get_index_name(strtab, name_offset + 1)
                            ref["bits"] = 16
                        else:
                            ref["bits"] = 32
                        ref["name"] = name
                        refs.append(ref)

                # get definitions
                num_defs = self.read_word(f)
                total_size -= 2
                if num_defs > 0:
                    defs = []
                    ihunk["defs"] = defs
                    for b in range(num_defs):
                        name_offset = self.read_word(f)
                        def_value = self.read_word(f)
                        def_type_flags = self.read_word(f)
                        def_type = def_type_flags & 0x3FFF
                        def_flags = def_type_flags & 0xC000
                        total_size -= 6
                        name = self.get_index_name(strtab, name_offset)
                        d = {"name": name, "value": def_value, "type": def_type}
                        self.set_mem_flags(d, def_flags, 14)
                        defs.append(d)

        # align hunk
        if total_size == 2:
            self.read_word(f)
        elif total_size != 0:
            self.error_string = "%s has invalid padding: %d" % (
                hunk["type_name"],
                total_size,
            )
            return RESULT_INVALID_HUNK_FILE
        return RESULT_OK

    def parse_ext(self, f, hunk):
        ext_def = []
        ext_ref = []
        ext_common = []
        hunk["ext_def"] = ext_def
        hunk["ext_ref"] = ext_ref
        hunk["ext_common"] = ext_common
        ext_type_size = 1
        while ext_type_size > 0:
            # ext type | size
            ext_type_size = self.read_long(f)
            if ext_type_size < 0:
                self.error_string = "%s has invalid size" % (hunk["type_name"])
                return RESULT_INVALID_HUNK_FILE
            ext_type = ext_type_size >> EXT_TYPE_SHIFT
            ext_size = ext_type_size & EXT_TYPE_SIZE_MASK

            # ext name
            l, ext_name = self.read_name_size(f, ext_size)
            if l < 0:
                self.error_string = "%s has invalid name" % (hunk["type_name"])
                return RESULT_INVALID_HUNK_FILE
            elif l == 0:
                break

            # create local ext object
            ext = {"type": ext_type, "name": ext_name}

            # check and setup type name
            if ext_type not in ext_names:
                self.error_string = "%s has unspported ext entry %d" % (
                    hunk["type_name"],
                    ext_type,
                )
                return RESULT_INVALID_HUNK_FILE
            ext["type_name"] = ext_names[ext_type]

            # ext common
            if ext_type == EXT_ABSCOMMON or ext_type == EXT_RELCOMMON:
                ext["common_size"] = self.read_long(f)
                ext_common.append(ext)
            # ext def
            elif ext_type == EXT_DEF or ext_type == EXT_ABS or ext_type == EXT_RES:
                ext["def"] = self.read_long(f)
                ext_def.append(ext)
            # ext ref
            else:
                num_refs = self.read_long(f)
                if num_refs == 0:
                    num_refs = 1
                refs = []
                for a in range(num_refs):
                    ref = self.read_long(f)
                    refs.append(ref)
                ext["refs"] = refs
                ext_ref.append(ext)

        return RESULT_OK

    def parse_unit_or_name(self, f, hunk):
        l, n = self.read_name(f)
        if l < 0:
            self.error_string = "%s has invalid name" % (hunk["type_name"])
            return RESULT_INVALID_HUNK_FILE
        elif l > 0:
            hunk["name"] = n
        else:
            hunk["name"] = ""
        return RESULT_OK

    def set_mem_flags(self, hunk, flags, shift):
        f = flags >> shift
        if f & 1 == 1:
            hunk["memf"] = "chip"
        elif f & 2 == 2:
            hunk["memf"] = "fast"
        else:
            hunk["memf"] = ""

    # ----- public functions -----

    """Read a hunk file and build internal hunk structure
     Return status and set self.error_string on failure
  """

    def read_file(self, hfile):
        with open(hfile, "rb") as f:
            return self.read_file_obj(hfile, f)

    """Read a hunk from memory"""

    def read_mem(self, name, data):
        fobj = io.StringIO(data)
        return self.read_file_obj(name, fobj)

    def read_file_obj(self, hfile, f):
        self.hunks = []
        is_first_hunk = True
        is_exe = False
        was_end = False
        was_overlay = False
        self.error_string = None
        lib_size = 0
        last_file_offset = 0

        while True:
            hunk_file_offset = f.tell()

            # read hunk type
            hunk_raw_type = self.read_long(f)
            if hunk_raw_type == -1 or hunk_raw_type == -2:  # tolerate extra byte at end
                if is_first_hunk:
                    self.error_string = "No valid hunk file: '%s' is empty" % (hfile)
                    return RESULT_NO_HUNK_FILE
                else:
                    # eof
                    break
            elif hunk_raw_type < 0:
                if is_first_hunk:
                    self.error_string = "No valid hunk file: '%s' is too short" % (
                        hfile
                    )
                    return RESULT_NO_HUNK_FILE
                else:
                    self.error_string = "Error reading hunk type @%08x" % (f.tell())
                    return RESULT_INVALID_HUNK_FILE

            hunk_type = hunk_raw_type & HUNK_TYPE_MASK
            hunk_flags = hunk_raw_type & HUNK_FLAGS_MASK

            # check range of hunk type
            if hunk_type not in hunk_names:
                # no hunk file?
                if is_first_hunk:
                    self.error_string = "No hunk file: '%s' type was %d" % (
                        hfile,
                        hunk_type,
                    )
                    return RESULT_NO_HUNK_FILE
                elif was_end:
                    # garbage after an end tag is ignored
                    return RESULT_OK
                elif was_overlay:
                    # seems to be a custom overlay -> read to end of file
                    ov_custom_data = f.read()
                    self.hunks[-1]["custom_data"] = ov_custom_data
                    return RESULT_OK
                else:
                    self.error_string = "Invalid hunk type %d/%x found at @%08x" % (
                        hunk_type,
                        hunk_type,
                        f.tell(),
                    )
                    return RESULT_INVALID_HUNK_FILE
            else:
                # check for valid first hunk type
                if is_first_hunk:
                    if not self.is_valid_first_hunk_type(hunk_type):
                        self.error_string = (
                            "No hunk file: '%s' first hunk type was %d"
                            % (hfile, hunk_type)
                        )
                        return RESULT_NO_HUNK_FILE
                    else:
                        is_exe = hunk_type == HUNK_HEADER

                is_first_hunk = False
                was_end = False
                was_overlay = False

                # V37 fix: in an executable DREL32 is wrongly assigned and actually is a RELOC32SHORT
                if hunk_type == HUNK_DREL32 and is_exe:
                    hunk_type = HUNK_RELOC32SHORT

                hunk = {"type": hunk_type, "hunk_file_offset": hunk_file_offset}
                self.hunks.append(hunk)
                hunk["type_name"] = hunk_names[hunk_type]
                self.set_mem_flags(hunk, hunk_flags, 30)

                # account for lib
                last_hunk_size = hunk_file_offset - last_file_offset
                if lib_size > 0:
                    lib_size -= last_hunk_size
                if lib_size > 0:
                    hunk["in_lib"] = True

                # ----- HUNK_HEADER -----
                if hunk_type == HUNK_HEADER:
                    result = self.parse_header(f, hunk)
                # ----- HUNK_CODE/HUNK_DATA ------
                elif (
                    hunk_type == HUNK_CODE
                    or hunk_type == HUNK_DATA
                    or hunk_type == HUNK_PPC_CODE
                ):
                    result = self.parse_code_or_data(f, hunk)
                # ---- HUNK_BSS ----
                elif hunk_type == HUNK_BSS:
                    result = self.parse_bss(f, hunk)
                # ----- HUNK_<reloc> -----
                elif (
                    hunk_type == HUNK_RELRELOC32
                    or hunk_type == HUNK_ABSRELOC16
                    or hunk_type == HUNK_RELRELOC8
                    or hunk_type == HUNK_RELRELOC16
                    or hunk_type == HUNK_ABSRELOC32
                    or hunk_type == HUNK_DREL32
                    or hunk_type == HUNK_DREL16
                    or hunk_type == HUNK_DREL8
                    or hunk_type == HUNK_RELRELOC26
                ):
                    result = self.parse_reloc(f, hunk)
                # ---- HUNK_<reloc short> -----
                elif hunk_type == HUNK_RELOC32SHORT:
                    result = self.parse_reloc_short(f, hunk)
                # ----- HUNK_SYMBOL -----
                elif hunk_type == HUNK_SYMBOL:
                    result = self.parse_symbol(f, hunk)
                # ----- HUNK_DEBUG -----
                elif hunk_type == HUNK_DEBUG:
                    result = self.parse_debug(f, hunk)
                # ----- HUNK_END -----
                elif hunk_type == HUNK_END:
                    was_end = True
                    result = RESULT_OK
                # ----- HUNK_OVERLAY -----
                elif hunk_type == HUNK_OVERLAY:
                    result = self.parse_overlay(f, hunk)
                    was_overlay = True
                # ----- HUNK_BREAK -----
                elif hunk_type == HUNK_BREAK:
                    result = RESULT_OK
                # ----- HUNK_LIB -----
                elif hunk_type == HUNK_LIB:
                    result, lib_size = self.parse_lib(f, hunk)
                    lib_size += 8  # add size of HUNK_LIB itself
                # ----- HUNK_INDEX -----
                elif hunk_type == HUNK_INDEX:
                    result = self.parse_index(f, hunk)
                # ----- HUNK_EXT -----
                elif hunk_type == HUNK_EXT:
                    result = self.parse_ext(f, hunk)
                # ----- HUNK_UNIT -----
                elif hunk_type == HUNK_UNIT or hunk_type == HUNK_NAME:
                    result = self.parse_unit_or_name(f, hunk)
                # ----- oops! unsupported hunk -----
                else:
                    self.error_string = "unsupported hunk %d" % (hunk_type)
                    return RESULT_UNSUPPORTED_HUNKS

                # a parse error occurred
                if result != RESULT_OK:
                    return result

                last_file_offset = hunk_file_offset
        return RESULT_OK

    """Return a list with all the hunk type names that were found
  """

    def get_hunk_summary(self):
        return self.get_struct_summary(self.hunks)

    # ---------- Build Segments from Hunks ----------

    def build_loadseg(self):
        in_header = True
        seek_begin = False
        segment = None
        segment_list = self.segments
        for e in self.hunks:
            hunk_type = e["type"]

            # check for end of header
            if in_header and hunk_type in loadseg_valid_begin_hunks:
                in_header = False
                seek_begin = True

            if in_header:
                if hunk_type == HUNK_HEADER:
                    # we are in an overlay!
                    if self.overlay != None:
                        segment_list = []
                        self.overlay_segments.append(segment_list)
                        self.overlay_headers.append(e)
                    else:
                        # set load_seg() header
                        self.header = e

                    # start a new segment
                    segment = []

                    # setup hunk counter
                    hunk_no = e["first_hunk"]

                # we allow a debug hunk in header for SAS compatibility
                elif hunk_type == HUNK_DEBUG:
                    segment.append(e)
                else:
                    self.error_string = "Expected header in loadseg: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False

            elif seek_begin:
                # a new hunk shall begin
                if hunk_type in loadseg_valid_begin_hunks:
                    segment = [e]
                    segment_list.append(segment)
                    seek_header = False
                    seek_begin = False
                    e["hunk_no"] = hunk_no
                    e["alloc_size"] = self.header["hunks"][hunk_no]["size"]
                    hunk_no += 1
                # add an extra overlay "hunk"
                elif hunk_type == HUNK_OVERLAY:
                    # assume hunk to be empty
                    if self.overlay != None:
                        self.error_string = "Multiple overlay in loadseg: %s %d/%x" % (
                            e["type_name"],
                            hunk_type,
                            hunk_type,
                        )
                        return False
                    self.overlay = e
                    self.overlay_headers = []
                    self.overlay_segments = []
                    in_header = True
                # break
                elif hunk_type == HUNK_BREAK:
                    # assume hunk to be empty
                    in_header = True
                # broken hunk: multiple END or other hunks
                elif hunk_type in [HUNK_END, HUNK_NAME, HUNK_DEBUG]:
                    pass
                else:
                    self.error_string = "Expected hunk start in loadseg: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False

            else:
                # an extra block in hunk or end is expected
                if hunk_type == HUNK_END:
                    seek_begin = True
                # contents of hunk
                elif hunk_type in loadseg_valid_extra_hunks or hunk_type == HUNK_DREL32:
                    segment.append(e)
                # broken hunk file without END tag
                elif hunk_type in loadseg_valid_begin_hunks:
                    segment = [e]
                    segment_list.append(segment)
                    seek_header = False
                    seek_begin = False
                    e["hunk_no"] = hunk_no
                    e["alloc_size"] = self.header["hunks"][hunk_no]["size"]
                    hunk_no += 1
                # unecpected hunk?!
                else:
                    self.error_string = "Unexpected hunk extra in loadseg: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False
        return True

    def build_unit(self):
        force_unit = True
        in_hunk = False
        name = None
        segment = None
        unit = None
        self.units = []
        unit_no = 0
        for e in self.hunks:
            hunk_type = e["type"]

            # optional unit as first entry
            if hunk_type == HUNK_UNIT:
                unit = {}
                unit["name"] = e["name"]
                unit["unit_no"] = unit_no
                unit["segments"] = []
                unit["unit"] = e
                unit_no += 1
                self.units.append(unit)
                force_unit = False
                hunk_no = 0
            elif force_unit:
                self.error_string = "Expected name hunk in unit: %s %d/%x" % (
                    e["type_name"],
                    hunk_type,
                    hunk_type,
                )
                return False
            elif not in_hunk:
                # begin a named hunk
                if hunk_type == HUNK_NAME:
                    name = e["name"]
                # main hunk block
                elif hunk_type in unit_valid_main_hunks:
                    segment = [e]
                    unit["segments"].append(segment)
                    # give main block the NAME
                    if name != None:
                        e["name"] = name
                        name = None
                    e["hunk_no"] = hunk_no
                    hunk_no += 1
                    in_hunk = True
                # broken hunk: ignore multi ENDs
                elif hunk_type == HUNK_END:
                    pass
                else:
                    self.error_string = "Expected main hunk in unit: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False
            else:
                # a hunk is finished
                if hunk_type == HUNK_END:
                    in_hunk = False
                # contents of hunk
                elif hunk_type in unit_valid_extra_hunks:
                    segment.append(e)
                # unecpected hunk?!
                else:
                    self.error_string = "Unexpected hunk in unit: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False

        return True

    def build_lib(self):
        self.libs = []
        lib_segments = []
        seek_lib = True
        seek_main = False
        for e in self.hunks:
            hunk_type = e["type"]

            # seeking for a LIB hunk
            if seek_lib:
                if hunk_type == HUNK_LIB:
                    segment_list = []
                    lib_segments.append(segment_list)
                    seek_lib = False
                    seek_main = True
                    hunk_no = 0

                    # get start address of lib hunk in file
                    lib_file_offset = e["lib_file_offset"]
                else:
                    self.error_string = "Expected lib hunk in lib: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False
            elif seek_main:
                # end of lib? -> index!
                if hunk_type == HUNK_INDEX:
                    seek_main = False
                    seek_lib = True
                    lib_units = []
                    if not self.resolve_index_hunks(e, segment_list, lib_units):
                        self.error_string = "Error resolving index hunks!"
                        return False
                    lib = {}
                    lib["units"] = lib_units
                    lib["lib_no"] = len(self.libs)
                    lib["index"] = e
                    self.libs.append(lib)
                # start of a hunk
                elif hunk_type in unit_valid_main_hunks:
                    segment = [e]
                    e["hunk_no"] = hunk_no
                    hunk_no += 1
                    segment_list.append(segment)
                    seek_main = False

                    # calc relative lib address
                    hunk_lib_offset = e["hunk_file_offset"] - lib_file_offset
                    e["hunk_lib_offset"] = hunk_lib_offset
                else:
                    self.error_string = "Expected main hunk in lib: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False
            else:
                # end hunk
                if hunk_type == HUNK_END:
                    seek_main = True
                # extra contents
                elif hunk_type in unit_valid_extra_hunks:
                    segment.append(e)
                else:
                    self.error_string = "Unexpected hunk in lib: %s %d/%x" % (
                        e["type_name"],
                        hunk_type,
                        hunk_type,
                    )
                    return False

        return True

    """Resolve hunks referenced in the index"""

    def resolve_index_hunks(self, index, segment_list, lib_units):
        units = index["units"]
        no = 0
        for unit in units:
            lib_unit = {}
            unit_segments = []
            lib_unit["segments"] = unit_segments
            lib_unit["name"] = unit["name"]
            lib_unit["unit_no"] = no
            lib_unit["index_unit"] = unit
            lib_units.append(lib_unit)
            no += 1

            # try to find segment with start offset
            hunk_offset = unit["hunk_begin_offset"]
            found = False
            for segment in segment_list:
                hunk_no = segment[0]["hunk_no"]
                lib_off = segment[0]["hunk_lib_offset"] // 4  # is in longwords
                if lib_off == hunk_offset:
                    # found segment
                    num_segs = len(unit["hunk_infos"])
                    for i in range(num_segs):
                        info = unit["hunk_infos"][i]
                        seg = segment_list[hunk_no + i]
                        unit_segments.append(seg)
                        # renumber hunk
                        seg[0]["hunk_no"] = i
                        seg[0]["name"] = info["name"]
                        seg[0]["index_hunk"] = info
                    found = True

            if not found:
                return False
        return True

    """From the hunk list build a set of segments that form the actual binary"""

    def build_segments(self):
        self.segments = []
        if len(self.hunks) == 0:
            self.type = TYPE_UNKNOWN
            return False

        # determine type of file from first hunk
        first_hunk_type = self.hunks[0]["type"]
        if first_hunk_type == HUNK_HEADER:
            self.type = TYPE_LOADSEG
            return self.build_loadseg()
        elif first_hunk_type == HUNK_UNIT:
            self.type = TYPE_UNIT
            return self.build_unit()
        elif first_hunk_type == HUNK_LIB:
            self.type = TYPE_LIB
            return self.build_lib()
        else:
            self.type = TYPE_UNKNOWN
            return False

    """Return a summary of the created segment structure"""

    def get_segment_summary(self):
        return self.get_struct_summary(self.segments)

    def get_overlay_segment_summary(self):
        if self.overlay_segments != None:
            return self.get_struct_summary(self.overlay_segments)
        else:
            return None

    def get_libs_summary(self):
        if self.libs != None:
            return self.get_struct_summary(self.libs)
        else:
            return None

    def get_units_summary(self):
        if self.units != None:
            return self.get_struct_summary(self.units)
        else:
            return None
