from .block.CommentBlock import CommentBlock
from .block.EntryBlock import EntryBlock
from .FileName import FileName
from .MetaInfo import MetaInfo
from .ProtectFlags import ProtectFlags
from .TimeStamp import TimeStamp
from .FSError import *
from .FSString import FSString
import amitools.util.ByteSize as ByteSize


class ADFSNode:
    def __init__(self, volume, parent):
        self.volume = volume
        self.blkdev = volume.blkdev
        self.parent = parent
        self.block_bytes = self.blkdev.block_bytes
        self.block = None
        self.name = None
        self.valid = False
        self.meta_info = None

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
        if self.block.comment_block_id != 0:
            comment_block = CommentBlock(self.blkdev, self.block.comment_block_id)
            comment_block.read()
            comment = comment_block.comment
        else:
            comment = self.block.comment
        self.meta_info = MetaInfo(self.block.protect, self.block.mod_ts, comment)

    def get_file_name(self):
        return self.name

    def delete(self, wipe=False, all=False, update_ts=True):
        if all:
            self.delete_children(wipe, all, update_ts)
        self.parent._delete(self, wipe, update_ts)

    def delete_children(self, wipe, all, update_ts):
        pass

    def get_meta_info(self):
        return self.meta_info

    def change_meta_info(self, meta_info):
        dirty = False

        # dircache?
        rebuild_dircache = False
        if self.volume.is_dircache and self.parent:
            record = self.parent.get_dircache_record(self.name.get_name())
            if not record:
                raise FSError(INTERNAL_ERROR, node=self, extra="dc not found!")
        else:
            record = None

        # alter protect flags
        protect = meta_info.get_protect()
        if protect and hasattr(self.block, "protect"):
            self.block.protect = protect
            self.meta_info.set_protect(protect)
            dirty = True
            if record:
                record.protect = protect

        # alter mod time
        mod_ts = meta_info.get_mod_ts()
        if mod_ts:
            self.block.mod_ts = mod_ts
            self.meta_info.set_mod_ts(mod_ts)
            dirty = True
            if record:
                record.mod_ts = mod_ts

        # alter comment
        comment = meta_info.get_comment()
        if comment and hasattr(self.block, "comment"):
            if EntryBlock.needs_extra_comment_block(self.name, comment):
                if self.block.comment_block_id == 0:
                    # Allocate and initialize extra block for comment
                    blks = self.volume.bitmap.alloc_n(1)
                    if blks is not None:
                        cblk = CommentBlock(self.blkdev, blks[0])
                        cblk.create(self.block.blk_num)
                        self.block.comment_block_id = cblk.blk_num
                    else:
                        raise FSError(NO_FREE_BLOCKS, node=self)
                else:
                    cblk = CommentBlock(self.blkdev, self.block.comment_block_id)
                    cblk.read()
                cblk.comment = comment
                cblk.write()
            else:
                self.block.comment = comment
                if self.block.comment_block_id != 0:
                    self.volume.bitmap.dealloc_n([self.block.comment_block_id])
                    self.block.comment_block_id = 0

            self.meta_info.set_comment(comment)
            dirty = True
            if record:
                rebuild_dircache = len(record.comment) < comment
                record.comment = comment

        # really need update?
        if dirty:
            self.block.write()
            # dirache update
            if record:
                self.parent.update_dircache_record(record, rebuild_dircache)

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
        t.parse(tm_str)
        self.change_meta_info(MetaInfo(mod_ts=t))

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
