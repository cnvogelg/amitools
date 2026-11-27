"""Files, directories and links of a PFS3 volume, with the interface of
ADFSNode and its subclasses"""

from amitools.fs.FileName import FileName
from amitools.fs.FSError import (
    DELETE_NOT_ALLOWED,
    FILE_NOT_FOUND,
    FSError,
    INTERNAL_ERROR,
    INVALID_FILE_NAME,
    LINK_NOT_ALLOWED,
    NO_FREE_BLOCKS,
    UNSUPPORTED_DIR_BLOCK,
    UNSUPPORTED_OPERATION,
)
from amitools.fs.FSString import FSString
from amitools.fs.MetaInfo import MetaInfo
from amitools.fs.ProtectFlags import ProtectFlags
from amitools.fs.TimeStamp import TimeStamp
import amitools.util.ByteSize as ByteSize

from .Const import (
    ANODE_ROOTDIR,
    ST_FILE,
    ST_LINKDIR,
    ST_LINKFILE,
    ST_ROLLOVERFILE,
    ST_SOFTLINK,
    ST_USERDIR,
    TYPE_NAMES,
)
from .DirEntry import DirEntry, name_upper
from .Disk import amiga_now

# protection bit cleared when an object changes
FIBF_ARCHIVE = 0x10


def ts_from_date(date):
    return TimeStamp(*date)


def date_from_ts(ts):
    return (ts.days, ts.mins, ts.ticks)


def fs_name(name):
    return FileName(FSString(name, encoding="Latin-1"), is_intl=True, is_longname=True)


def entry_meta_info(entry):
    return MetaInfo(
        entry.get_protect32(),
        ts_from_date(entry.date),
        FSString(entry.comment) if entry.comment else None,
        owner_uid=entry.uid,
        owner_gid=entry.gid,
    )


