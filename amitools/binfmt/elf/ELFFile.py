import struct
from .ELF import *


class ELFParseError(Exception):
    def __init__(self, msg):
        self.msg = msg


class ELFPart:
    """base class for parts of ELF file"""

    _names = []

    def __init__(self):
        for name in self._names:
            setattr(self, name, None)

    def _parse_data(self, fmt, data):
        flen = len(fmt)
        nlen = len(self._names)
        if flen != nlen:
            raise ValueError("_parse_data size mismatch")
        decoded = struct.unpack(">" + fmt, data)
        if len(decoded) != nlen:
            raise ELFParseError("data decode error")
        for i in range(nlen):
            setattr(self, self._names[i], decoded[i])

    def _decode_flags(self, value, names):
        result = []
        for mask in names:
            if mask & value == mask:
                result.append(names[mask])
        return result

    def _decode_value(self, value, names):
        if value in names:
            return names[value]
        else:
            return None


class ELFIdentifier(ELFPart):
    _names = ["class_", "data", "version", "osabi", "abiversion"]

    def __init__(self):
        ELFPart.__init__(self)

    def parse(self, ident_data):
        # magic
        magic = ident_data[0:4]
        if magic != b"\177ELF":
            raise ELFParseError("No ELF Magic found!")
        self.class_ = ident_data[4]
        self.data = ident_data[5]
        self.version = ident_data[6]
        self.osabi = ident_data[7]
        self.abiversion = ident_data[8]


class ELFHeader(ELFPart):
    _names = [
        "type_",
        "machine",
        "version",
        "entry",
        "phoff",
        "shoff",
        "flags",
        "ehsize",
        "phentsize",
        "phnum",
        "shentsize",
        "shnum",
        "shstrndx",
    ]

    def __init__(self):
        ELFPart.__init__(self)

    def parse(self, data):
        fmt = "HHIIIIIHHHHHH"
        self._parse_data(fmt, data)
        self.type_str = self._decode_value(self.type_, ET_values)


class ELFSectionHeader(ELFPart):
    _names = [
        "name",
        "type_",
        "flags",
        "addr",
        "offset",
        "size",
        "link",
        "info",
        "addralign",
        "entsize",
    ]

    def __init__(self):
        ELFPart.__init__(self)

    def parse(self, data):
        fmt = "IIIIIIIIII"
        self._parse_data(fmt, data)
        self.flags_dec = self._decode_flags(self.flags, SHT_flags)
        self.type_str = self._decode_value(self.type_, SHT_values)


# ----- Sections -----


class ELFSection:
    def __init__(self, header, idx):
        self.header = header
        self.idx = idx
        self.data = None
        # resolved data
        self.name_str = None
        self.symbols = []
        self.relocations = None
        self.reloc_by_sect = {}
        self.bss = None

    def get_rela(self):
        """return a list with all relocations"""
        if self.relocations is not None:
            return self.relocations.rela
        else:
            return []

    def get_rela_by_section(self, sect):
        """return a list of relocations from the given section"""
        if sect in self.reloc_by_sect:
            return self.reloc_by_sect[sect]
        else:
            return []

    def get_rela_sections(self):
        return sorted(list(self.reloc_by_sect.keys()), key=lambda x: x.idx)

    def get_symbols(self):
        return self.symbols


class ELFSectionWithData(ELFSection):
    def __init__(self, header, index, data):
        ELFSection.__init__(self, header, index)
        self.data = data


class ELFSectionStringTable(ELFSectionWithData):
    def __init__(self, header, index, data):
        ELFSectionWithData.__init__(self, header, index, data)
        self.strtab = None

    def decode(self):
        l = len(self.data)
        o = 0
        strtab = []
        while o < l:
            n = self.data.find(b"\0", o)
            if n == -1:
                raise ELFParseError("Invalid strtab!")
            if n > 0:
                s = self.data[o:n]
            else:
                s = ""
            strtab.append((o, s))
            o = n + 1
        self.strtab = strtab

    def get_string(self, off):
        old = (0, "")
        for e in self.strtab:
            if off < e[0]:
                delta = off - old[0]
                return old[1][delta:]
            old = e
        delta = off - self.strtab[-1][0]
        return self.strtab[-1][1][delta:]


class ELFSymbol(ELFPart):
    _names = ["name", "value", "size", "info", "other", "shndx"]

    def __init__(self, idx):
        ELFPart.__init__(self)
        self.idx = idx
        self.bind = None
        self.type_ = None
        self.visibility = None
        # will be resolved
        self.name_str = None
        self.section = None

    def parse(self, data):
        fmt = "IIIBBH"
        self._parse_data(fmt, data)
        # decode sub values
        self.bind = self.info >> 4
        self.type_ = self.info & 0xF
        self.visibility = self.other & 3
        # string values
        self.bind_str = self._decode_value(self.bind, STB_values)
        self.type_str = self._decode_value(self.type_, STT_values)
        self.visibility_str = self._decode_value(self.visibility, STV_values)
        self.shndx_str = self._decode_value(self.shndx, SHN_values)


class ELFSectionSymbolTable(ELFSectionWithData):
    def __init__(self, header, index, data):
        ELFSectionWithData.__init__(self, header, index, data)
        self.symtab = []

    def decode(self):
        entsize = self.header.entsize
        num = self.header.size // entsize
        symtab = []
        self.symtab = symtab
        off = 0
        idx = 0
        for n in range(num):
            entry = ELFSymbol(idx)
            entry_data = self.data[off : off + entsize]
            entry.parse(entry_data)
            symtab.append(entry)
            off += entsize
            idx += 1
        return True

    def get_symbol(self, idx):
        return self.symtab[idx]

    def get_table_symbols(self):
        return self.symtab


class ELFRelocationWithAddend(ELFPart):
    _names = ["offset", "info", "addend"]

    def __init__(self):
        ELFPart.__init__(self)
        self.sym = None
        self.type_ = None
        self.type_str = None
        self.symbol = None

    def parse(self, data):
        fmt = "IIi"
        self._parse_data(fmt, data)
        # decode sym and type
        self.sym = self.info >> 8
        self.type_ = self.info & 0xFF
        self.type_str = self._decode_value(self.type_, R_68K_values)


class ELFSectionRelocationsWithAddend(ELFSectionWithData):
    def __init__(self, header, index, data):
        ELFSectionWithData.__init__(self, header, index, data)
        self.rela = []
        self.symtab = None
        self.reloc_section = None

    def decode(self):
        entsize = self.header.entsize
        num = self.header.size // entsize
        rela = []
        self.rela = rela
        off = 0
        for n in range(num):
            entry = ELFRelocationWithAddend()
            entry_data = self.data[off : off + entsize]
            entry.parse(entry_data)
            rela.append(entry)
            off += entsize

    def get_relocations(self):
        return self.rela


class ELFFile:
    def __init__(self):
        self.identifier = None
        self.header = None
        self.section_hdrs = []
        self.sections = []
        self.symtabs = []
        self.relas = []

    def get_section_by_name(self, name):
        for sect in self.sections:
            if sect.name_str == name:
                return sect
        return None
