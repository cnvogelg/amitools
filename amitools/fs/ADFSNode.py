from .block.Block import Block
from .block.CommentBlock import CommentBlock
from .block.DirCacheBlock import DirCacheRecord
from .block.EntryBlock import EntryBlock
from .FileName import FileName
from .MetaInfo import MetaInfo
from .ProtectFlags import ProtectFlags
from .TimeStamp import TimeStamp
from .FSError import *
from .FSString import FSString
import amitools.util.ByteSize as ByteSize

# AmigaDOS keeps at most 79 bytes of comment, whatever the DOS type
MAX_COMMENT_BYTES = 79


def check_comment(comment, node=None, file_name=None):
    """refuse a comment the disk cannot hold: FastFileSystem rejects more
    than 79 bytes, and the disk stores Latin-1 only"""
    try:
        size = len(comment.get_ami_str())
    except UnicodeEncodeError:
        raise FSError(
            INVALID_COMMENT, node=node, file_name=file_name, extra="not Latin-1"
        ) from None
    if size > MAX_COMMENT_BYTES:
        raise FSError(
            INVALID_COMMENT,
            node=node,
            file_name=file_name,
            extra="%d bytes, max %d" % (size, MAX_COMMENT_BYTES),
        )


class ADFSNode:
    """an entry of a directory, or the root directory.

    A block write that fails leaves the entry as it was, in memory as on
    disk: a create or delete takes effect with the one write that links or
    unlinks the entry, a meta info change with the write of its header,
    which is written back as it was if a later write fails. If a write
    that undoes a change fails too, blocks may stay allocated with nothing
    using them, but no write makes a header or a dircache record point to
    a block that the change frees, or to a free block that it did not
    point to when it was read. A copy of a dircache record that is left
    behind goes with the entry's next change or delete, a record that is
    lost comes back with its next change, and a create that cannot take
    its record out again leaves that record, and the blocks it points to,
    with no entry. A meta info change whose header cannot be written back
    leaves the change in the header on disk, but not in memory or in the
    dircache record, until the entry's next change."""

    def __init__(self, volume, parent):
        self.volume = volume
        self.blkdev = volume.blkdev
        self.parent = parent
        self.block_bytes = self.blkdev.block_bytes
        self.block = None
        self.name = None
        self.valid = False
        self.meta_info = None
        # the comment block that belongs to this entry, if any
        self.comment_blk_num = 0

    def __str__(self):
        return "%s:'%s'(@%d)" % (
            self.__class__.__name__,
            self.get_node_path_name(),
            self.block.blk_num,
        )

    def set_block(self, block):
        self.block = block
        self.name = FileName(
            self.block.name,
            is_intl=self.volume.is_intl,
            is_longname=self.volume.is_longname,
        )
        self.valid = True
        self.create_meta_info()

    def create_meta_info(self):
        """take protection, date and comment from my header. My header keeps
        its pointer to a block that reads as my comment block, and I keep
        the comment read from it, also if the bitmap marks the block free,
        as when the bitmap was not written after a change. Such a block is
        mine to free, rewrite and count only if the bitmap has it
        allocated"""
        self.meta_info = MetaInfo(
            self.block.protect, self.block.mod_ts, self.block.comment
        )
        blk_num = self.block.comment_block_id
        comment_block = self._read_comment_block(blk_num)
        if comment_block is None:
            # any other block is, or may become, another entry's: it is
            # never freed or rewritten, and the next header write drops the
            # pointer
            self.block.comment_block_id = 0
            return
        if comment_block.valid:
            self.meta_info.set_comment(comment_block.comment)
        if not self.volume.bitmap.get_bit(blk_num):
            self.comment_blk_num = blk_num

    def _read_comment_block(self, blk_num):
        """read block blk_num if it reads as my comment block: its type, own
        key, header key and a comment of at most 79 bytes, whatever its
        checksum, so that a damaged one holds the comment again once
        repaired. A block off the disk or a boot block never does, nor a
        bitmap block, which is always allocated and whose first long is its
        checksum. Returns the block, or None"""
        if blk_num < self.blkdev.reserved or blk_num >= self.blkdev.num_blocks:
            return None
        bitmap = self.volume.bitmap
        if blk_num in [blk.blk_num for blk in bitmap.bitmap_blks + bitmap.ext_blks]:
            return None
        comment_block = CommentBlock(self.blkdev, blk_num)
        comment_block.read()
        if (
            comment_block.type == Block.T_COMMENT
            and comment_block._get_long(1) == blk_num
            and comment_block._get_long(2) == self.block.blk_num
            and comment_block._get_bytes(6, 1)[0] <= MAX_COMMENT_BYTES
        ):
            return comment_block
        return None

    def _own_comment_block(self):
        """my comment block, read, or None: the block that my header pointed
        to when it was read, or that a comment change of mine wrote, while
        the bitmap has it allocated and it reads as mine. A block can be
        freed and taken by another entry while the volume is open, as when
        it holds data of a file that is deleted, so this is checked each
        time before the block is freed, rewritten or counted, and once the
        check fails the block is not mine again.

        Only a comment change of mine writes a comment block: the one I own,
        or a new one from the bitmap, which it writes before my header
        points to it. Every other write of my header keeps the pointer as it
        was read. So no write makes my header point to a block that the
        write frees, or to a free block that it did not point to when it was
        read"""
        blk_num = self.comment_blk_num
        comment_block = None
        if blk_num != 0 and not self.volume.bitmap.get_bit(blk_num):
            comment_block = self._read_comment_block(blk_num)
        if comment_block is None:
            self.comment_blk_num = 0
        return comment_block

    def _get_comment_blocks(self):
        """my comment block, as a list for get_blocks(): empty if I have
        none, or one too damaged to decode"""
        comment_block = self._own_comment_block()
        if comment_block is not None and comment_block.valid:
            return [comment_block]
        return []

    def get_file_name(self):
        return self.name

    def delete(self, wipe=False, all=False, update_ts=True):
        if not self.parent:
            # the root has no parent to unlink it from: it stays, and only
            # its entries go
            if not all:
                raise FSError(DELETE_NOT_ALLOWED, node=self)
            self.delete_children(wipe, all, update_ts)
            return
        if all:
            # refuse before the first entry goes, not after: the tree is
            # checked once, here, and not again for each entry
            self.parent.check_delete(self, all, update_ts)
        self._delete_tree(wipe, all, update_ts)

    def _delete_tree(self, wipe, all, update_ts):
        """delete me, and first, with all set, my entries, through this,
        too: the tree is checked already"""
        if all and self.is_dir():
            for entry in self.get_entries()[:]:
                entry._delete_tree(wipe, all, update_ts)
        self.parent._delete(self, wipe, update_ts)

    def delete_children(self, wipe, all, update_ts):
        pass

    def get_meta_info(self):
        return self.meta_info

    def _check_comment(self, comment, file_name=None):
        check_comment(comment, node=self, file_name=file_name)

    def change_meta_info(self, meta_info):
        # check the comment before anything changes
        comment = meta_info.get_comment()
        if comment and hasattr(self.block, "comment"):
            self._check_comment(comment)
        else:
            comment = None
        protect = meta_info.get_protect()
        if not hasattr(self.block, "protect"):
            protect = None
        mod_ts = meta_info.get_mod_ts()
        # a protection of 0, ----rwed, is a change, too
        if protect is None and not (mod_ts or comment):
            return
        # a comment change rewrites or frees only a comment block that is
        # still mine
        own_blk_num = 0
        if comment and self._own_comment_block() is not None:
            own_blk_num = self.comment_blk_num

        # dircache: a new record, swapped in once written, takes the values
        # of the header, not of the record: a record left behind by a failed
        # write may hold those of that change, a stale one another entry's
        # name. A record that a failed write lost is added again
        record = None
        new_record = None
        if self.volume.is_dircache and self.parent:
            self.parent.check_dircache()
            record = self.parent.get_dircache_record(self)
            new_comment = comment or self.meta_info.get_comment()
            if new_comment is None and record:
                # the header's comment cannot be read, and the record's,
                # longer than 79 bytes, did not fit into it when the
                # directory was read: keep the record's
                new_comment = record.comment
            new_record = DirCacheRecord(
                entry=self.block.blk_num,
                size=self.get_size(),
                protect=(
                    protect if protect is not None else self.meta_info.get_protect()
                ),
                mod_ts=mod_ts or self.meta_info.get_mod_ts(),
                sub_type=self.block.sub_type,
                name=self.name.get_name(),
                comment=new_comment,
            )
            # a grown record may need a new dircache block: make sure that
            # there is one before anything changes
            self.parent.check_dircache_room(record, new_record)

        # a long name comment that does not fit beside the name goes into
        # the entry's own comment block, or else into a new one
        comment_blk_num = 0
        new_blk_num = 0
        if (
            comment
            and self.volume.is_longname
            and EntryBlock.needs_extra_comment_block(self.name.get_name(), comment)
        ):
            comment_blk_num = own_blk_num
            if comment_blk_num == 0:
                blks = self.volume.bitmap.alloc_n(1)
                if blks is None:
                    raise FSError(NO_FREE_BLOCKS, node=self)
                comment_blk_num = new_blk_num = blks[0]

        # change the header, and put it back as it was if a write fails
        saved = {
            name: getattr(self.block, name)
            for name in ("protect", "mod_ts", "comment", "comment_block_id")
            if hasattr(self.block, name)
        }
        if protect is not None:
            self.block.protect = protect
        if mod_ts:
            self.block.mod_ts = mod_ts
        if comment:
            self.block.comment_block_id = comment_blk_num
            if comment_blk_num == 0:
                self.block.comment = comment
        header_written = False
        try:
            # a new comment block is written before the header points to it,
            # the entry's own one after the header, so that a header write
            # that fails leaves the old comment
            if new_blk_num != 0:
                self._write_comment_block(new_blk_num, comment)
            self.block.write()
            header_written = True
            if comment_blk_num != 0 and new_blk_num == 0:
                self._write_comment_block(comment_blk_num, comment)
            if new_record:
                self.parent.update_dircache_record(record, new_record)
        except Exception:
            # a new comment block is released once no header points to it
            for name, value in saved.items():
                setattr(self.block, name, value)
            try:
                if header_written:
                    self.block.write()
                if new_blk_num != 0:
                    self.volume.bitmap.dealloc_n([new_blk_num])
            except Exception:
                # the header on disk keeps the change until the entry's next
                # change: raise the first error
                pass
            raise

        # all is written: release a comment block the entry no longer uses
        if comment:
            if own_blk_num not in (0, comment_blk_num):
                self.volume.bitmap.dealloc_n([own_blk_num])
            self.comment_blk_num = comment_blk_num
            self.meta_info.set_comment(comment)
        if protect is not None:
            self.meta_info.set_protect(protect)
        if mod_ts:
            self.meta_info.set_mod_ts(mod_ts)

    def _write_comment_block(self, blk_num, comment):
        """write comment into comment block blk_num of this entry"""
        comment_block = CommentBlock(self.blkdev, blk_num)
        comment_block.create(self.block.blk_num, comment)
        comment_block.write()

    def change_comment(self, comment):
        self.change_meta_info(MetaInfo(comment=comment))

    def change_protect(self, protect):
        self.change_meta_info(MetaInfo(protect=protect))

    def change_protect_by_string(self, pr_str):
        p = ProtectFlags()
        p.parse(pr_str)
        self.change_protect(p.mask)

    def change_mod_ts(self, mod_ts):
        self.change_meta_info(MetaInfo(mod_ts=mod_ts))

    def change_mod_ts_by_string(self, tm_str):
        t = TimeStamp()
        if not t.parse(tm_str):
            return False
        self.change_meta_info(MetaInfo(mod_ts=t))
        return True

    def get_list_str(self, indent=0, all=False, detail=False):
        istr = "  " * indent
        if detail:
            extra = self.get_detail_str()
        else:
            extra = self.meta_info.get_str_line()
        return "%-40s       %8s  %s" % (
            istr + self.name.get_unicode_name(),
            self.get_size_str(),
            extra,
        )

    def list(self, indent=0, all=False, detail=False, encoding="UTF-8"):
        print(self.get_list_str(indent=indent, all=all, detail=detail))

    def get_size_str(self):
        # re-implemented in derived classes!
        return ""

    def get_blocks(self, with_data=False):
        # re-implemented in derived classes!
        return 0

    def get_file_data(self):
        return None

    def dump_blocks(self, with_data=False):
        blks = self.get_blocks(with_data)
        for b in blks:
            b.dump()

    def get_node_path(self, with_vol=False):
        if self.parent != None:
            if not with_vol and self.parent.parent == None:
                r = []
            else:
                r = self.parent.get_node_path()
        else:
            if not with_vol:
                return []
            r = []
        r.append(self.name.get_unicode_name())
        return r

    def get_node_path_name(self, with_vol=False):
        r = self.get_node_path()
        return FSString("/".join(r))

    def get_detail_str(self):
        return ""

    def get_block_usage(self, all=False, first=True):
        return (0, 0)

    def get_file_bytes(self, all=False, first=True):
        return (0, 0)

    def is_file(self):
        return False

    def is_dir(self):
        return False

    def get_info(self, all=False):
        # block usage: data + fs blocks
        (data, fs) = self.get_block_usage(all=all)
        total = data + fs
        bb = self.blkdev.block_bytes
        btotal = total * bb
        bdata = data * bb
        bfs = fs * bb
        prc_data = 10000 * data / total
        prc_fs = 10000 - prc_data
        res = []
        res.append(
            "sum:    %10d  %s  %12d"
            % (total, ByteSize.to_byte_size_str(btotal), btotal)
        )
        res.append(
            "data:   %10d  %s  %12d  %5.2f%%"
            % (data, ByteSize.to_byte_size_str(bdata), bdata, prc_data / 100.0)
        )
        res.append(
            "fs:     %10d  %s  %12d  %5.2f%%"
            % (fs, ByteSize.to_byte_size_str(bfs), bfs, prc_fs / 100.0)
        )
        return res
