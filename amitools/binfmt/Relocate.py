import struct
from .BinImage import BIN_IMAGE_RELOC_32, BIN_IMAGE_RELOC_PC32


class Relocate:
    """Relocate a BinImage to given addresses"""

    def __init__(self, bin_img, verbose=False):
        self.bin_img = bin_img
        self.verbose = verbose

    def get_sizes(self):
        """return a list of the required sizes for all sections"""
        sizes = []
        for segment in self.bin_img.get_segments():
            size = segment.size
            sizes.append(size)
        return sizes

    def get_total_size(self, padding=0):
        """return the total size of all segments appended. useful for one large blob"""
        sizes = self.get_sizes()
        total = 0
        for s in sizes:
            total += s + padding
        return total

    def get_seq_addrs(self, base_addr, padding=0):
        """generate a sequence of addresses for continous segments in one blob"""
        sizes = self.get_sizes()
        addrs = []
        addr = base_addr
        for s in sizes:
            addrs.append(addr)
            addr += s + padding
        return addrs

    def relocate_one_block(self, base_addr, padding=0):
        total_size = self.get_total_size(padding)
        data = bytearray(total_size)
        addrs = self.get_seq_addrs(base_addr, padding)
        offset = 0
        segs = self.bin_img.get_segments()
        for segment in segs:
            self._copy_data(data, segment, offset)
            self._reloc_data(data, segment, addrs, offset)
            offset += segment.size + padding
        return data

    def relocate(self, addrs, in_data=None):
        """perform relocations on segments and return relocated data"""
        segs = self.bin_img.get_segments()
        if len(segs) != len(addrs):
            raise ValueError("addrs != segments")
        datas = []
        for segment in segs:
            # allocate new buffer
            data = bytearray(segment.size)
            self._copy_data(data, segment)
            self._reloc_data(data, segment, addrs)
            datas.append(data)
        return datas

    def _copy_data(self, data, segment, offset=0):
        # allocate segment data
        size = segment.size
        src_data = segment.data
        if src_data is not None:
            src_len = len(src_data)
            data[offset : src_len + offset] = src_data

        if self.verbose:
            print("#%02d @%06x +%06x" % (segment.id, addrs[segment.id], size))

    def _reloc_data(self, data, segment, addrs, offset=0):
        # find relocations
        to_segs = segment.get_reloc_to_segs()
        my_addr = addrs[segment.id]
        for to_seg in to_segs:
            # get target segment's address
            to_id = to_seg.id
            to_addr = addrs[to_id]
            # get relocations
            reloc = segment.get_reloc(to_seg)
            for r in reloc.get_relocs():
                self._reloc(segment.id, data, r, my_addr, to_addr, to_id, offset)

    def _reloc(self, my_id, data, reloc, my_addr, to_addr, to_id, extra_offset):
        """relocate one entry"""
        offset = reloc.get_offset() + extra_offset
        delta = self._read_long(data, offset) + reloc.addend
        if reloc.get_type() == BIN_IMAGE_RELOC_32:
            addr = to_addr + delta
        elif reloc.get_type() == BIN_IMAGE_RELOC_PC32:
            addr = delta + to_addr - my_addr - offset
        else:
            raise (Exception("unsupported type %d" % reloc.get_type()))
        self._write_long(data, offset, addr)
        if self.verbose:
            print(
                "#%02d + %06x: %06x (delta) + @%06x (#%02d) -> %06x"
                % (my_id, offset, delta, to_addr, to_id, addr)
            )

    def _read_long(self, data, offset):
        d = data[offset : offset + 4]
        return struct.unpack(">i", d)[0]

    def _write_long(self, data, offset, value):
        d = struct.pack(">i", value)
        data[offset : offset + 4] = d


# mini test
if __name__ == "__main__":
    import sys
    from .BinFmt import BinFmt

    bf = BinFmt()
    for a in sys.argv[1:]:
        bi = bf.load_image(a)
        if bi is not None:
            print(a)
            r = Relocate(bi, True)
            addrs = r.get_seq_addrs(0)
            datas = r.relocate(addrs)
            data = r.relocate_one_block(0)
