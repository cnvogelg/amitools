from .BinImage import *
import amitools.util.HexDump as HexDump


class Dumper:
    def __init__(self, bin_img):
        self.bin_img = bin_img

    def dump(
        self,
        hex_dump=False,
        show_reloc=False,
        show_symbols=False,
        show_debug_line=False,
    ):
        for seg in self.bin_img.get_segments():
            seg_type = seg.seg_type
            seg_type_name = segment_type_names[seg_type]
            size = seg.size
            print("#%02d  %04s  %08x/%10d" % (seg.id, seg_type_name, size, size))
            # show hex dump?
            data = seg.data
            if data is not None and hex_dump:
                HexDump.print_hex(data, 4)
            # show reloc
            if show_reloc:
                to_segs = seg.get_reloc_to_segs()
                for to_seg in to_segs:
                    print("  RELOC to #%02d" % (to_seg.id))
                    reloc = seg.get_reloc(to_seg)
                    for r in reloc.get_relocs():
                        off = r.get_offset()
                        add = r.get_addend()
                        print("    %08x/%10d    +%08x/%10d" % (off, off, add, add))
            # show symbols
            if show_symbols:
                symtab = seg.get_symtab()
                if symtab is not None:
                    print("  SYMBOLS")
                    for sym in symtab.get_symbols():
                        off = sym.get_offset()
                        name = sym.get_name()
                        print("    %08x/%10d    %s" % (off, off, name))
            # show debug info
            if show_debug_line:
                debug_line = seg.get_debug_line()
                if debug_line is not None:
                    print("  DEBUG LINE")
                    for f in debug_line.get_files():
                        print(
                            "    FILE: [%s] %s" % (f.get_dir_name(), f.get_src_file())
                        )
                        for e in f.get_entries():
                            print("      %08x  %d" % (e.get_offset(), e.get_src_line()))


# mini test
if __name__ == "__main__":
    import sys
    from .BinFmt import BinFmt

    bf = BinFmt()
    for a in sys.argv[1:]:
        bi = bf.load_image(a)
        if bi is not None:
            print(a)
            d = Dumper(bi)
            d.dump(True, True, True, True)
