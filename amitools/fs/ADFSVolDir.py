from .ADFSDir import ADFSDir
from .MetaInfo import MetaInfo
from . import DosType


class ADFSVolDir(ADFSDir):
    def __init__(self, volume, root_block):
        ADFSDir.__init__(self, volume, None)
        self.set_block(root_block)
        self._init_name_hash()

    def __repr__(self):
        return "[VolDir(%d)'%s':%s]" % (
            self.block.blk_num,
            self.block.name,
            self.entries,
        )

    def draw_on_bitmap(self, bm, show_all=False, first=True):
        blk_num = self.block.blk_num
        bm[blk_num] = "V"
        if show_all or first:
            self.ensure_entries()
            for e in self.entries:
                e.draw_on_bitmap(bm, show_all, False)

    def get_size_str(self):
        return "VOLUME"

    def create_meta_info(self):
        self.meta_info = MetaInfo(mod_ts=self.block.mod_ts)

    def can_delete(self):
        return False

    def get_list_str(self, indent=0, all=False, detail=False):
        a = ADFSDir.get_list_str(self, indent=indent, all=all, detail=detail)
        a += DosType.get_dos_type_str(self.volume.get_dos_type())
        a += " #%d" % self.block_bytes
        return a
