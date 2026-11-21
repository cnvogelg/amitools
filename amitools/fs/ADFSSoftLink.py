from .ADFSNode import ADFSNode
from .block.Block import Block
from .block.FileHeaderBlock import FileHeaderBlock
from .FSError import *
from .FSString import FSString


class ADFSSoftLink(ADFSNode):
    """a soft link (``ST_SOFTLINK``) on an ADFS volume.

    A soft link is stored as a file header block with no data blocks whose
    data-block pointer table holds the link target as a NUL-terminated C
    string (see :class:`FileHeaderBlock`). It is an object of its own: a
    normal path lookup follows it to the object it names, while
    ``ADFSVolume.get_link_path_name`` returns the link itself.
    """

    def __init__(self, volume, parent):
        ADFSNode.__init__(self, volume, parent)
        self.target = None
        self.valid = False

    def __repr__(self):
        return "[SoftLink(%d)'%s'->'%s']" % (
            self.block.blk_num,
            self.block.name,
            self.target,
        )

    def blocks_create_old(self, anon_blk):
        # create file header block
        fhb = FileHeaderBlock(
            self.blkdev,
            anon_blk.blk_num,
            self.volume.is_longname,
            sub_type=Block.ST_SOFTLINK,
        )
        fhb.set(anon_blk.data)
        if not fhb.valid:
            raise FSError(INVALID_FILE_HEADER_BLOCK, block=anon_blk)
        self.set_block(fhb)
        self.target = fhb.symbolic_name
        return fhb

    def blocks_get_create_num(self):
        # a soft link needs only its header block
        return 1

    def blocks_create_new(self, free_blks, name, hash_chain_blk, parent_blk, meta_info):
        fhb = FileHeaderBlock(
            self.blkdev,
            free_blks[0],
            self.volume.is_longname,
            sub_type=Block.ST_SOFTLINK,
        )
        fhb.create(
            parent_blk,
            name,
            [],
            0,
            byte_size=0,
            protect=meta_info.get_protect(),
            comment=meta_info.get_comment(),
            mod_ts=meta_info.get_mod_ts(),
            hash_chain=hash_chain_blk,
            symbolic_name=self.target,
            uid=meta_info.get_owner_uid(),
            gid=meta_info.get_owner_gid(),
        )
        fhb.write()
        self.set_block(fhb)
        self.valid = True
        return free_blks[0]

    def get_target(self):
        return self.target

    def set_target(self, fs_str):
        if not isinstance(fs_str, FSString):
            raise ValueError("set_target's target must be a FSString")
        max_size = (self.blkdev.block_longs - 56) * 4 - 1
        if len(fs_str.get_ami_str()) > max_size:
            raise FSError(INVALID_FILE_NAME, node=self, extra="link target too long")
        self.target = fs_str

    def flush(self):
        pass

    def draw_on_bitmap(self, bm, show_all=False, first=False):
        bm[self.block.blk_num] = ord("L")
        if self._own_comment_block() is not None:
            bm[self.comment_blk_num] = ord("c")

    def get_block_nums(self):
        result = [self.block.blk_num]
        if self._own_comment_block() is not None:
            result.append(self.comment_blk_num)
        return result

    def get_blocks(self, with_data=True):
        result = [self.block]
        result += self._get_comment_blocks()
        return result

    def can_delete(self):
        return True

    def get_size(self):
        return 0

    def get_size_str(self):
        return "LINK"

    def get_detail_str(self):
        return "link=%s" % self.target.get_unicode()

    def get_block_usage(self, all=False, first=True):
        num_non_data = 1
        if self._own_comment_block() is not None:
            num_non_data += 1
        return (0, num_non_data)

    def get_file_bytes(self, all=False, first=True):
        return 0

    def is_file(self):
        return True

    def is_dir(self):
        return False