class PFS3Node:
    """an entry of a directory, or the root directory"""

    def __init__(self, volume, parent, entry=None):
        self.volume = volume
        self.disk = volume.disk
        self.blkdev = volume.blkdev
        self.block_bytes = volume.disk.B
        self.parent = parent
        self.entry = entry
        self.valid = True
        if entry is not None:
            self.anode = entry.anode
            self.name = fs_name(entry.name)
            self.meta_info = entry_meta_info(entry)

    def __repr__(self):
        return "%s(%r@%d)" % (
            self.__class__.__name__,
            self.name.get_unicode_name(),
            self.anode,
        )

    def __str__(self):
        return "%s:'%s'(anode %d)" % (
            self.__class__.__name__,
            self.get_node_path_name().get_unicode(),
            self.anode,
        )

    # ----- entry -----

    def _find_entry(self):
        """(res, offset, entry) of my entry in my parent's directory: by my
        anode, or by my name if a hard link took the place of what I was"""
        found = self.disk.find_entry(self.parent.anode, self.anode)
        if found is None and self.entry is not None:
            found = self.disk.find_name(self.parent.anode, self.entry.name)
        if found is None:
            raise FSError(
                INTERNAL_ERROR, node=self, extra="PFS3: entry not found in parent"
            )
        return found

    def _set_entry(self, entry):
        self.entry = entry
        self.name = fs_name(entry.name)
        self.meta_info = entry_meta_info(entry)

    # ----- query -----

    def get_file_name(self):
        return self.name

    def get_meta_info(self):
        return self.meta_info

    def get_size(self):
        return 0

    def get_size_str(self):
        return ""

    def get_detail_str(self):
        return "anode=%d" % self.anode

    def is_file(self):
        return False

    def is_dir(self):
        return False

    def is_link(self):
        return False

    def is_rollover(self):
        return self.entry is not None and self.entry.type == ST_ROLLOVERFILE

    def flush(self):
        pass

    def get_node_path(self, with_vol=False):
        if self.parent is not None:
            if not with_vol and self.parent.parent is None:
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
        return FSString("/".join(self.get_node_path()))

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

    def get_block_usage(self, all=False, first=True):
        return (0, 0)

    def get_file_bytes(self, all=False, first=True):
        return 0

    def get_info(self, all=False):
        (data, fs) = self.get_block_usage(all=all)
        total = data + fs
        bb = self.block_bytes
        res = []
        res.append(
            "sum:    %10d  %s  %12d"
            % (total, ByteSize.to_byte_size_str(total * bb), total * bb)
        )
        prc_data = 10000 * data / total if total else 0
        res.append(
            "data:   %10d  %s  %12d  %5.2f%%"
            % (data, ByteSize.to_byte_size_str(data * bb), data * bb, prc_data / 100.0)
        )
        res.append(
            "fs:     %10d  %s  %12d  %5.2f%%"
            % (
                fs,
                ByteSize.to_byte_size_str(fs * bb),
                fs * bb,
                (10000 - prc_data) / 100.0 if total else 0,
            )
        )
        return res

    def get_blocks(self, with_data=False):
        return []

    def dump_blocks(self, with_data=False):
        e = self.entry
        print("PFS3 entry '%s'" % self.name.get_unicode_name())
        if e is not None:
            print(" type:        %s (%d)" % (TYPE_NAMES.get(e.type, "?"), e.type))
            print(" anode:       %d" % e.anode)
            print(" fsize:       %d (fsizex %d)" % (e.fsize, e.fsizex))
            print(" protection:  0x%08x" % e.get_protect32())
            print(" date:        %s" % ts_from_date(e.date))
            print(" comment:     %r" % e.comment)
            print(" link:        %d" % e.link)
            print(" uid/gid:     %d/%d" % (e.uid, e.gid))
            if e.type == ST_ROLLOVERFILE:
                print(" virtualsize: %d" % e.virtualsize)
                print(" rollpointer: %d" % e.rollpointer)
        if not self.is_link():
            print(" anodes:")
            for nr, cs, bn, nx in self.disk.get_chain(self.anode):
                print("  #%d: clustersize=%d blocknr=%d next=%d" % (nr, cs, bn, nx))

    def draw_on_bitmap(self, bm, show_all=False, first=True):
        raise FSError(INTERNAL_ERROR, node=self, extra="PFS3: no bitmap drawing")

    # ----- change -----

    def change_meta_info(self, meta_info):
        comment = meta_info.get_comment()
        if comment is not None:
            comment_bytes = self.volume.check_comment(comment, node=self)
        protect = meta_info.get_protect()
        mod_ts = meta_info.get_mod_ts()
        owner = None
        if meta_info.has_owner():
            owner = self.volume.check_owner(
                meta_info.get_owner_uid(), meta_info.get_owner_gid(), node=self
            )
        if protect is None and mod_ts is None and comment is None and owner is None:
            return

        def change():
            res, off, e = self._find_entry()
            e = e.copy()
            if protect is not None:
                e.set_protect32(protect)
            if mod_ts is not None:
                e.date = date_from_ts(mod_ts)
            if comment is not None:
                e.comment = comment_bytes
            if owner is not None:
                e.uid, e.gid = owner
            self.disk.replace_entry(self.parent.anode, res, off, e)
            return e

        e = self.volume.modify(change, update_ts=False)
        self._set_entry(e)

    def change_comment(self, comment):
        self.change_meta_info(MetaInfo(comment=comment))

    def change_protect(self, protect):
        self.change_meta_info(MetaInfo(protect=protect))

    def change_protect_by_string(self, pr_str):
        if not pr_str:
            return
        p = ProtectFlags()
        p.parse(pr_str)
        self.change_protect(p.mask)

    def change_owner(self, uid, gid):
        """set the entry's user and group id (both 16-bit)"""
        self.change_meta_info(MetaInfo(owner_uid=uid, owner_gid=gid))

    def change_mod_ts(self, mod_ts):
        self.change_meta_info(MetaInfo(mod_ts=mod_ts))

    def change_mod_ts_by_string(self, tm_str):
        t = TimeStamp()
        if not t.parse(tm_str):
            return False
        self.change_meta_info(MetaInfo(mod_ts=t))
        return True

    # ----- delete -----

    def can_delete(self):
        return True

    def delete(self, wipe=False, all=False, update_ts=True):
        if self.parent is None:
            # the root stays, only its entries go
            if not all:
                raise FSError(DELETE_NOT_ALLOWED, node=self)
            self.volume.modify(lambda: self.delete_children(wipe, all, update_ts))
            return
        if all:
            self.parent.check_delete(self, all, update_ts)
        self.volume.modify(lambda: self._delete_tree(wipe, all, update_ts))

    def _delete_tree(self, wipe, all, update_ts):
        # a hard link may have taken the place of what I was
        node = self.parent.refresh_node(self)
        if all and node.is_dir():
            for entry in node.get_entries()[:]:
                entry._delete_tree(wipe, all, update_ts)
        node.parent._delete(node, wipe, update_ts)

    def delete_children(self, wipe, all, update_ts):
        pass


