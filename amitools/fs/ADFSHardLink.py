from .ADFSFile import ADFSFile
from .ADFSNode import ADFSNode
from .block.Block import Block
from .block.FileHeaderBlock import FileHeaderBlock
from .FSError import FSError, INVALID_FILE_HEADER_BLOCK


class ADFSHardLink(ADFSNode):
    """a hard link (``ST_LINKFILE``) on an ADFS volume.

    A hard link is stored as its own file header block: its ``real_entry``
    points at the block of the file it names and its ``next_link`` chains the
    links of that file (newest first). The link block holds the link's own
    name, parent and hash chain, while the data and metadata are shared with
    the real file: a lookup follows the link to the real node, and both names
    see the same file. Deleting the link frees only its own block.
    """

    def __init__(self, volume, parent):
        ADFSNode.__init__(self, volume, parent)
        self.real_entry = 0
        self.real_node = None
        self.valid = False

    def __repr__(self):
        return "[HardLink(%d)'%s'->%d]" % (
            self.block.blk_num,
            self.block.name,
            self.real_entry,
        )

    def blocks_create_old(self, anon_blk):
        # create the link's file header block
        fhb = FileHeaderBlock(
            self.blkdev,
            anon_blk.blk_num,
            self.volume.is_longname,
            sub_type=Block.ST_LINKFILE,
        )
        fhb.set(anon_blk.data)
        if not fhb.valid:
            raise FSError(INVALID_FILE_HEADER_BLOCK, block=anon_blk)
        self.set_block(fhb)
        self.real_entry = fhb.real_entry
        self.real_node = self._read_real_node()
        self.valid = True
        return fhb

    def _read_real_node(self):
        """read the file the link names, as an :class:`ADFSFile`"""
        blk_num = self.real_entry
        if not self.blkdev.reserved <= blk_num < self.blkdev.num_blocks:
            raise FSError(
                INVALID_FILE_HEADER_BLOCK, node=self, extra="real entry off the disk"
            )
        blk = Block(self.blkdev, blk_num)
        blk.read()
        if not blk.valid:
            raise FSError(INVALID_FILE_HEADER_BLOCK, block=blk)
        real = ADFSFile(self.volume, self.parent)
        real.blocks_create_old(blk)
        return real

    def blocks_get_create_num(self):
        # a hard link needs only its header block
        return 1

    def blocks_create_new(self, free_blks, name, hash_chain_blk, parent_blk, meta_info):
        real = self.real_node
        link_num = free_blks[0]
        # read the real file's header fresh: the in-memory node may be a
        # separate instance with a stale link chain
        real_blk = FileHeaderBlock(
            self.blkdev, real.block.blk_num, self.volume.is_longname
        )
        real_blk.read()
        old_head = real_blk.next_link if real_blk.valid else real.block.next_link
        fhb = FileHeaderBlock(
            self.blkdev,
            link_num,
            self.volume.is_longname,
            sub_type=Block.ST_LINKFILE,
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
            real_entry=real.block.blk_num,
            next_link=old_head,
            uid=meta_info.get_owner_uid(),
            gid=meta_info.get_owner_gid(),
        )
        fhb.write()
        # chain the new link at the head of the real file's link list; put it
        # back if the write fails
        real_blk.next_link = link_num
        try:
            real_blk.write(links=True)
        except Exception:
            real_blk.next_link = old_head
            raise
        # keep the in-memory real node in step
        real.block.next_link = link_num
        self._sync_loaded(real.block.blk_num, link_num)
        self.set_block(fhb)
        self.real_entry = real.block.blk_num
        self.valid = True
        return link_num

    def _sync_loaded(self, blk_num, next_link):
        """keep the node of block blk_num that the volume has read in step
        with the chain on disk: a file can be held by more than one instance
        (the directory's entry and a link's real node), and a stale one must
        not write its old chain back"""
        node = self.volume.find_node(blk_num)
        if node is not None and node.block is not None:
            node.block.next_link = next_link

    def get_real_node(self):
        return self.real_node

    def unlink_extra(self):
        """take my block out of the real file's hard-link chain"""
        real = self.real_node
        if real is None:
            return
        real_blk = FileHeaderBlock(
            self.blkdev, real.block.blk_num, self.volume.is_longname
        )
        real_blk.read()
        if not real_blk.valid:
            return
        prev = real_blk
        nxt = prev.next_link
        while nxt != 0 and nxt != self.block.blk_num:
            link = FileHeaderBlock(
                self.blkdev, nxt, self.volume.is_longname, sub_type=Block.ST_LINKFILE
            )
            link.read()
            if not link.valid:
                return
            prev = link
            nxt = link.next_link
        if nxt == self.block.blk_num:
            # my own header may be stale, too: read its current chain link
            my = FileHeaderBlock(
                self.blkdev,
                self.block.blk_num,
                self.volume.is_longname,
                sub_type=Block.ST_LINKFILE,
            )
            my.read()
            after = my.next_link if my.valid else self.block.next_link
            prev.next_link = after
            prev.write(links=True)
            self.block.next_link = after
            self._sync_loaded(prev.blk_num, after)
        # keep the in-memory real node in step
        real.block.next_link = real_blk.next_link
        self._sync_loaded(real.block.blk_num, real_blk.next_link)

    def flush(self):
        if self.real_node is not None:
            self.real_node.flush()

    def is_file(self):
        return True

    def is_dir(self):
        return False

    def get_size(self):
        return self.real_node.get_size()

    def get_size_str(self):
        return self.real_node.get_size_str()

    def get_file_data(self):
        return self.real_node.get_file_data()

    def ensure_data(self):
        self.real_node.ensure_data()

    def get_data_block_contents_bytes(self):
        return self.real_node.get_data_block_contents_bytes()

    def get_detail_str(self):
        return "link=#%d" % self.real_entry

    def get_block_usage(self, all=False, first=True):
        # the link's own header, not the blocks it shares with the real file
        num_non_data = 1
        if self._own_comment_block() is not None:
            num_non_data += 1
        return (0, num_non_data)

    def get_file_bytes(self, all=False, first=True):
        return 0

    def get_block_nums(self):
        result = [self.block.blk_num]
        if self._own_comment_block() is not None:
            result.append(self.comment_blk_num)
        return result

    def get_blocks(self, with_data=True):
        result = [self.block]
        result += self._get_comment_blocks()
        if with_data and self.real_node is not None:
            result += self.real_node.get_blocks(with_data)
        return result

    def draw_on_bitmap(self, bm, show_all=False, first=False):
        bm[self.block.blk_num] = ord("H")
        if self._own_comment_block() is not None:
            bm[self.comment_blk_num] = ord("c")

    def can_delete(self):
        return True
