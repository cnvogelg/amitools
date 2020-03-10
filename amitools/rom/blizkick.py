"""handle BlizKick modules."""

import struct
import amitools.binfmt.BinImage as BinImage

BKMODULE_ID = 0x707A4E75
BK_MODULE_ID = 0x4AFC
BK_PATCH_ID = 0x4E71


class BlizKickModule:
    """Work with a BlizKick binary image"""

    def __init__(self, bin_img):
        self.bin_img = bin_img
        self.bk_type = self._find_type()

    def _find_type(self):
        segs = self.bin_img.get_segments()
        if not segs:
            return None
        seg = segs[0]
        # assume not empty code segment
        if seg.get_type() != BinImage.SEGMENT_TYPE_CODE:
            return None
        data = seg.get_data()
        if data is None:
            return None
        num = len(data)
        if num < 8:
            return None
        # first 8 bytes contain bk header
        hdr = data[0:8]
        bk_magic, _, bk_type = struct.unpack(">IHH", hdr)
        if bk_magic != BKMODULE_ID:
            return None
        if bk_type == BK_MODULE_ID:
            return "module"
        elif bk_type == BK_PATCH_ID:
            return "patch"
        else:
            return None

    def get_type(self):
        """return type of module"""
        return self.bk_type

    def fix_module(self):
        """cleanup module and apply relocations"""
        if self.bk_type != "module":
            return
        segs = self.bin_img.get_segments()
        # strip bk module header
        seg = segs[0]
        data = seg.get_data()
        seg.data = data[6:]
        seg.size -= 6
        # auto init flag set?
        flags = ord(seg.data[10])
        auto_init = (flags & 0x80) == 0x80
        # add relocations to myself for the following offsets
        # see blizkick source: blizkickmodule.i for details
        offs = (2, 6, 14, 18, 22)
        if auto_init:
            offs += (34, 38, 42)
        # get relocs to myself (seg 0)
        relocs = seg.get_reloc(seg)
        if relocs is not None:
            raise ValueError("no relocations expected in BlizKick module")
        relocs = BinImage.Relocations(seg)
        seg.add_reloc(seg, relocs)
        # add relocs
        for o in offs:
            relocs.add_reloc(BinImage.Reloc(o))
        # check if we can remove last data segment (contains only version info)
        if len(segs) == 2 and segs[1].get_type() == BinImage.SEGMENT_TYPE_DATA:
            data = segs[1].get_data()
            if data[:5] == "$VER:":
                self.bin_img.segments = [seg]


# test
if __name__ == "__main__":
    import sys
    from amitools.binfmt.BinFmt import BinFmt

    bfmt = BinFmt()
    for f in sys.argv[1:]:
        if bfmt.is_image(f):
            my_bin_img = bfmt.load_image(f)
            print(my_bin_img)
            bkm = BlizKickModule(my_bin_img)
            print((bkm.bk_type))
            bkm.fix_module()
