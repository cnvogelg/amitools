from amitools.binfmt.BinImage import (
    BIN_IMAGE_TYPE_ELF,
    SEGMENT_TYPE_CODE,
    SEGMENT_TYPE_DATA,
    SEGMENT_FLAG_READ_ONLY,
    SEGMENT_TYPE_BSS,
    Segment,
    Relocations,
    SymbolTable,
    Symbol,
    Reloc,
    DebugLine,
    DebugLineFile,
    DebugLineEntry,
    BinImage,
)
from .ELFFile import ELFIdentifier, ELFHeader, ELFParseError
from .ELF import EM_68K, ELFOSABI_AROS, ELFOSABI_SYSV
from .ELFReader import ELFReader
from .DwarfDebugLine import DwarfDebugLine


class BinFmtELF:
    """Handle Amiga m68k binaries in ELF format (usually from AROS)"""

    def is_image(self, path):
        """check if a given file is a supported ELF file"""
        with open(path, "rb") as f:
            return self.is_image_fobj(f)

    def is_image_fobj(self, fobj):
        """check if a given fobj is a supported ELF file"""
        try:
            pos = fobj.tell()

            # read identifier
            ident = ELFIdentifier()
            ident_data = fobj.read(16)
            ident.parse(ident_data)

            # read header
            hdr = ELFHeader()
            hdr_data = fobj.read(36)
            hdr.parse(hdr_data)

            # seek back
            fobj.seek(pos, 0)

            # check header
            return self.is_supported_elf(ident, hdr)
        except ELFParseError:
            return False

    def is_supported_elf(self, ident, hdr):
        """check ELF header if its a m68k binary"""
        if hdr.machine != EM_68K:
            return False
        if ident.osabi not in (ELFOSABI_SYSV, ELFOSABI_AROS):
            return False
        return True

    def load_image(self, path):
        """load a BinImage from an ELF file given via path"""
        with open(path, "rb") as f:
            return self.load_image_fobj(f)

    def load_image_fobj(self, fobj):
        """load a BinImage from an ELF file given via file object"""
        # read elf file
        reader = ELFReader()
        elf = reader.load(fobj)
        # create bin image and assign elf file
        bi = BinImage(BIN_IMAGE_TYPE_ELF)
        bi.set_file_data(elf)
        # walk through elf sections
        sect_to_seg = {}
        for sect in elf.sections:
            if sect.header.type_ == 0 or sect.header.type_ == 4:
                continue
            # determine segment type
            seg_type = None
            name = sect.name_str
            flags = 0
            if name.startswith(b".text"):
                seg_type = SEGMENT_TYPE_CODE
            elif name == b".bss":
                seg_type = SEGMENT_TYPE_BSS
            else:
                seg_type = SEGMENT_TYPE_DATA
            # we got a segment
            if seg_type is not None:
                size = sect.header.size
                data = sect.data
                seg = Segment(seg_type, size, data, flags)
                bi.add_segment(seg)
                # assign section to segment
                seg.set_file_data(sect)
                sect_to_seg[sect] = seg

        # now run through segments to add relocations
        bi_segs = bi.get_segments()
        for seg in bi_segs:
            # retrieve associated ELF section
            sect = seg.get_file_data()

            # any relocations?
            rela = sect.get_rela()
            num_rela = len(rela)
            if num_rela > 0:
                self.add_elf_rela(sect, seg, sect_to_seg)

            # any symbols?
            symbols = sect.get_symbols()
            num_syms = len(symbols)
            if num_syms > 0:
                self.add_elf_symbols(symbols, seg)

        # try to add debug info
        ddl = DwarfDebugLine()
        got = ddl.decode(elf)
        if got:
            self.add_debug_line(ddl, bi, sect_to_seg)

        return bi

    def add_elf_rela(self, sect, seg, sect_to_seg):
        for tgt_sect in sect.get_rela_sections():
            # is this a relocation to a used section?
            if tgt_sect in sect_to_seg:
                to_seg = sect_to_seg[tgt_sect]
                rl = Relocations(to_seg)
                seg.add_reloc(to_seg, rl)
                # add relocations
                for rel in sect.get_rela_by_section(tgt_sect):
                    r = Reloc(rel.offset, rel.type_, addend=rel.section_addend)
                    rl.add_reloc(r)

    def add_elf_symbols(self, symbols, seg):
        symtab = SymbolTable()
        seg.set_symtab(symtab)
        for sym in symbols:
            # add entry
            off = sym.value
            name = sym.name_str
            file_sym = sym.file_sym
            if file_sym is not None:
                file_name = file_sym.name_str
            else:
                file_name = None
            symbol = Symbol(off, name, file_name)
            symtab.add_symbol(symbol)

    def add_debug_line(self, ddl, bi, sect_to_seg):
        seg_to_dl = {}
        matrix = ddl.get_matrix()
        for row in matrix:
            sect = row.section
            if sect in sect_to_seg:
                segment = sect_to_seg[sect]

                # fetch debug info
                if segment in seg_to_dl:
                    dl, file_to_df = seg_to_dl[segment]
                else:
                    dl = DebugLine()
                    file_to_df = {}
                    segment.set_debug_line(dl)
                    seg_to_dl[segment] = (dl, file_to_df)

                # fetch file instance
                fid = row.file
                if fid in file_to_df:
                    df = file_to_df[fid]
                else:
                    df = DebugLineFile(ddl.get_file_name(fid), ddl.get_file_dir(fid))
                    dl.add_file(df)
                    file_to_df[fid] = df

                # add entry
                e = DebugLineEntry(row.address, row.line)
                df.add_entry(e)


# mini test
if __name__ == "__main__":
    import sys

    bf = BinFmtELF()
    for a in sys.argv[1:]:
        if bf.is_image(a):
            print("loading", a)
            bi = bf.load_image(a)
            print(bi)
        else:
            print("NO ELF:", a)
