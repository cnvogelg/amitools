SEGMENT_TYPE_CODE = 0
SEGMENT_TYPE_DATA = 1
SEGMENT_TYPE_BSS = 2

SEGMENT_FLAG_READ_ONLY = 1

segment_type_names = ["CODE", "DATA", "BSS"]

BIN_IMAGE_TYPE_HUNK = 0
BIN_IMAGE_TYPE_ELF = 1

bin_image_type_names = ["hunk", "elf"]

BIN_IMAGE_RELOC_32 = 1
BIN_IMAGE_RELOC_PC32 = 4


class Reloc:
    def __init__(self, offset, type=BIN_IMAGE_RELOC_32, width=2, addend=0):
        self.offset = offset
        self.type = type
        self.width = width
        self.addend = addend

    def get_offset(self):
        return self.offset

    def get_type(self):
        return self.type

    def get_width(self):
        return self.width

    def get_addend(self):
        return self.addend


class Relocations:
    def __init__(self, to_seg):
        self.to_seg = to_seg
        self.entries = []

    def add_reloc(self, reloc):
        self.entries.append(reloc)

    def get_relocs(self):
        return self.entries


class Symbol:
    def __init__(self, offset, name, file_name=None):
        self.offset = offset
        self.name = name
        self.file_name = file_name

    def get_offset(self):
        return self.offset

    def get_name(self):
        return self.name

    def get_file_name(self):
        return self.file_name


class SymbolTable:
    def __init__(self):
        self.symbols = []

    def add_symbol(self, symbol):
        self.symbols.append(symbol)

    def get_symbols(self):
        return self.symbols


class DebugLineEntry:
    def __init__(self, offset, src_line, flags=0):
        self.offset = offset
        self.src_line = src_line
        self.flags = flags
        self.file_ = None

    def get_offset(self):
        return self.offset

    def get_src_line(self):
        return self.src_line

    def get_flags(self):
        return self.flags

    def get_file(self):
        return self.file_


class DebugLineFile:
    def __init__(self, src_file, dir_name=None, base_offset=0):
        self.src_file = src_file
        self.dir_name = dir_name
        self.base_offset = base_offset
        self.entries = []

    def get_src_file(self):
        return self.src_file

    def get_dir_name(self):
        return self.dir_name

    def get_entries(self):
        return self.entries

    def get_base_offset(self):
        return self.base_offset

    def add_entry(self, e):
        self.entries.append(e)
        e.file_ = self


class DebugLine:
    def __init__(self):
        self.files = []

    def add_file(self, src_file):
        self.files.append(src_file)

    def get_files(self):
        return self.files


class Segment:
    def __init__(self, seg_type, size, data=None, flags=0):
        self.seg_type = seg_type
        self.size = size
        self.data = data
        self.flags = flags
        self.relocs = {}
        self.symtab = None
        self.id = None
        self.file_data = None
        self.debug_line = None

    def __str__(self):
        # relocs
        relocs = []
        for to_seg in self.relocs:
            r = self.relocs[to_seg]
            relocs.append("(#%d:size=%d)" % (to_seg.id, len(r.entries)))
        # symtab
        if self.symtab is not None:
            symtab = "symtab=#%d" % len(self.symtab.symbols)
        else:
            symtab = ""
        # debug_line
        if self.debug_line is not None:
            dl_files = self.debug_line.get_files()
            file_info = []
            for dl_file in dl_files:
                n = len(dl_file.entries)
                file_info.append("(%s:#%d)" % (dl_file.src_file, n))
            debug_line = "debug_line=" + ",".join(file_info)
        else:
            debug_line = ""
        # summary
        return "[#%d:%s:size=%d,flags=%d,%s,%s,%s]" % (
            self.id,
            segment_type_names[self.seg_type],
            self.size,
            self.flags,
            ",".join(relocs),
            symtab,
            debug_line,
        )

    def get_type(self):
        return self.seg_type

    def get_type_name(self):
        return segment_type_names[self.seg_type]

    def get_size(self):
        return self.size

    def get_data(self):
        return self.data

    def add_reloc(self, to_seg, relocs):
        self.relocs[to_seg] = relocs

    def get_reloc_to_segs(self):
        keys = list(self.relocs.keys())
        return sorted(keys, key=lambda x: x.id)

    def get_reloc(self, to_seg):
        if to_seg in self.relocs:
            return self.relocs[to_seg]
        else:
            return None

    def set_symtab(self, symtab):
        self.symtab = symtab

    def get_symtab(self):
        return self.symtab

    def set_debug_line(self, debug_line):
        self.debug_line = debug_line

    def get_debug_line(self):
        return self.debug_line

    def set_file_data(self, file_data):
        """set associated loaded binary file"""
        self.file_data = file_data

    def get_file_data(self):
        """get associated loaded binary file"""
        return self.file_data

    def find_symbol(self, offset):
        symtab = self.get_symtab()
        if symtab is None:
            return None
        for symbol in symtab.get_symbols():
            off = symbol.get_offset()
            if off == offset:
                return symbol.get_name()
        return None

    def find_reloc(self, offset, size):
        to_segs = self.get_reloc_to_segs()
        for to_seg in to_segs:
            reloc = self.get_reloc(to_seg)
            for r in reloc.get_relocs():
                off = r.get_offset()
                if off >= offset and off <= (offset + size):
                    return r, to_seg, off
        return None

    def find_debug_line(self, offset):
        debug_line = self.debug_line
        if debug_line is None:
            return None
        for df in debug_line.get_files():
            for e in df.get_entries():
                if e.get_offset() == offset:
                    return e
        return None


class BinImage:
    """A binary image contains all the segments of a program's binary image."""

    def __init__(self, file_type):
        self.segments = []
        self.file_data = None
        self.file_type = file_type

    def __str__(self):
        return "<%s>" % ",".join(map(str, self.segments))

    def get_size(self):
        total_size = 0
        for seg in self.segments:
            total_size += seg.get_size()
        return total_size

    def add_segment(self, seg):
        seg.id = len(self.segments)
        self.segments.append(seg)

    def get_segments(self):
        return self.segments

    def set_file_data(self, file_data):
        """set associated loaded binary file"""
        self.file_data = file_data

    def get_file_data(self):
        """get associated loaded binary file"""
        return self.file_data

    def get_segment_names(self):
        names = []
        for seg in self.segments:
            names.append(seg.get_type_name())
        return names