class PFS3File(PFS3Node):
    """a file or a rollover file"""

    def __init__(self, volume, parent, entry):
        PFS3Node.__init__(self, volume, parent, entry)
        self.data = None

    def is_file(self):
        return True

    def get_size(self):
        e = self.entry
        if e.type == ST_ROLLOVERFILE:
            return e.virtualsize
        return e.get_size(self.disk.is_largefile())

    def get_size_str(self):
        return "%8d" % self.get_size()

    def get_detail_str(self):
        blocks = self.disk.chain_block_count(self.anode)
        s = "anode=%d data=%d" % (self.anode, blocks)
        if self.entry.type == ST_ROLLOVERFILE:
            s += " rollover=%d" % self.entry.fsize
        if self.entry.link:
            s += " links"
        return s

    def get_file_data(self):
        if self.data is None:
            self.data = self._read_data()
        return self.data

    def _read_data(self):
        e = self.entry
        if e.type == ST_ROLLOVERFILE:
            phys = self.disk.read_chain_data(self.anode, e.fsize)
            if not e.fsize:
                return b""
            start = e.rollpointer % e.fsize
            data = phys[start:] + phys[:start]
            return data[: e.virtualsize]
        return self.disk.read_chain_data(self.anode, self.get_size())

    def ensure_data(self):
        self.get_file_data()

    def flush(self):
        self.data = None

    def get_block_usage(self, all=False, first=True):
        return (self.disk.chain_block_count(self.anode), 0)

    def get_file_bytes(self, all=False, first=True):
        return self.get_size()


class PFS3FileLink(PFS3File):
    """a hard link to a file: reads as the file it links to"""

    def is_link(self):
        return True

    def _target(self):
        return self.volume.resolve_link(self.entry)

    def get_size(self):
        target = self._target()
        if target is None:
            return 0
        if target.type == ST_ROLLOVERFILE:
            return target.virtualsize
        return target.get_size(self.disk.is_largefile())

    def get_detail_str(self):
        return "anode=%d link to anode %d" % (self.anode, self.entry.link)

    def get_link_target(self):
        """the name of the object the link names"""
        return self.volume.get_link_object_name(self)

    def _read_data(self):
        target = self._target()
        if target is None:
            raise FSError(FILE_NOT_FOUND, node=self, extra="PFS3: dangling hard link")
        if target.type in (ST_FILE, ST_ROLLOVERFILE):
            node = PFS3File(self.volume, self.parent, target)
            return node._read_data()
        raise FSError(UNSUPPORTED_DIR_BLOCK, node=self, extra="PFS3: link to no file")

    def get_block_usage(self, all=False, first=True):
        return (0, 0)


class PFS3SoftLink(PFS3Node):
    """a soft link: neither a file nor a directory"""

    def is_link(self):
        return True

    def get_target(self):
        """the path the link points to, as a FSString"""
        data = self.disk.read_chain_data(self.anode, self.entry.fsize)
        return FSString(data.split(b"\0", 1)[0])

    def get_link_target(self):
        return self.get_target()

    def get_size_str(self):
        return "SOFTLINK"

    def get_detail_str(self):
        return "-> %s" % self.get_target().get_unicode()

    def get_block_usage(self, all=False, first=True):
        return (self.disk.chain_block_count(self.anode), 0)


