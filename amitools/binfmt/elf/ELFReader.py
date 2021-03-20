"""A class for reading and writing ELF format binaries (esp. Amiga m68k ones)"""

import os
from .ELF import *
from .ELFFile import *


class ELFReader:
    def _load_section_headers(self, f, ef):
        shoff = ef.header.shoff
        shentsize = ef.header.shentsize
        f.seek(shoff, os.SEEK_SET)
        shnum = ef.header.shnum
        for i in range(shnum):
            sh = ELFSectionHeader()
            sh_data = f.read(shentsize)
            sh.parse(sh_data)
            ef.section_hdrs.append(sh)

    def _load_sections(self, f, ef):
        sect_hdrs = ef.section_hdrs
        idx = 0
        for sect_hdr in sect_hdrs:
            idx += 1
            sect = self._load_section(f, sect_hdr, idx)
            ef.sections.append(sect)
            if sect_hdr.type_ == SHT_NOBITS:
                ef.bss = sect

    def _load_section(self, f, sect_hdr, idx):
        t = sect_hdr.type_
        size = sect_hdr.size
        if t == SHT_NOBITS or size == 0:
            sect = ELFSection(sect_hdr, idx)
        else:
            # read data
            offset = sect_hdr.offset
            f.seek(offset, os.SEEK_SET)
            data = f.read(size)
            # decode?
            if t == SHT_STRTAB:
                sect = ELFSectionStringTable(sect_hdr, idx, data)
                sect.decode()
            elif t == SHT_SYMTAB:
                sect = ELFSectionSymbolTable(sect_hdr, idx, data)
                sect.decode()
            elif t == SHT_RELA:
                sect = ELFSectionRelocationsWithAddend(sect_hdr, idx, data)
                sect.decode()
            else:
                sect = ELFSectionWithData(sect_hdr, idx, data)

        return sect

    def _name_section(self, section, strtab):
        off = section.header.name
        section.name_str = strtab.get_string(off)

    def _resolve_symtab_names(self, sect, sections):
        # get linked string table
        strtab_seg_num = sect.header.link
        if strtab_seg_num < 1 or strtab_seg_num >= len(sections):
            raise ELFParseError("Invalid strtab for symtab: " + strtab_seg_num)
        strtab = sections[strtab_seg_num]
        if strtab.__class__ != ELFSectionStringTable:
            raise ELFParseError("Invalid strtab segment for symtab")
        # resolve all symbol names
        for sym in sect.symtab:
            sym.name_str = strtab.get_string(sym.name)

    def _resolve_symtab_indices(self, sect, ef, sections):
        for sym in sect.symtab:
            if sym.shndx_str == None:
                # refers a valid section
                idx = sym.shndx
                if idx == 65522:  # common
                    sym.section = ef.bss
                    sym.value = ef.bss.header.size
                    ef.bss.header.size += sym.size + 3 & ~3
                else:
                    sym.section = sections[idx]

    def _assign_symbols_to_sections(self, sect):
        src_file_sym = None
        all_symbols = []
        for sym in sect.symtab:
            sym_type = sym.type_str
            if sym_type == "FILE":
                # store file symbol for following symbols
                src_file_sym = sym
            elif sym_type in ("OBJECT", "FUNC", "NOTYPE"):
                # add containing file symbol and its name
                if src_file_sym != None:
                    sym.file_sym = src_file_sym
                else:
                    sym.file_sym = None
                # add symbol to segment
                sym_sect = sym.section
                if sym_sect is not None:
                    sym_sect.symbols.append(sym)
                    # list of all symbols assigned
                    all_symbols.append(sym_sect.symbols)
        # now sort all symbol lists
        for symbols in all_symbols:
            symbols.sort(key=lambda x: x.value)

    def _resolve_rela_links(self, sect, sections):
        link = sect.header.link
        info = sect.header.info
        num_sects = len(sections)
        if link == 0 or link >= num_sects:
            raise ELFParseError("Invalid rela link!")
        if info == 0 or info >= num_sects:
            raise ELFParseError("Invalid rela info!")

        # info_seg -> src segment we will apply rela on
        src_sect = sections[info]
        sect.reloc_section = src_sect

        # link_seg -> symbol table
        sect.symtab = sections[link]

        # store link in segment for this relocation
        src_sect.relocations = sect

        # a map for rela by tgt segment
        by_sect = {}
        src_sect.reloc_by_sect = by_sect

        # now process all rela entries
        symtab = sect.symtab
        for entry in sect.rela:
            # look up symbol of rela entry
            sym_idx = entry.sym
            sym = symtab.get_symbol(sym_idx)
            entry.symbol = sym
            # copy section we relocate from
            entry.section = sym.section
            # calc addend in segment
            entry.section_addend = entry.addend + sym.value

            # clear symbol if its empty
            if sym.name_str == "":
                entry.symbol = None

            # add entry to section list
            tgt_sect = entry.section
            if tgt_sect in by_sect:
                by_sect_list = by_sect[tgt_sect]
            else:
                by_sect_list = []
                by_sect[tgt_sect] = by_sect_list
            by_sect_list.append(entry)

        # sort all by_seg entries
        for sect in by_sect:
            by_sect_list = by_sect[sect]
            by_sect_list.sort(key=lambda x: x.offset)

    def load(self, f):
        """load an ELF file from the given file object f
        and return an ELFFile instance or None if loading failed"""

        ef = ELFFile()

        # read identifier
        ident = ELFIdentifier()
        ident_data = f.read(16)
        ident.parse(ident_data)
        ef.identifier = ident

        # read header
        hdr = ELFHeader()
        hdr_data = f.read(36)
        hdr.parse(hdr_data)
        ef.header = hdr

        # expect a non-empty section header
        if hdr.shnum == 0:
            raise ELFParseError("No segment header defined!")

        # load all section headers
        self._load_section_headers(f, ef)

        # load and decode sections
        self._load_sections(f, ef)

        # get string table with segment names
        strtab_idx = ef.header.shstrndx
        strtab = ef.sections[strtab_idx]
        if strtab.__class__ != ELFSectionStringTable:
            raise ELFParseError("No strtab for segment header found! ")

        # process sections
        for sect in ef.sections:
            # name all sections by using the string table
            self._name_section(sect, strtab)
            # resolve symbol table names
            if sect.header.type_ == SHT_SYMTAB:
                # store in file symtabs
                ef.symtabs.append(sect)
                # get names in symtab
                self._resolve_symtab_names(sect, ef.sections)
                # link sections to symbols
                self._resolve_symtab_indices(sect, ef, ef.sections)
                # assign symbols to sections
                self._assign_symbols_to_sections(sect)

        # resolve rela links and symbols
        for sect in ef.sections:
            if sect.header.type_ == SHT_RELA:
                self._resolve_rela_links(sect, ef.sections)
                ef.relas.append(sect)

        return ef


# mini test
if __name__ == "__main__":
    import sys

    reader = ELFReader()
    for a in sys.argv[1:]:
        f = open(a, "rb")
        ef = reader.load(f)
