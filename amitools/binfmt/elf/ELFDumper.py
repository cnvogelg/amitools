from .ELF import *


class ELFDumper:
    def __init__(self, elf_file):
        self.elf = elf_file

    def _dump_rela_entry(self, rel, prefix="\t\t\t"):
        rel_sect = rel.section
        sect_txt = "%s (%d) + %d" % (
            rel_sect.name_str,
            rel_sect.idx,
            rel.section_addend,
        )
        rel_symbol = rel.symbol
        if rel_symbol is not None:
            sym_txt = "%s (%d) + %d" % (rel_symbol.name_str, rel_symbol.idx, rel.addend)
        else:
            sym_txt = ""
        print(
            "%s%08x  %-10s  %-20s  %s"
            % (prefix, rel.offset, rel.type_str, sect_txt, sym_txt)
        )

    def _dump_symbol(self, sym):
        print(
            "\t\t\t%08x  %6d  %-8s  %-8s  %-16s"
            % (sym.value, sym.size, sym.type_str, sym.bind_str, sym.name_str)
        )

    def dump_sections(self, show_relocs=False, show_debug=False):
        print("ELF Sections")
        print("id  name             size      rela  syms  type       flags")
        for sect in self.elf.sections:

            # determine number of relocations
            rela = sect.get_rela()
            num_rela = len(rela)

            # determine number of symbols
            symbols = sect.get_symbols()
            num_syms = len(symbols)

            print(
                "%2d  %-16s %08x  %4d  %4d  %-10s %s"
                % (
                    sect.idx,
                    sect.name_str,
                    sect.header.size,
                    num_rela,
                    num_syms,
                    sect.header.type_str,
                    ",".join(sect.header.flags_dec),
                )
            )

            # show relas
            if show_relocs and num_rela > 0:
                print("\t\tRelocations:")
                for rel in rela:
                    self._dump_rela_entry(rel)

                # per segment relocations
                for tgt_sect in sect.get_rela_sections():
                    print("\t\tTo Section #%d:" % tgt_sect.idx)
                    for rel in sect.get_rela_by_section(tgt_sect):
                        self._dump_rela_entry(rel)

            # show symbols
            if show_debug and num_syms > 0:
                print("\t\tSymbols:")
                for sym in symbols:
                    self._dump_symbol(sym)

    def dump_symbols(self):
        print("ELF Symbol Table")
        symtabs = self.elf.symtabs
        if len(symtabs) == 0:
            print("no symbols")
            return

        print(
            "idx   value     size    type      bind      visible   ndx              name"
        )
        for symtab in symtabs:
            for sym in symtab.get_table_symbols():
                txt = sym.shndx_str
                if txt is None:
                    txt = sym.section.name_str
                print(
                    "%4d  %08x  %6d  %-8s  %-8s  %-8s  %-16s  %s"
                    % (
                        sym.idx,
                        sym.value,
                        sym.size,
                        sym.type_str,
                        sym.bind_str,
                        sym.visibility_str,
                        txt,
                        sym.name_str,
                    )
                )

    def dump_relas(self):
        print("ELF Relocations")
        rela_sects = self.elf.relas
        if len(rela_sects) == 0:
            print("no relocations")
            return

        for rela_sect in rela_sects:
            print(rela_sect.name_str, "linked to", rela_sect.reloc_section.name_str)
            print("      offset    type        segment + addend      symbol + addend")
            num = 0
            for rela in rela_sect.get_relocations():
                self._dump_rela_entry(rela, prefix="%4d  " % num)
                num += 1

    def dump_relas_by_sect(self):
        print("ELF Relocations (by sections)")
        for sect in self.elf.sections:
            to_sects = sect.get_rela_sections()
            if len(to_sects) > 0:
                print("  section", sect.idx)
                for to_sect in to_sects:
                    print("    -> section", to_sect.idx)
                    num = 0
                    for rela in sect.get_rela_by_section(to_sect):
                        self._dump_rela_entry(rela, prefix="      %4d  " % num)
                        num += 1


if __name__ == "__main__":
    from .ELFReader import ELFReader
    import sys

    reader = ELFReader()
    for a in sys.argv[1:]:
        f = open(a, "rb")
        ef = reader.load(f)
        dumper = ELFDumper(ef)
        dumper.dump_sections(True, True)
        dumper.dump_symbols()
        dumper.dump_relas()
        dumper.dump_relas_by_sect()