class PFS3DirLink(PFS3Node):
    """a hard link to a directory. It is not followed by listings and
    copies, which could loop"""

    def is_link(self):
        return True

    def get_size_str(self):
        return "DIRLINK"

    def get_detail_str(self):
        return "anode=%d link to anode %d" % (self.anode, self.entry.link)

    def get_link_target(self):
        """the name of the directory the link names"""
        return self.volume.get_link_object_name(self)

    def get_target_dir(self):
        target = self.volume.resolve_link(self.entry)
        if target is None or target.type != ST_USERDIR:
            return None
        return PFS3Dir(self.volume, self.parent, target)


class PFS3Dir(PFS3Node):
    def __init__(self, volume, parent, entry=None):
        PFS3Node.__init__(self, volume, parent, entry)
        self.entries = None
        self.entries_gen = None
        # Imager and Repacker look for entries that could not be read
        self.entry_bad_blk = None

    def is_dir(self):
        return True

    def get_size_str(self):
        return "DIR"

    def get_detail_str(self):
        self.ensure_entries()
        return "anode=%d entries=%d blocks=%d" % (
            self.anode,
            len(self.entries),
            len(self.disk.get_chain(self.anode)),
        )

    def refresh_node(self, node):
        """node, or a new node for its entry if a hard link took its place"""
        res, off, e = node._find_entry()
        if e.anode == node.anode and e.type == node.entry.type:
            return node
        return self._make_node(e)

    def _make_node(self, entry):
        t = entry.type
        if t == ST_USERDIR:
            return PFS3Dir(self.volume, self, entry)
        if t in (ST_FILE, ST_ROLLOVERFILE):
            return PFS3File(self.volume, self, entry)
        if t == ST_LINKFILE:
            return PFS3FileLink(self.volume, self, entry)
        if t == ST_SOFTLINK:
            return PFS3SoftLink(self.volume, self, entry)
        if t == ST_LINKDIR:
            return PFS3DirLink(self.volume, self, entry)
        raise FSError(UNSUPPORTED_DIR_BLOCK, node=self, extra="PFS3: entry type %d" % t)

    def read(self):
        self.entries_gen = self.volume.entries_gen
        self.entries = [
            self._make_node(e) for res, off, e in self.disk.dir_entries(self.anode)
        ]

    def ensure_entries(self):
        # a change of hard links can change the entries of any directory
        if self.entries is None or self.entries_gen != self.volume.entries_gen:
            self.read()

    def get_entries(self):
        self.ensure_entries()
        return self.entries

    def get_entries_sorted_by_name(self):
        self.ensure_entries()
        return sorted(self.entries, key=lambda x: name_upper(x.entry.name))

    def check_entries(self):
        pass

    def flush(self):
        if self.entries:
            for e in self.entries:
                e.flush()
        self.entries = None

    def list(self, indent=0, all=False, detail=False, encoding="UTF-8"):
        PFS3Node.list(self, indent, all, detail, encoding)
        if not all and indent > 0:
            return
        for e in self.get_entries_sorted_by_name():
            e.list(indent=indent + 1, all=all, detail=detail, encoding=encoding)

    def get_path(self, pc, allow_file=True, allow_dir=True):
        if len(pc) == 0:
            return self
        if not isinstance(pc[0], FileName):
            raise ValueError("get_path's pc must be a FileName array")
        want = name_upper(pc[0].get_ami_str_name())
        for e in self.get_entries():
            if name_upper(e.entry.name) != want:
                continue
            if len(pc) > 1:
                if isinstance(e, PFS3DirLink):
                    e = e.get_target_dir()
                if isinstance(e, PFS3Dir):
                    return e.get_path(pc[1:], allow_file, allow_dir)
                return None
            if e.is_dir():
                return e if allow_dir else None
            if e.is_file():
                return e if allow_file else None
            # a link that is no file: only for operations on any entry
            return e if (allow_file and allow_dir) else None
        return None

    def get_block_usage(self, all=False, first=True):
        num_data = 0
        num_fs = len(self.disk.get_chain(self.anode)) * self.disk.rescluster
        if all or first:
            for e in self.get_entries():
                d, f = e.get_block_usage(all=all, first=False)
                num_data += d
                num_fs += f
        return (num_data, num_fs)

    def get_file_bytes(self, all=False, first=True):
        size = 0
        if all or first:
            for e in self.get_entries():
                size += e.get_file_bytes(all=all, first=False)
        return size

    # ----- create -----

    def _new_entry(self, name, type, anode, size, meta_info):
        ami_name = self.volume.check_new_name(self, name)
        protect = 0
        date = None
        comment = b""
        if meta_info is not None:
            if meta_info.get_protect() is not None:
                protect = meta_info.get_protect()
            if meta_info.get_mod_ts() is not None:
                date = date_from_ts(meta_info.get_mod_ts())
            if meta_info.get_comment() is not None:
                comment = self.volume.check_comment(meta_info.get_comment())
        if date is None:
            date = amiga_now()
        e = DirEntry(
            type=type,
            anode=anode,
            date=date,
            name=ami_name,
            comment=comment,
            has_extra=self.disk.has_dir_extension(),
        )
        e.set_size(size)
        e.set_protect32(protect)
        if (
            meta_info is not None
            and meta_info.has_owner()
            and self.disk.has_dir_extension()
        ):
            e.uid, e.gid = self.volume.check_owner(
                meta_info.get_owner_uid(), meta_info.get_owner_gid()
            )
        return e

    def _touch(self):
        """my contents changed: a new date and no archive bit"""
        e = self.volume.touch_dir(self.anode)
        if e is None:
            self.meta_info.set_mod_ts(ts_from_date(self.disk.get_root_date()))
        else:
            self._set_entry(e)

    def _check_new(self, name, meta_info):
        if not isinstance(name, FSString):
            raise ValueError("name must be a FSString")
        ami_name = self.volume.check_new_name(self, name)
        if meta_info is not None and meta_info.get_comment() is not None:
            self.volume.check_comment(meta_info.get_comment())
        return ami_name

    def create_dir(self, name, meta_info=None, update_ts=True):
        self._check_new(name, meta_info)

        def create():
            anode = self.disk.create_dir_chain(self.anode)
            e = self._new_entry(name, ST_USERDIR, anode, 0, meta_info)
            self.disk.add_entry(self.anode, e)
            if update_ts:
                self._touch()
            return e

        e = self.volume.modify(create, update_ts=update_ts)
        node = PFS3Dir(self.volume, self, e)
        if self.entries is not None:
            self.entries.append(node)
        return node

    def create_file(self, name, data, meta_info=None, update_ts=True):
        self._check_new(name, meta_info)
        if len(data) > self.disk.get_max_file_size():
            raise FSError(
                NO_FREE_BLOCKS, node=self, extra="PFS3: file too large: %d" % len(data)
            )

        def create():
            anode = self.disk.create_chain(data)
            e = self._new_entry(name, ST_FILE, anode, len(data), meta_info)
            self.disk.add_entry(self.anode, e)
            if update_ts:
                self._touch()
            return e

        e = self.volume.modify(create, update_ts=update_ts)
        node = PFS3File(self.volume, self, e)
        if self.entries is not None:
            self.entries.append(node)
        return node

    def create_soft_link(self, name, target, meta_info=None, update_ts=True):
        """a soft link named name to the path target. Its block holds the
        path, so the path must be shorter than a block"""
        if not isinstance(target, FSString):
            raise ValueError("create_soft_link's target must be a FSString")
        self._check_new(name, meta_info)
        try:
            path = target.get_ami_str()
        except UnicodeEncodeError:
            raise FSError(
                INVALID_FILE_NAME, file_name=target, extra="not Latin-1"
            ) from None
        if b"\0" in path or len(path) >= self.disk.B:
            raise FSError(
                INVALID_FILE_NAME,
                file_name=target,
                extra="PFS3: soft link targets are shorter than %d bytes" % self.disk.B,
            )

        def create():
            anode = self.disk.create_chain(path + b"\0")
            e = self._new_entry(name, ST_SOFTLINK, anode, len(path), meta_info)
            self.disk.add_entry(self.anode, e)
            if update_ts:
                self._touch()
            return e

        e = self.volume.modify(create, update_ts=update_ts)
        node = PFS3SoftLink(self.volume, self, e)
        if self.entries is not None:
            self.entries.append(node)
        return node

    def create_hard_link(self, name, target_node, meta_info=None, update_ts=True):
        """a hard link named name to the file, rollover file or directory of
        target_node. A link given as target_node links to its object, as a
        lock on a link is one on its object. Soft links can not be locked,
        so the handler makes no hard links to them, and neither do I"""
        if not isinstance(target_node, PFS3Node) or target_node.volume is not (
            self.volume
        ):
            raise ValueError("create_hard_link's target must be a node of my volume")
        if target_node.parent is None:
            raise FSError(LINK_NOT_ALLOWED, node=target_node, extra="the root")
        if not self.disk.has_dir_extension():
            raise FSError(
                UNSUPPORTED_OPERATION,
                node=self,
                extra="PFS3: hard links need the directory extension",
            )
        self._check_new(name, meta_info)
        disk = self.disk

        def create():
            obj_dir, obj = self.volume.find_link_object(target_node)
            if obj.type not in (ST_FILE, ST_ROLLOVERFILE, ST_USERDIR):
                raise FSError(LINK_NOT_ALLOWED, node=target_node)
            node_nr = disk.alloc_anode()
            link_type = ST_LINKDIR if obj.type == ST_USERDIR else ST_LINKFILE
            e = self._new_entry(name, link_type, node_nr, 0, meta_info)
            e.fsize = obj.fsize
            e.link = obj.anode
            disk.add_entry(self.anode, e)
            if obj.link:
                # a later link goes right after the first one
                cs, bn, nx = disk.get_anode(obj.link)
                disk.set_anode(node_nr, obj_dir, self.anode, nx)
                disk.set_anode(obj.link, cs, bn, node_nr)
            else:
                disk.set_anode(node_nr, obj_dir, self.anode, 0)
                res, off, obj = disk.find_entry(obj_dir, obj.anode)
                obj = obj.copy()
                obj.link = node_nr
                disk.replace_entry(obj_dir, res, off, obj)
                if update_ts:
                    self.volume.touch_dir(obj_dir)
            if update_ts:
                self._touch()
            self.volume.entries_gen += 1
            return e

        e = self.volume.modify(create, update_ts=update_ts)
        return self._make_node(e)

    def rename_node(self, node, new_name):
        """move node into this directory under new_name. Its links follow
        it, and a directory gets me as its parent"""
        if not isinstance(new_name, FSString):
            raise ValueError("rename_node's new_name must be a FSString")
        if node.parent is None:
            raise FSError(DELETE_NOT_ALLOWED, node=node)
        volume = self.volume
        disk = self.disk
        ami_name = volume.check_name(new_name)
        src_dir = node.parent.anode
        if src_dir == self.anode and node._find_entry()[2].name == ami_name:
            # the same object under exactly the same name
            return

        def change():
            res, off, e = node._find_entry()
            volume.check_new_name(self, new_name, ignore_anode=e.anode)
            if e.type == ST_USERDIR and src_dir != self.anode:
                volume.check_not_inside(self.anode, e.anode, new_name)
            new = e.copy()
            new.name = ami_name
            if src_dir == self.anode:
                disk.replace_entry(src_dir, res, off, new)
            else:
                disk.add_entry(self.anode, new)
                res, off, _ = disk.find_entry(src_dir, e.anode)
                disk.remove_entry(src_dir, res, off)
                volume.move_links(new, self.anode)
                if new.type == ST_USERDIR:
                    disk.set_dir_parent(new.anode, self.anode)
                volume.touch_dir(src_dir)
            self._touch()
            volume.entries_gen += 1
            return new

        new = volume.modify(change)
        node.parent = self
        node._set_entry(new)

    # ----- delete -----

    def can_delete(self):
        return len(self.get_entries()) == 0

    def check_delete(self, node, all=False, update_ts=True):
        """refuse to delete node before anything is written"""
        if node.parent is not self or not any(
            e.anode == node.anode for e in self.get_entries()
        ):
            raise FSError(INTERNAL_ERROR, node=node, extra="node is not my entry")
        if node.is_dir():
            if all:
                for entry in node.get_entries():
                    node.check_delete(entry, all, update_ts)
            elif not node.can_delete():
                raise FSError(DELETE_NOT_ALLOWED, node=node)

    def delete_children(self, wipe, all, update_ts):
        if all:
            for e in self.get_entries():
                self.check_delete(e, all, update_ts)
        for e in self.get_entries()[:]:
            e._delete_tree(wipe, all, update_ts)

    def _delete(self, node, wipe, update_ts):
        """remove the entry of node. Runs inside a modification. What it
        holds is taken from the entry on disk, not from the node, which a
        hard link may have replaced"""
        if node.parent is not self:
            raise FSError(INTERNAL_ERROR, node=node, extra="node parent is not me")
        disk = self.disk
        res, off, e = node._find_entry()
        if e.type == ST_USERDIR and disk.dir_entries(e.anode):
            raise FSError(DELETE_NOT_ALLOWED, node=node)
        if e.is_link():
            self.volume.unlink_hard_link(self.anode, e)
            res, off, e = node._find_entry()
            disk.remove_entry(self.anode, res, off)
        elif e.link:
            # others link to it: the first link takes its place
            self.volume.promote_link(self.anode, e)
        else:
            disk.remove_entry(self.anode, res, off)
            if e.type == ST_USERDIR:
                disk.free_dir_chain(e.anode)
            else:
                disk.free_chain(e.anode, wipe=wipe)
        if update_ts:
            self._touch()
        if self.entries is not None and node in self.entries:
            self.entries.remove(node)


