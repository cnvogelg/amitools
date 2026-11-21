from .ADFSNode import ADFSNode
from .block.Block import Block
from .block.UserDirBlock import UserDirBlock
from .FSError import FSError, INVALID_USER_DIR_BLOCK


class ADFSHardLinkDir(ADFSNode):
    """a hard link to a directory (``ST_LINKDIR``) on an ADFS volume.

    It is stored as its own directory block: its ``real_entry`` points at the
    directory it names and its ``next_link`` chains the links of that
    directory. A lookup follows the link to the real directory, so a foreign
    disk that holds one lists and reads it. Creating one is refused (AmigaDOS
    does not let ``MakeLink`` link a directory, and following a link chain
    could recurse), so this node is read-only.
    """

    def __init__(self, volume, parent):
        ADFSNode.__init__(self, volume, parent)
        self.real_entry = 0
        self.real_node = None
        self.valid = False

    def __repr__(self):
        return "[HardLinkDir(%d)'%s'->%d]" % (
            self.block.blk_num,
            self.block.name,
            self.real_entry,
        )

    def blocks_create_old(self, anon_blk):
        # create the link's directory block
        ud = UserDirBlock(
            self.blkdev,
            anon_blk.blk_num,
            self.volume.is_longname,
            sub_type=Block.ST_LINKDIR,
        )
        ud.set(anon_blk.data)
        if not ud.valid:
            raise FSError(INVALID_USER_DIR_BLOCK, block=anon_blk)
        self.set_block(ud)
        self.real_entry = ud.real_entry
        self.real_node = self._read_real_node()
        self.valid = True
        return ud

    def _read_real_node(self):
        """read the directory the link names, as an :class:`ADFSDir`"""
        # imported here: ADFSDir imports this module for the lookup
        from .ADFSDir import ADFSDir

        blk_num = self.real_entry
        if not self.blkdev.reserved <= blk_num < self.blkdev.num_blocks:
            raise FSError(
                INVALID_USER_DIR_BLOCK, node=self, extra="real entry off the disk"
            )
        blk = Block(self.blkdev, blk_num)
        blk.read()
        if not blk.valid:
            raise FSError(INVALID_USER_DIR_BLOCK, block=blk)
        real = ADFSDir(self.volume, self.parent)
        real.blocks_create_old(blk)
        return real

    def get_real_node(self):
        return self.real_node

    def is_file(self):
        return False

    def is_dir(self):
        return True

    def read(self, recursive=False):
        if self.real_node is not None:
            self.real_node.read(recursive)

    def ensure_entries(self):
        if self.real_node is not None:
            self.real_node.ensure_entries()

    def get_entries(self):
        if self.real_node is None:
            return []
        return self.real_node.get_entries()

    def get_entries_sorted_by_name(self):
        if self.real_node is None:
            return []
        return self.real_node.get_entries_sorted_by_name()

    def check_entries(self):
        if self.real_node is not None:
            self.real_node.check_entries()

    def check_dircache(self):
        if self.real_node is not None:
            self.real_node.check_dircache()

    def get_size(self):
        return 0

    def get_size_str(self):
        return "DIR"

    def get_detail_str(self):
        return "linkdir=#%d" % self.real_entry

    def get_blocks(self, with_data=False):
        result = [self.block]
        result += self._get_comment_blocks()
        return result

    def get_block_nums(self):
        result = [self.block.blk_num]
        if self._own_comment_block() is not None:
            result.append(self.comment_blk_num)
        return result

    def draw_on_bitmap(self, bm, show_all=False, first=False):
        bm[self.block.blk_num] = ord("L")

    def flush(self):
        if self.real_node is not None:
            self.real_node.flush()

    def can_delete(self):
        # read-only: a directory link is never created here and is not deleted
        return False
