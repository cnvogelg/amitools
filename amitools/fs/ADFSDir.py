import struct
from .block.Block import Block
from .block.UserDirBlock import UserDirBlock
from .block.EntryBlock import EntryBlock
from .block.DirCacheBlock import *
from .ADFSFile import ADFSFile
from .ADFSNode import ADFSNode
from .FileName import FileName
from .FSError import *
from .FSString import FSString
from .MetaInfo import *


class ADFSDir(ADFSNode):
    def __init__(self, volume, parent):
        ADFSNode.__init__(self, volume, parent)
        # state
        self.entries = None
        self.entry_bad_blk = None
        self.dcache_blks = None
        self.dcache_bad_blk = None
        self.name_hash = None
        self.hash_size = 72
        self.valid = False

    def __repr__(self):
        if self.block != None:
            return "[Dir(%d)'%s':%s]" % (
                self.block.blk_num,
                self.block.name,
                self.entries,
            )
        else:
            return "[Dir]"

    def create_extra_blks(self):
        # create a single empty dir cache block
        if self.volume.is_dircache:
            self.dcache_blks = []
            if self._dircache_add_block(True) == None:
                raise FSError(NO_FREE_BLOCKS, node=self, extra="want dcache")

    def blocks_create_old(self, anon_blk):
        ud = UserDirBlock(self.blkdev, anon_blk.blk_num, self.volume.is_longname)
        ud.set(anon_blk.data)
        if not ud.valid:
            raise FSError(INVALID_USER_DIR_BLOCK, block=anon_blk)
        self.set_block(ud)
        return ud

    def _read_add_node(self, blk, recursive):
        """the hash chain link and node of entry block blk. The node is None
        if blk gives none: it is no header, the header is invalid or of a
        type that is not read, as a link or the root block, or the blocks of
        its file cannot all be found. The link is 0 unless the header is
        valid"""
        node = None
        is_header = blk.valid_chksum and blk.type == Block.T_SHORT
        if is_header:
            # its a userdir
            if blk.sub_type == Block.ST_USERDIR:
                node = ADFSDir(self.volume, self)
            # its a file
            elif blk.sub_type == Block.ST_FILE:
                node = ADFSFile(self.volume, self)
        if node == None:
            # a valid header of a type that is not read, as a link, leads on
            # along its hash chain; the root block is in none
            if is_header and blk.sub_type != Block.ST_ROOT:
                return blk._get_long(-4), None
            return 0, None
        try:
            blk = node.blocks_create_old(blk)
        except FSError:
            # a file whose header is valid leads on along its hash chain
            if node.block != None:
                return node.block.hash_chain, None
            return 0, None
        if recursive and node.is_dir():
            node.read()
        return blk.hash_chain, node

    def _init_name_hash(self):
        self.name_hash = []
        self.hash_size = self.block.hash_size
        for i in range(self.hash_size):
            self.name_hash.append([])

    def read(self, recursive=False):
        # read into locals: a read that raises leaves me as I was
        name_hash = [[] for i in range(self.block.hash_size)]
        entries = []
        entry_bad_blk = None

        # create initial list with blk_num/hash_index for dir scan
        blocks = []
        for i in range(self.block.hash_size):
            blk_num = self.block.hash_table[i]
            if blk_num != 0:
                blocks.append((blk_num, i))

        blk_nums = set()
        for blk_num, hash_idx in blocks:
            # read anonymous block, once: a hash chain that leads to a block
            # of mine read before loops, or joins another chain. A block off
            # the disk is no entry
            blk = Block(self.blkdev, blk_num)
            node = None
            hash_chain = 0
            on_disk = self.blkdev.reserved <= blk_num < self.blkdev.num_blocks
            if on_disk and blk_num not in blk_nums:
                blk_nums.add(blk_num)
                blk.read()
                if blk.valid:
                    # create file/dir node
                    hash_chain, node = self._read_add_node(blk, recursive)
            if node == None:
                # a block that gives no entry ends its hash chain, unless it
                # is a valid header other than the root block, and the others
                # are read in full.
                # The entries read can be listed and read, but a new entry
                # could take the name or hash chain of one not read, and
                # deleting me would lose those
                if entry_bad_blk == None:
                    entry_bad_blk = blk
            else:
                # store node in entries
                entries.append(node)
                # store node in name_hash
                name_hash[hash_idx].append(node)
            # follow hash chain
            if hash_chain != 0:
                blocks.append((hash_chain, hash_idx))

        # dircaches available?
        dcache_blks = None
        dcache_bad_blk = None
        if self.volume.is_dircache:
            dcache_blks = []
            dcb_nums = set()
            dcb_num = self.block.extension
            while dcb_num != 0:
                dcb = DirCacheBlock(self.blkdev, dcb_num)
                if not self._read_dircache_block(dcb, dcb_nums):
                    # the entries can still be read, but a change would drop
                    # the records that could not be read
                    dcache_bad_blk = dcb
                    break
                dcache_blks.append(dcb)
                dcb_nums.add(dcb_num)
                dcb_num = dcb.next_cache

        self.hash_size = self.block.hash_size
        self.name_hash = name_hash
        self.entries = entries
        self.entry_bad_blk = entry_bad_blk
        self.dcache_blks = dcache_blks
        self.dcache_bad_blk = dcache_bad_blk
        if entry_bad_blk != None:
            self.valid = False

    def _read_dircache_block(self, dcb, dcb_nums):
        """read the next block of my dircache chain, after the blocks
        numbered in dcb_nums. It must lie on the disk, not be in the chain
        already, and be a valid dircache block of mine"""
        blk_num = dcb.blk_num
        if blk_num < self.blkdev.reserved or blk_num >= self.blkdev.num_blocks:
            return False
        if blk_num in dcb_nums:
            return False
        dcb.read()
        if not dcb.valid:
            return False
        return dcb.own_key == blk_num and dcb.parent == self.block.blk_num

    def check_entries(self):
        """refuse to add an entry to a directory, or remove one, if not all
        its entries could be read"""
        if self.entry_bad_blk != None:
            raise FSError(INVALID_ENTRY_BLOCK, block=self.entry_bad_blk, node=self)

    def check_dircache(self):
        """refuse to change a directory whose dircache cannot be read"""
        if self.dcache_bad_blk != None:
            raise FSError(INVALID_DIR_CACHE_BLOCK, block=self.dcache_bad_blk, node=self)

    def flush(self):
        if self.entries:
            for e in self.entries:
                e.flush()
        self.entries = None
        self.name_hash = None

    def ensure_entries(self):
        if self.entries == None:
            self.read()

    def get_entries(self):
        self.ensure_entries()
        return self.entries

    def has_name(self, fn):
        fn_hash = fn.hash(hash_size=self.hash_size)
        fn_up = fn.get_upper_ami_str()
        node_list = self.name_hash[fn_hash]
        for node in node_list:
            if node.name.get_upper_ami_str() == fn_up:
                return True
        return False

    def blocks_create_new(self, free_blks, name, hash_chain_blk, parent_blk, meta_info):
        blk_num = free_blks[0]
        blkdev = self.blkdev
        # create a UserDirBlock
        ud = UserDirBlock(blkdev, blk_num, self.volume.is_longname)
        ud.create(
            parent_blk,
            name,
            meta_info.get_protect(),
            meta_info.get_comment(),
            meta_info.get_mod_ts(),
            hash_chain_blk,
        )
        ud.write()
        self.set_block(ud)
        self._init_name_hash()
        # DOS5: create extra blocks
        if self.volume.is_dircache:
            self.create_extra_blks()
        return blk_num

    def blocks_get_create_num(self):
        # the number of blocks needed for a new (empty) directory
        # -> only one UserDirBlock
        return 1

    def _create_node(self, node, name, meta_info, update_ts=True):
        self.ensure_entries()
        self.check_entries()
        self.check_dircache()
        if update_ts and self.parent:
            self.parent.check_dircache()

        # make sure a default meta_info is available
        if meta_info == None:
            meta_info = MetaInfo()
            meta_info.set_current_as_mod_time()
            meta_info.set_default_protect()
        # check file name
        fn = FileName(
            name, is_intl=self.volume.is_intl, is_longname=self.volume.is_longname
        )
        if not fn.is_valid():
            raise FSError(INVALID_FILE_NAME, file_name=name, node=self)
        # does already exist an entry in this dir with this name?
        if self.has_name(fn):
            raise FSError(NAME_ALREADY_EXISTS, file_name=name, node=self)
        # check comment
        extra_comment = meta_info.get_comment()
        if extra_comment is not None:
            self._check_comment(extra_comment, file_name=name)
        # a long name comment that does not fit beside the name in the header
        # goes into a comment block, allocated along with the node's blocks
        if (
            self.volume.is_longname
            and extra_comment is not None
            and EntryBlock.needs_extra_comment_block(name, extra_comment)
        ):
            meta_info = MetaInfo(meta_info.get_protect(), meta_info.get_mod_ts())
        else:
            extra_comment = None
        # calc hash index of name
        fn_hash = fn.hash(hash_size=self.hash_size)
        hash_chain = self.name_hash[fn_hash]
        if len(hash_chain) == 0:
            hash_chain_blk = 0
        else:
            hash_chain_blk = hash_chain[0].block.blk_num

        # return the number of blocks required to create this node
        num_blks = node.blocks_get_create_num()
        if extra_comment is not None:
            num_blks += 1

        # try to find free blocks
        free_blks = self.volume.bitmap.alloc_n(num_blks)
        if free_blks == None:
            raise FSError(
                NO_FREE_BLOCKS, node=self, file_name=name, extra="want %d" % num_blks
            )
        if extra_comment is not None:
            comment_blk_num = free_blks.pop()

        # now create the blocks for this node
        new_blk = node.blocks_create_new(
            free_blks, name, hash_chain_blk, self.block.blk_num, meta_info
        )
        # write the comment block, then point the header to it
        if extra_comment is not None:
            try:
                node._write_comment_block(comment_blk_num, extra_comment)
                node.block.comment_block_id = comment_blk_num
                node.block.write()
            except Exception:
                # nothing links the new node yet: release all of its blocks
                self.volume.bitmap.dealloc_n(free_blks + [comment_blk_num])
                raise
            node.comment_blk_num = comment_blk_num
            node.meta_info.set_comment(extra_comment)

        # dircache: create record for this node
        if self.volume.is_dircache:
            ok = self._dircache_add_entry(
                name,
                meta_info,
                new_blk,
                node.get_size(),
                update_myself=False,
                sub_type=Block.ST_USERDIR if node.is_dir() else Block.ST_FILE,
            )
            if not ok:
                self.delete()
                raise FSError(
                    NO_FREE_BLOCKS, node=self, file_name=name, extra="want dcache"
                )

        # update my dir
        self.block.hash_table[fn_hash] = new_blk
        self.block.write()

        # add node
        self.name_hash[fn_hash].insert(0, node)
        self.entries.append(node)

        # update time stamps
        if update_ts:
            self.update_dir_mod_time()
            self.volume.update_disk_time()

    def update_dir_mod_time(self):
        mi = MetaInfo()
        mi.set_current_as_mod_time()
        self.change_meta_info(mi)

    def create_dir(self, name, meta_info=None, update_ts=True):
        if not isinstance(name, FSString):
            raise ValueError("create_dir's name must be a FSString")
        node = ADFSDir(self.volume, self)
        self._create_node(node, name, meta_info, update_ts)
        return node

    def create_file(self, name, data, meta_info=None, update_ts=True):
        if not isinstance(name, FSString):
            raise ValueError("create_file's name must be a FSString")
        node = ADFSFile(self.volume, self)
        node.set_file_data(data)
        self._create_node(node, name, meta_info, update_ts)
        return node

    def check_delete(self, node, all=False, update_ts=True):
        """refuse to delete node, with all its entries if all is set,
        before anything is written"""
        self.ensure_entries()
        self.check_entries()
        self.check_dircache()
        if update_ts and self.parent:
            self.parent.check_dircache()
        # the node is unlinked from the hash chain its name hashes to
        if node not in self.name_hash[node.name.hash(hash_size=self.hash_size)]:
            raise FSError(
                INTERNAL_ERROR, node=node, extra="node not found in hash chain"
            )
        if node.is_dir():
            node.ensure_entries()
            node.check_entries()
            node.check_dircache()
            if all:
                for entry in node.entries:
                    node.check_delete(entry, all, update_ts)

    def _delete(self, node, wipe, update_ts):
        self.check_delete(node, update_ts=update_ts)

        # can we delete?
        if not node.can_delete():
            raise FSError(DELETE_NOT_ALLOWED, node=node)
        # make sure its a node of mine
        if node.parent != self:
            raise FSError(INTERNAL_ERROR, node=node, extra="node parent is not me")
        if node not in self.entries:
            raise FSError(INTERNAL_ERROR, node=node, extra="node not in entries")
        # get hash key
        hash_key = node.name.hash(hash_size=self.hash_size)
        names = self.name_hash[hash_key]
        # find my node
        pos = None
        for i in range(len(names)):
            if names[i] == node:
                pos = i
                break
        # hmm not found?!
        if pos == None:
            raise FSError(
                INTERNAL_ERROR, node=node, extra="node not found in hash chain"
            )
        # find prev and next in hash list
        if pos > 0:
            prev = names[pos - 1]
        else:
            prev = None
        if pos == len(names) - 1:
            next_blk = 0
        else:
            next_blk = names[pos + 1].block.blk_num
        # the blocks to release: listed before anything is written, as this
        # checks that the comment block is still the node's
        blk_nums = node.get_block_nums()

        # remove node from the hash chain
        if prev == None:
            self.block.hash_table[hash_key] = next_blk
            self.block.write()
        else:
            prev.block.hash_chain = next_blk
            prev.block.write()

        # remove from my lists
        self.entries.remove(node)
        names.remove(node)

        # remove blocks of node in bitmap
        self.volume.bitmap.dealloc_n(blk_nums)

        # dircache?
        if self.volume.is_dircache:
            free_blk_num = self._dircache_remove_entry(node.name.name)
        else:
            free_blk_num = None

        # (optional) wipe blocks
        if wipe:
            clr_blk = b"\0" * self.blkdev.block_bytes
            for blk_num in blk_nums:
                self.blkdev.write_block(blk_num, clr_blk)
            # wipe a potentially free'ed dircache block, too
            if free_blk_num != None:
                self.blkdev.write_block(free_blk_num, clr_blk)

        # update time stamps
        if update_ts:
            self.update_dir_mod_time()
            self.volume.update_disk_time()

    def can_delete(self):
        self.ensure_entries()
        return len(self.entries) == 0

    def delete_children(self, wipe, all, update_ts):
        self.ensure_entries()
        if all:
            # refuse before the first entry goes, not after: the tree of
            # each entry is checked once, here
            for e in self.entries:
                self.check_delete(e, all, update_ts)
        for e in self.entries[:]:
            e._delete_tree(wipe, all, update_ts)

    def get_entries_sorted_by_name(self):
        self.ensure_entries()
        return sorted(self.entries, key=lambda x: x.name.get_upper_ami_str())

    def list(self, indent=0, all=False, detail=False, encoding="UTF-8"):
        ADFSNode.list(self, indent, all, detail, encoding)
        if not all and indent > 0:
            return
        self.ensure_entries()
        es = self.get_entries_sorted_by_name()
        for e in es:
            e.list(indent=indent + 1, all=all, detail=detail, encoding=encoding)

    def get_path(self, pc, allow_file=True, allow_dir=True):
        if len(pc) == 0:
            return self
        self.ensure_entries()
        for e in self.entries:
            if not isinstance(pc[0], FileName):
                raise ValueError("get_path's pc must be a FileName array")
            if e.name.get_upper_ami_str() == pc[0].get_upper_ami_str():
                if len(pc) > 1:
                    if isinstance(e, ADFSDir):
                        return e.get_path(pc[1:], allow_file, allow_dir)
                    else:
                        return None
                else:
                    if isinstance(e, ADFSDir):
                        if allow_dir:
                            return e
                        else:
                            return None
                    elif isinstance(e, ADFSFile):
                        if allow_file:
                            return e
                        else:
                            return None
                    else:
                        return None
        return None

    def draw_on_bitmap(self, bm, show_all=False, first=True):
        blk_num = self.block.blk_num
        bm[blk_num] = ord("D")
        if self._own_comment_block() is not None:
            bm[self.comment_blk_num] = ord("c")
        if show_all or first:
            self.ensure_entries()
            for e in self.entries:
                e.draw_on_bitmap(bm, show_all, False)
        if self.dcache_blks != None:
            for dcb in self.dcache_blks:
                bm[dcb.blk_num] = ord("C")

    def get_block_nums(self):
        self.ensure_entries()
        result = [self.block.blk_num]
        # the root block has no comment block: comment_blk_num stays 0
        if self._own_comment_block() is not None:
            result.append(self.comment_blk_num)
        if self.volume.is_dircache:
            for dcb in self.dcache_blks:
                result.append(dcb.blk_num)
        return result

    def get_blocks(self, with_data=False):
        self.ensure_entries()
        result = [self.block]
        result += self._get_comment_blocks()
        if self.volume.is_dircache:
            result += self.dcache_blks
        return result

    def get_size(self):
        return 0

    def get_size_str(self):
        return "DIR"

    def get_detail_str(self):
        self.ensure_entries()
        if self.entries != None:
            s = "entries=%d" % len(self.entries)
        else:
            s = ""
        if self.dcache_blks != None:
            s += " dcache=%d" % len(self.dcache_blks)
        return s

    # ----- dir cache -----

    def _dircache_check_read(self):
        """the changes refuse a dircache that could not be read before they
        write anything: getting here with one is a bug"""
        if self.dcache_blks == None or self.dcache_bad_blk != None:
            raise FSError(INTERNAL_ERROR, node=self, extra="dircache not read")

    def _dircache_add_entry(
        self, name, meta_info, entry_blk, size, update_myself=True, sub_type=0
    ):
        if not Block._is_valid_subtype(sub_type):
            raise FSError(
                UNSUPPORTED_DIR_BLOCK,
                block=entry_blk,
                extra="Sub_Type: %08x" % sub_type,
            )
        # create a new dircache record
        r = DirCacheRecord(
            entry=entry_blk,
            size=size,
            protect=meta_info.get_protect(),
            mod_ts=meta_info.get_mod_ts(),
            sub_type=sub_type,
            name=name,
            comment=meta_info.get_comment(),
        )
        return self._dircache_add_entry_int(r, update_myself)

    def _dircache_add_entry_int(self, r, update_myself=True):
        self._dircache_check_read()
        r_bytes = r.get_size()
        # find a dircache block with enough space
        for dcb in self.dcache_blks:
            free_bytes = dcb.get_free_record_size()
            if r_bytes < free_bytes:
                # add record to block and update it
                dcb.add_record(r)
                try:
                    dcb.write()
                except Exception:
                    dcb.remove_record(r)
                    raise
                return True
        # need to create a new one
        return self._dircache_add_block(update_myself, [r]) != None

    def _dircache_add_block(self, update_myself, records=None):
        # allocate block
        blk_nums = self.volume.bitmap.alloc_n(1)
        if blk_nums == None:
            return None
        # setup dir cache block and write it before anything links to it
        dcb_num = blk_nums[0]
        dcb = DirCacheBlock(self.blkdev, dcb_num)
        dcb.create(parent=self.block.blk_num, records=records)
        try:
            dcb.write()
            # link new cache block
            if len(self.dcache_blks) == 0:
                self.block.extension = dcb_num
                if update_myself:
                    self.block.write()
            else:
                last_dcb = self.dcache_blks[-1]
                last_dcb.next_cache = dcb_num
                last_dcb.write()
        except Exception:
            # nothing on disk links to the block: release it
            if len(self.dcache_blks) == 0:
                self.block.extension = 0
            else:
                self.dcache_blks[-1].next_cache = 0
            self.volume.bitmap.dealloc_n([dcb_num])
            raise
        self.dcache_blks.append(dcb)
        return dcb

    def _dircache_remove_entry(self, name, update_myself=True):
        # first find entry
        for dcb in self.dcache_blks:
            record = dcb.get_record_by_name(name)
            if record != None:
                return self._dircache_remove_record(dcb, record, update_myself)
        raise FSError(INTERNAL_ERROR, node=self, extra="no dc record!")

    def _dircache_remove_record(self, dcb, record, update_myself=True):
        self._dircache_check_read()
        pos = self.dcache_blks.index(dcb)
        idx = dcb.records.index(record)
        # remove entry from this block
        dcb.remove_record(record)
        try:
            # remove whole block? (but keep at least one)
            if dcb.is_empty() and len(self.dcache_blks) > 1:
                # next block following me
                if pos == len(self.dcache_blks) - 1:
                    next = 0
                else:
                    next = self.dcache_blks[pos + 1].blk_num
                # update block links
                if pos == 0:
                    # adjust extension link in this dir node
                    self.block.extension = next
                    if update_myself:
                        self.block.write()
                else:
                    # adjust dircache block in front of me
                    prev_blk = self.dcache_blks[pos - 1]
                    prev_blk.next_cache = next
                    prev_blk.write()
            else:
                # update cache block with reduced set of records
                dcb.write()
                return None
        except Exception:
            # the record is still on disk: keep it here, too
            if pos == 0:
                self.block.extension = dcb.blk_num
            else:
                self.dcache_blks[pos - 1].next_cache = dcb.blk_num
            dcb.records.insert(idx, record)
            dcb.num_records = len(dcb.records)
            raise
        # free cache block in bitmap
        blk_num = dcb.blk_num
        self.volume.bitmap.dealloc_n([blk_num])
        del self.dcache_blks[pos]
        return blk_num  # return number of just deleted block

    def get_dircache_record(self, name):
        if self.dcache_blks:
            for dcb in self.dcache_blks:
                record = dcb.get_record_by_name(name)
                if record:
                    return record
        return None

    def _dircache_fits(self, dcb, new_record, record):
        """does new_record fit into dcb once record leaves it?"""
        size = new_record.get_size()
        free_bytes = dcb.get_free_record_size()
        if dcb.has_record(record):
            # a record that does not grow always fits in its place
            if size <= record.get_size():
                return True
            free_bytes += record.get_size()
        return size < free_bytes

    def check_dircache_room(self, record, new_record):
        """make sure that new_record, replacing record, finds room in the
        dircache: in a block, or else in a free block for a new one"""
        for dcb in self.dcache_blks:
            if self._dircache_fits(dcb, new_record, record):
                return
        if self.volume.bitmap.find_n_free(1) == None:
            raise FSError(NO_FREE_BLOCKS, node=self, extra="want dcache")

    def update_dircache_record(self, record, new_record):
        """replace record by new_record, in its block if it fits there. Else
        new_record is written to another block before record leaves its
        own, and taken out again if that fails: only if that fails, too,
        are both on disk, and the records here as on disk"""
        self._dircache_check_read()
        for dcb in self.dcache_blks:
            if dcb.has_record(record):
                break
        else:
            raise FSError(INTERNAL_ERROR, node=self, extra="no dc record!")
        if self._dircache_fits(dcb, new_record, record):
            idx = dcb.records.index(record)
            dcb.records[idx] = new_record
            try:
                dcb.write()
            except Exception:
                dcb.records[idx] = record
                raise
        else:
            # check_dircache_room() made sure that this finds room
            if not self._dircache_add_entry_int(new_record):
                raise FSError(INTERNAL_ERROR, node=self, extra="dc record lost!")
            try:
                self._dircache_remove_record(dcb, record)
            except Exception:
                self._dircache_take_back(new_record)
                raise

    def _dircache_take_back(self, record):
        """remove a record added just before, and a block added for it,
        after a later write failed. Returns False if that fails, too: the
        record then stays, here as on disk"""
        for dcb in self.dcache_blks:
            if dcb.has_record(record):
                try:
                    self._dircache_remove_record(dcb, record)
                except Exception:
                    return False
                break
        return True

    def get_block_usage(self, all=False, first=True):
        num_non_data = 1
        num_data = 0
        if self._own_comment_block() is not None:
            num_non_data += 1
        if self.dcache_blks != None:
            num_non_data += len(self.dcache_blks)
        if all or first:
            self.ensure_entries()
            for e in self.entries:
                bu = e.get_block_usage(all=all, first=False)
                num_data += bu[0]
                num_non_data += bu[1]
        return (num_data, num_non_data)

    def get_file_bytes(self, all=False, first=True):
        size = 0
        if all or first:
            self.ensure_entries()
            for e in self.entries:
                size += e.get_file_bytes(all=all, first=False)
        return size

    def is_dir(self):
        return True
