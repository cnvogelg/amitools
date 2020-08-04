import struct
from .block.Block import Block
from .block.UserDirBlock import UserDirBlock
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
        self.dcache_blks = None
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
            dcb = self._dircache_add_block(True)
            dcb.write()

    def blocks_create_old(self, anon_blk):
        ud = UserDirBlock(self.blkdev, anon_blk.blk_num, self.volume.is_longname)
        ud.set(anon_blk.data)
        if not ud.valid:
            raise FSError(INVALID_USER_DIR_BLOCK, block=anon_blk)
        self.set_block(ud)
        return ud

    def _read_add_node(self, blk, recursive):
        hash_chain = None
        node = None
        if blk.valid_chksum and blk.type == Block.T_SHORT:
            # its a userdir
            if blk.sub_type == Block.ST_USERDIR:
                node = ADFSDir(self.volume, self)
                blk = node.blocks_create_old(blk)
                if recursive:
                    node.read()
            # its a file
            elif blk.sub_type == Block.ST_FILE:
                node = ADFSFile(self.volume, self)
                blk = node.blocks_create_old(blk)
            # unsupported
            else:
                raise FSError(
                    UNSUPPORTED_DIR_BLOCK,
                    block=blk,
                    extra="Sub_Type: %08x" % blk.sub_type,
                )
        hash_chain = blk.hash_chain
        return hash_chain, node

    def _init_name_hash(self):
        self.name_hash = []
        self.hash_size = self.block.hash_size
        for i in range(self.hash_size):
            self.name_hash.append([])

    def read(self, recursive=False):
        self._init_name_hash()
        self.entries = []

        # create initial list with blk_num/hash_index for dir scan
        blocks = []
        for i in range(self.block.hash_size):
            blk_num = self.block.hash_table[i]
            if blk_num != 0:
                blocks.append((blk_num, i))

        for blk_num, hash_idx in blocks:
            # read anonymous block
            blk = Block(self.blkdev, blk_num)
            blk.read()
            if not blk.valid:
                self.valid = False
                return
            # create file/dir node
            hash_chain, node = self._read_add_node(blk, recursive)
            # store node in entries
            self.entries.append(node)
            # store node in name_hash
            self.name_hash[hash_idx].append(node)
            # follow hash chain
            if hash_chain != 0:
                blocks.append((hash_chain, hash_idx))

        # dircaches available?
        if self.volume.is_dircache:
            self.dcache_blks = []
            dcb_num = self.block.extension
            while dcb_num != 0:
                dcb = DirCacheBlock(self.blkdev, dcb_num)
                dcb.read()
                if not dcb.valid:
                    self.valid = False
                    return
                self.dcache_blks.append(dcb)
                dcb_num = dcb.next_cache

    def flush(self):
        if self.entries:
            for e in self.entries:
                e.flush()
        self.entries = None
        self.name_hash = None

    def ensure_entries(self):
        if not self.entries:
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
        # calc hash index of name
        fn_hash = fn.hash(hash_size=self.hash_size)
        hash_chain = self.name_hash[fn_hash]
        if len(hash_chain) == 0:
            hash_chain_blk = 0
        else:
            hash_chain_blk = hash_chain[0].block.blk_num

        # return the number of blocks required to create this node
        num_blks = node.blocks_get_create_num()

        # try to find free blocks
        free_blks = self.volume.bitmap.alloc_n(num_blks)
        if free_blks == None:
            raise FSError(
                NO_FREE_BLOCKS, node=self, file_name=name, extra="want %d" % num_blks
            )

        # now create the blocks for this node
        new_blk = node.blocks_create_new(
            free_blks, name, hash_chain_blk, self.block.blk_num, meta_info
        )

        # dircache: create record for this node
        if self.volume.is_dircache:
            ok = self._dircache_add_entry(
                name, meta_info, new_blk, node.get_size(), update_myself=False
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

    def _delete(self, node, wipe, update_ts):
        self.ensure_entries()

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
        blk_nums = node.get_block_nums()
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
        entries = self.entries[:]
        for e in entries:
            e.delete(wipe, all, update_ts)

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
        bm[blk_num] = "D"
        if show_all or first:
            self.ensure_entries()
            for e in self.entries:
                e.draw_on_bitmap(bm, show_all, False)
        if self.dcache_blks != None:
            for dcb in self.dcache_blks:
                bm[dcb.blk_num] = "C"

    def get_block_nums(self):
        self.ensure_entries()
        result = [self.block.blk_num]
        if self.volume.is_dircache:
            for dcb in self.dcache_blks:
                result.append(dcb.blk_num)
        return result

    def get_blocks(self, with_data=False):
        self.ensure_entries()
        result = [self.block]
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

    def _dircache_add_entry(self, name, meta_info, entry_blk, size, update_myself=True):
        # create a new dircache record
        r = DirCacheRecord(
            entry=entry_blk,
            size=size,
            protect=meta_info.get_protect(),
            mod_ts=meta_info.get_mod_ts(),
            sub_type=0,
            name=name,
            comment=meta_info.get_comment(),
        )
        return self._dircache_add_entry_int(r, update_myself)

    def _dircache_add_entry_int(self, r, update_myself=True):
        r_bytes = r.get_size()
        # find a dircache block with enough space
        found_blk = None
        for dcb in self.dcache_blks:
            free_bytes = dcb.get_free_record_size()
            if r_bytes < free_bytes:
                found_blk = dcb
                break
        # need to create a new one?
        if found_blk == None:
            found_blk = self._dircache_add_block(update_myself)
            if found_blk == None:
                return False
        # add record to block and update it
        found_blk.add_record(r)
        found_blk.write()
        return True

    def _dircache_add_block(self, update_myself):
        # allocate block
        blk_nums = self.volume.bitmap.alloc_n(1)
        if blk_nums == None:
            return None
        # setup dir cache block
        dcb_num = blk_nums[0]
        dcb = DirCacheBlock(self.blkdev, dcb_num)
        dcb.create(parent=self.block.blk_num)
        # link new cache block
        if len(self.dcache_blks) == 0:
            self.block.extension = dcb_num
            if update_myself:
                self.block.write()
        else:
            last_dcb = self.dcache_blks[-1]
            last_dcb.next_cache = dcb_num
            last_dcb.write()
        self.dcache_blks.append(dcb)
        return dcb

    def _dircache_remove_entry(self, name, update_myself=True):
        # first find entry
        pos = None
        dcb = None
        record = None
        n = len(self.dcache_blks)
        for i in range(n):
            dcb = self.dcache_blks[i]
            record = dcb.get_record_by_name(name)
            if record != None:
                pos = i
                break
        if record == None:
            raise FSError(INTERNAL_ERROR, node=self, extra="no dc record!")
        # remove entry from this block
        dcb.remove_record(record)
        # remove whole block? (but keep at least one)
        if dcb.is_empty() and len(self.dcache_blks) > 1:
            # next block following me
            if pos == n - 1:
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
            # free cache block in bitmap
            blk_num = dcb.blk_num
            self.volume.bitmap.dealloc_n([blk_num])
            return blk_num  # return number of just deleted block
        else:
            # update cache block with reduced set of records
            dcb.write()
            return None

    def get_dircache_record(self, name):
        if self.dcache_blks:
            for dcb in self.dcache_blks:
                record = dcb.get_record_by_name(name)
                if record:
                    return record
        return None

    def update_dircache_record(self, record, rebuild):
        if self.dcache_blks == None:
            return
        # update record
        if rebuild:
            self._dircache_remove_entry(record.name, update_myself=False)
            self._dircache_add_entry_int(record, update_myself=True)
        else:
            # simply re-write the dircache block
            for dcb in self.dcache_blks:
                if dcb.has_record(record):
                    dcb.write()
                    break

    def get_block_usage(self, all=False, first=True):
        num_non_data = 1
        num_data = 0
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
