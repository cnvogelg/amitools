from amitools.vamos.machine import DisAsm
from .BinImage import *


class Disassemble:
    """allows to disassemble code segments of a BinImage"""

    def __init__(self, cpu="68000"):
        self.disasm = DisAsm.create(cpu)

    def _get_line_info(self, segment, addr, size):
        infos = []
        # info about src line
        d = segment.find_debug_line(addr)
        if d is not None:
            f = d.get_file()
            infos.append(
                "src %10s:%d  [%s]"
                % (f.get_src_file(), d.get_src_line(), f.get_dir_name())
            )
        # info about relocation
        r = segment.find_reloc(addr, size)
        if r is not None:
            delta = r[2] - addr
            infos.append("reloc +%02d: (#%02d + %08x)" % (delta, r[1].id, r[0].addend))
        return infos

    def disassemble(self, segment, bin_img):
        # make sure its a code segment
        if segment.seg_type != SEGMENT_TYPE_CODE:
            return None

        # generate raw assembly
        data = segment.data
        lines = self.disasm.disassemble_block(data)

        # process lines
        result = []
        for l in lines:
            addr = l[0]
            word = l[1]
            code = l[2]

            # try to find a symbol for this addr
            symbol = segment.find_symbol(addr)
            if symbol is not None:
                line = "\t\t\t\t%s:" % symbol
                result.append(line)

            # create final line
            line = "%08x\t%-20s\t%-30s  " % (
                addr,
                " ".join(["%04x" % x for x in word]),
                code,
            )

            # create line info
            size = len(word) * 2
            info = self._get_line_info(segment, addr, size)
            if info is None or len(info) == 0:
                result.append(line)
            else:
                result.append(line + "; " + info[0])
                spc = " " * len(line)
                for i in info[1:]:
                    result.append(spc + "; " + i)

        return result


# mini test
if __name__ == "__main__":
    import sys
    from .BinFmt import BinFmt

    bf = BinFmt()
    for a in sys.argv[1:]:
        bi = bf.load_image(a)
        if bi is not None:
            print(a)
            d = Disassemble()
            for seg in bi.get_segments():
                if seg.seg_type == SEGMENT_TYPE_CODE:
                    lines = d.disassemble(seg, bi)
                    for l in lines:
                        print(l)