class PFS3VolDir(PFS3Dir):
    """the root directory"""

    def __init__(self, volume):
        PFS3Dir.__init__(self, volume, None)
        self.anode = ANODE_ROOTDIR
        self.name = FileName(volume.name, is_intl=True, is_longname=True)
        self.meta_info = MetaInfo(mod_ts=ts_from_date(volume.disk.get_root_date()))

    def __repr__(self):
        return "PFS3VolDir(%r)" % self.name.get_unicode_name()

    def get_size_str(self):
        return "VOLUME"

    def can_delete(self):
        return False

    def change_owner(self, uid, gid):
        raise FSError(
            UNSUPPORTED_OPERATION, node=self, extra="PFS3: the root has no owner"
        )

    def change_meta_info(self, meta_info):
        """only a date: the root has no protection, comment or owner"""
        mod_ts = meta_info.get_mod_ts()
        if mod_ts is None:
            return

        def change():
            self.disk.set_root_date(date_from_ts(mod_ts))

        self.volume.modify(change, update_ts=False)
        self.meta_info.set_mod_ts(mod_ts)
        self.volume.update_meta_info()

    def get_list_str(self, indent=0, all=False, detail=False):
        a = PFS3Dir.get_list_str(self, indent=indent, all=all, detail=detail)
        return a + self.volume.get_dos_type_str() + " #%d" % self.block_bytes

    def dump_blocks(self, with_data=False):
        print("PFS3 root directory")
        for nr, cs, bn, nx in self.disk.get_chain(self.anode):
            print("  #%d: clustersize=%d blocknr=%d next=%d" % (nr, cs, bn, nx))
