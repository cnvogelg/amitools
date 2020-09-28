import ctypes
import struct
from . import Hunk


class HunkRelocate:
    def __init__(self, hunk_file, verbose=False):
        self.hunk_file = hunk_file
        self.verbose = verbose

    def get_sizes(self):
        sizes = []
        for segment in self.hunk_file.segments:
            main_hunk = segment[0]
            size = main_hunk["alloc_size"]
            sizes.append(size)
        return sizes

    def get_total_size(self):
        sizes = self.get_sizes()
        total = 0
        for s in sizes:
            total += s
        return total

    def get_type_names(self):
        names = []
        for segment in self.hunk_file.segments:
            main_hunk = segment[0]
            name = main_hunk["type_name"]
            names.append(name)
        return names

    # generate a sequence of addresses suitable for relocation
    # in a single block
    def get_seq_addrs(self, base_addr, padding=0):
        sizes = self.get_sizes()
        addrs = []
        addr = base_addr
        for s in sizes:
            addrs.append(addr)
            addr += s + padding
        return addrs

    def relocate(self, addr):
        datas = []
        for segment in self.hunk_file.segments:
            main_hunk = segment[0]
            hunk_no = main_hunk["hunk_no"]
            alloc_size = main_hunk["alloc_size"]
            size = main_hunk["size"]
            data = ctypes.create_string_buffer(alloc_size)

            # fill in segment data
            if "data" in main_hunk:
                data.value = main_hunk["data"]

            if self.verbose:
                print("#%02d @ %06x" % (hunk_no, addr[hunk_no]))

            # find relocation hunks
            for hunk in segment[1:]:
                # abs reloc 32 or
                # HUNK_DREL32 is a buggy V37 HUNK_RELOC32SHORT...
                if (
                    hunk["type"] == Hunk.HUNK_ABSRELOC32
                    or hunk["type"] == Hunk.HUNK_DREL32
                ):
                    reloc = hunk["reloc"]
                    for hunk_num in reloc:
                        # get address of other hunk
                        hunk_addr = addr[hunk_num]
                        offsets = reloc[hunk_num]
                        for offset in offsets:
                            self.relocate32(hunk_no, data, offset, hunk_addr)

            datas.append(data.raw)
        return datas

    def relocate32(self, hunk_no, data, offset, hunk_addr):
        delta = self.read_long(data, offset)
        addr = hunk_addr + delta
        self.write_long(data, offset, addr)
        if self.verbose:
            print(
                "#%02d + %06x: %06x (delta) + %06x (hunk_addr) -> %06x"
                % (hunk_no, offset, delta, hunk_addr, addr)
            )

    def read_long(self, data, offset):
        bytes = data[offset : offset + 4]
        return struct.unpack(">i", bytes)[0]

    def write_long(self, data, offset, value):
        bytes = struct.pack(">i", value)
        data[offset : offset + 4] = bytes
