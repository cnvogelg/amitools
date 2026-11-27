"""A PFS3 volume with the interface of ADFSVolume"""

import struct

from amitools.fs.FileName import FileName
from amitools.fs.FSError import (
    DELETE_NOT_ALLOWED,
    FILE_NOT_FOUND,
    FSError,
    INVALID_ANODE,
    INVALID_BOOT_BLOCK,
    INVALID_COMMENT,
    INVALID_FILE_NAME,
    INVALID_PARENT_DIRECTORY,
    INVALID_ROOT_BLOCK,
    INVALID_VOLUME_NAME,
    NAME_ALREADY_EXISTS,
    UNSUPPORTED_OPERATION,
)
from amitools.fs.FSString import FSString
from amitools.fs.RootMetaInfo import RootMetaInfo
from amitools.fs.TimeStamp import TimeStamp
import amitools.fs.DosType as DosType
import amitools.util.ByteSize as ByteSize

from .Const import (
    ANODE_ROOTDIR,
    BLOCK_ID_NAMES,
    DEFAULT_FNSIZE,
    DELDIR_NAME,
    ID_PFS1,
    ID_PFS2,
    ID_PFS3,
    MAX_COMMENT,
    MAX_VOLNAME,
    ST_USERDIR,
    is_pfs_dos_type,
)
from .DirEntry import name_upper
from .Disk import PFS3Disk, amiga_now, u16, u32
from .PFS3Node import FIBF_ARCHIVE, PFS3Node, PFS3VolDir, ts_from_date, date_from_ts


class PFS3BootInfo:
    """the boot blocks of a PFS3 volume: they hold its disk type, no code"""

    def __init__(self, volume):
        self.volume = volume
        self.dos_type = volume.disk.disktype
        self.boot_code = None
        self.valid = True

    def set_boot_code(self, boot_code):
        if boot_code:
            raise FSError(INVALID_BOOT_BLOCK, extra="PFS3 volumes hold no boot code")
        return True

    def write(self):
        pass

    def dump(self):
        print("PFS3 boot block: %s" % DosType.num_to_tag_str(self.dos_type))


class PFS3RootInfo:
    """the root block of a PFS3 volume, for 'root show'"""

    def __init__(self, volume):
        self.volume = volume

    def dump(self):
        d = self.volume.disk
        print("PFS3 root block")
        print(" disktype:      %s" % DosType.num_to_tag_str(d.disktype))
        print(" options:       0x%08x" % d.options)
        print(" datestamp:     %d" % d.get_datestamp())
        print(" name:          %s" % self.volume.name.get_unicode())
        print(" created:       %s" % ts_from_date(d.get_creation_date()))
        print(" root date:     %s" % ts_from_date(d.get_root_date()))
        vd = d.get_volume_date()
        print(" volume date:   %s" % (ts_from_date(vd) if vd else "-"))
        print(" block size:    %d" % d.B)
        print(" reserved size: %d" % d.R)
        print(
            " reserved:      %d..%d (%d blocks, %d free)"
            % (
                d.firstreserved,
                d.lastreserved,
                d.numreserved,
                d._r32(0x3C),
            )
        )
        print(" rblkcluster:   %d" % d.rblkcluster)
        print(
            " blocks:        %d (%d free, %d always free)"
            % (
                d.numblocks,
                d.get_blocks_free(),
                d.get_always_free(),
            )
        )
        print(" supermode:     %s" % d.supermode)
        print(" largefile:     %s" % d.is_largefile())
        print(" fnsize:        %d" % d.get_fnsize())
        print(" deldir:        %d blocks" % d.get_deldir_size())
        if d.read_only_reason:
            print(" read-only:     %s" % d.read_only_reason)


class PFS3Volume:
    is_pfs3 = True
    # for code that looks at the flags of OFS/FFS volumes
    is_ffs = False
    is_intl = True
    is_dircache = False
    is_longname = True

    def __init__(self, blkdev):
        self.blkdev = blkdev
        self.disk = None
        self.boot = None
        self.root = None
        self.root_dir = None
        self.bitmap = None
        self.valid = False
        self.name = None
        self.meta_info = None
        self._depth = 0
        # raised when entries of directories change that are not the one
        # being changed: their nodes read their entries again
        self.entries_gen = 0

    # ----- open/create -----

    def open(self):
        self.disk = PFS3Disk(self.blkdev)
        self.disk.open()
        self._setup()

    def _setup(self):
        self.name = FSString(self.disk.get_volume_name())
        self.update_meta_info()
        self.boot = PFS3BootInfo(self)
        self.root = PFS3RootInfo(self)
        self.root_dir = PFS3VolDir(self)
        self.valid = True

    def update_meta_info(self):
        d = self.disk
        vd = d.get_volume_date()
        self.meta_info = RootMetaInfo(
            ts_from_date(d.get_creation_date()),
            ts_from_date(vd) if vd else None,
            ts_from_date(d.get_root_date()),
        )

    def create(
        self,
        name,
        meta_info=None,
        dos_type=None,
        boot_code=None,
        fnsize=DEFAULT_FNSIZE,
        largefile=False,
        numreserved=None,
        supermode=None,
        resblksize=None,
    ):
        """format the block device with an empty PFS3 volume. fnsize is the
        name size (names of up to fnsize - 1 characters), largefile allows
        files of 4 GiB and more. supermode and resblksize force a layout
        that the formatter only chooses for larger volumes"""
        if not isinstance(name, FSString):
            raise ValueError("create's name must be a FSString")
        if boot_code:
            raise FSError(INVALID_BOOT_BLOCK, extra="PFS3 volumes hold no boot code")
        ami_name = self._check_volume_name(name)
        disktype = None
        if dos_type == ID_PFS2:
            disktype = ID_PFS2
        elif dos_type is not None and not is_pfs_dos_type(dos_type):
            raise FSError(INVALID_ROOT_BLOCK, extra="no PFS3 dos type")
        date = amiga_now()
        root_date = None
        volume_date = None
        if meta_info is not None:
            if meta_info.get_create_ts() is not None:
                date = date_from_ts(meta_info.get_create_ts())
            if meta_info.get_mod_ts() is not None:
                root_date = date_from_ts(meta_info.get_mod_ts())
            if meta_info.get_disk_ts() is not None:
                volume_date = date_from_ts(meta_info.get_disk_ts())
        self.disk = PFS3Disk(self.blkdev)
        self.disk.format(
            ami_name,
            date=date,
            disktype=disktype,
            largefile=largefile,
            fnsize=fnsize,
            numreserved=numreserved,
            dos_type=ID_PFS3 if dos_type in (None, ID_PFS1) else dos_type,
            supermode=supermode,
            resblksize=resblksize,
        )
        if root_date is not None or volume_date is not None:
            if root_date is not None:
                self.disk.set_root_date(root_date)
            if volume_date is not None:
                self.disk.set_volume_date(volume_date)
            self.disk.commit(update_ts=False)
        self._setup()

    def close(self):
        # every change is committed when it is made. Only blocks whose free
        # could not be written yet are left
        if self.disk is not None and self.disk.is_dirty():
            self.disk.commit(update_ts=False)

    # ----- modifications -----

    def modify(self, fn, update_ts=True):
        """run fn, which changes the volume, and commit its changes. If fn
        or the commit fails, nothing of it reaches the disk"""
        self.disk.check_writable()
        self._depth += 1
        try:
            result = fn()
            if self._depth == 1:
                self.disk.commit(update_ts)
        except BaseException:
            if self._depth == 1:
                self.disk.rollback()
                self.entries_gen += 1
                self.update_meta_info()
            raise
        finally:
            self._depth -= 1
        return result

    # ----- checks -----

    def _check_volume_name(self, name):
        try:
            ami = name.get_ami_str()
        except UnicodeEncodeError:
            raise FSError(INVALID_VOLUME_NAME, file_name=name) from None
        if not 1 <= len(ami) <= MAX_VOLNAME or b":" in ami or b"/" in ami:
            raise FSError(INVALID_VOLUME_NAME, file_name=name)
        return ami

    def check_comment(self, comment, node=None):
        """the comment as bytes, if the volume can hold it"""
        try:
            ami = comment.get_ami_str()
        except UnicodeEncodeError:
            raise FSError(
                INVALID_COMMENT, node=node, file_name=comment, extra="not Latin-1"
            ) from None
        if len(ami) > MAX_COMMENT:
            raise FSError(
                INVALID_COMMENT,
                node=node,
                file_name=comment,
                extra="%d bytes, max %d" % (len(ami), MAX_COMMENT),
            )
        return ami

    def check_name(self, name):
        """the name as bytes, if it is a valid name for an entry"""
        try:
            ami = name.get_ami_str()
        except UnicodeEncodeError:
            raise FSError(
                INVALID_FILE_NAME, file_name=name, extra="not Latin-1"
            ) from None
        max_len = self.disk.get_max_name_len()
        if not ami or b":" in ami or b"/" in ami or b"\0" in ami:
            raise FSError(INVALID_FILE_NAME, file_name=name)
        if len(ami) > max_len:
            raise FSError(
                INVALID_FILE_NAME,
                file_name=name,
                extra="longer than %d characters" % max_len,
            )
        return ami

    def check_new_name(self, dir_node, name, ignore_anode=None):
        """the name as bytes, if an entry of that name can be added to
        dir_node. The entry of ignore_anode may hold the name already"""
        ami = self.check_name(name)
        if (
            dir_node.anode == ANODE_ROOTDIR
            and self.disk.deldir_enabled()
            and name_upper(ami) == name_upper(DELDIR_NAME)
        ):
            raise FSError(NAME_ALREADY_EXISTS, file_name=name, extra="reserved name")
        found = self.disk.find_name(dir_node.anode, ami)
        if found is not None and found[2].anode != ignore_anode:
            raise FSError(NAME_ALREADY_EXISTS, file_name=name)
        return ami

    def check_owner(self, uid, gid, node=None):
        """(uid, gid), if the volume can store them"""
        for v in (uid, gid):
            if not isinstance(v, int) or not 0 <= v <= 0xFFFF:
                raise ValueError("uid and gid must be in 0..65535")
        if not self.disk.has_dir_extension():
            raise FSError(
                UNSUPPORTED_OPERATION,
                node=node,
                extra="PFS3: owners need the directory extension",
            )
        return uid, gid

    def check_not_inside(self, dir_anode, moved_anode, name=None):
        """refuse to move directory moved_anode into dir_anode if that is
        moved_anode or inside it"""
        seen = set()
        nr = dir_anode
        while nr != ANODE_ROOTDIR:
            if nr == moved_anode:
                raise FSError(
                    INVALID_PARENT_DIRECTORY,
                    file_name=name,
                    extra="PFS3: a directory can not move into itself",
                )
            if nr in seen:
                raise FSError(INVALID_ANODE, extra="PFS3: directory parents loop")
            seen.add(nr)
            nr = self.disk.dir_parent(nr)

    def touch_dir(self, dir_anode):
        """the contents of directory dir_anode changed: give it a new date
        and clear its archive bit. Returns its new entry, None for the root.
        The entry is found through the parent of its dir blocks, so this
        works for directories reached through a hard link, too"""
        disk = self.disk
        now = amiga_now()
        if dir_anode == ANODE_ROOTDIR:
            disk.set_root_date(now)
            self.root_dir.meta_info.set_mod_ts(ts_from_date(now))
            return None
        parent = disk.dir_parent(dir_anode)
        found = disk.find_entry(parent, dir_anode)
        if found is None:
            raise FSError(INVALID_ANODE, extra="PFS3: directory not in its parent")
        res, off, e = found
        e = e.copy()
        e.date = now
        e.protection &= ~FIBF_ARCHIVE
        disk.replace_entry(parent, res, off, e)
        return e

    # ----- hard links -----

    def resolve_link(self, link):
        """the entry of the object a hard link entry links to, or None"""
        disk = self.disk
        obj_dir, link_dir, nx = disk.get_anode(link.anode)
        try:
            found = disk.find_entry(obj_dir, link.link)
        except FSError:
            return None
        return found[2] if found else None

    def unlink_hard_link(self, dir_anode, link):
        """take the link node of hard link entry link out of the list of its
        object and free it. The entry stays"""
        disk = self.disk
        self.entries_gen += 1
        node = link.anode
        obj_dir, _, node_next = disk.get_anode(node)
        try:
            found = disk.find_entry(obj_dir, link.link)
        except FSError:
            found = None
        if found is not None:
            res, off, obj = found
            if obj.link == node:
                obj = obj.copy()
                obj.link = node_next
                disk.replace_entry(obj_dir, res, off, obj)
            else:
                nr = obj.link
                seen = set()
                while nr and nr not in seen:
                    seen.add(nr)
                    cs, bn, nx = disk.get_anode(nr)
                    if nx == node:
                        disk.set_anode(nr, cs, bn, node_next)
                        break
                    nr = nx
        disk.free_anode(node)

    def promote_link(self, dir_anode, obj):
        """the object obj in directory dir_anode goes: its first hard link
        takes its place"""
        disk = self.disk
        self.entries_gen += 1
        head = obj.link
        _, link_dir, head_next = disk.get_anode(head)
        found = disk.find_entry(link_dir, head)
        if found is None:
            raise FSError(INVALID_ANODE, extra="PFS3: first hard link not found")
        new = found[2].copy()
        new.type = obj.type
        new.fsize = obj.fsize
        new.fsizex = obj.fsizex
        new.anode = obj.anode
        new.link = head_next
        new.virtualsize = obj.virtualsize
        new.rollpointer = obj.rollpointer
        disk.free_anode(head)
        res, off, _ = disk.find_entry(dir_anode, obj.anode)
        disk.remove_entry(dir_anode, res, off)
        res, off, _ = disk.find_entry(link_dir, head)
        disk.replace_entry(link_dir, res, off, new)
        # the other links point to the new directory of the object
        nr = head_next
        seen = set()
        while nr and nr not in seen:
            seen.add(nr)
            cs, bn, nx = disk.get_anode(nr)
            disk.set_anode(nr, link_dir, bn, nx)
            nr = nx
        if new.type == ST_USERDIR:
            disk.set_dir_parent(new.anode, link_dir)

    def _link_nodes(self, head):
        """the anode numbers of the link list from head"""
        out = []
        nr = head
        while nr and nr not in out:
            out.append(nr)
            nr = self.disk.get_anode(nr)[2]
        return out

    def move_links(self, entry, new_dir):
        """entry moved to directory new_dir: update the link nodes that
        name its directory"""
        disk = self.disk
        if not entry.link:
            return
        if entry.is_link():
            # a link: its own node names the directory of the link
            cs, bn, nx = disk.get_anode(entry.anode)
            disk.set_anode(entry.anode, cs, new_dir, nx)
        else:
            # an object with links: every node names the object's directory
            for nr in self._link_nodes(entry.link):
                cs, bn, nx = disk.get_anode(nr)
                disk.set_anode(nr, new_dir, bn, nx)

    def find_link_object(self, node):
        """(directory anode, entry) of the object a hard link to node links
        to: node's own entry, or its object if node is a hard link"""
        disk = self.disk
        res, off, e = node._find_entry()
        if e.is_link():
            obj_dir = disk.get_anode(e.anode)[0]
            found = disk.find_entry(obj_dir, e.link)
            if found is None:
                raise FSError(FILE_NOT_FOUND, node=node, extra="PFS3: dangling link")
            return obj_dir, found[2]
        if e.type == ST_USERDIR:
            # its dir blocks know its parent, even when reached through a link
            return disk.dir_parent(e.anode), e
        return node.parent.anode, e

    def get_link_object_name(self, node):
        """the name of the object hard link node links to"""
        target = self.resolve_link(node.entry)
        if target is None:
            raise FSError(FILE_NOT_FOUND, node=node, extra="PFS3: dangling link")
        return FSString(target.name, encoding="Latin-1")

    # ----- info -----

    def get_dos_type_str(self):
        return DosType.get_dos_type_str(self.disk.disktype)

    def get_info(self):
        total = self.get_total_blocks()
        free = self.get_free_blocks()
        used = total - free
        bb = self.disk.B
        prc_free = 10000 * free / total
        prc_used = 10000 - prc_free
        return [
            "total:  %10d  %s  %12d"
            % (total, ByteSize.to_byte_size_str(total * bb), total * bb),
            "used:   %10d  %s  %12d  %5.2f%%"
            % (used, ByteSize.to_byte_size_str(used * bb), used * bb, prc_used / 100.0),
            "free:   %10d  %s  %12d  %5.2f%%"
            % (free, ByteSize.to_byte_size_str(free * bb), free * bb, prc_free / 100.0),
        ]

    def check(self):
        """check the volume: a FsckResult"""
        from .Check import PFS3Check

        return PFS3Check(self.disk).run()

    def get_create_options(self):
        """the options to create() a volume like this one with"""
        return {"fnsize": self.disk.get_fnsize(), "largefile": self.disk.is_largefile()}

    def print_bitmap_info(self):
        d = self.disk
        print("PFS3 data area: blocks %d..%d" % (d.bitmapstart, d.numblocks - 1))
        print(" free:        %d" % d.get_blocks_free())
        print(" always free: %d" % d.get_always_free())
        print(" used:        %d" % (d.data_bits - d.get_blocks_free()))
        print("PFS3 reserved area: blocks %d..%d" % (d.firstreserved, d.lastreserved))
        print(" reserved blocks: %d of %d bytes" % (d.numreserved, d.R))
        print(" free:            %d" % d._r32(0x3C))

    def decode_block(self, blocknr):
        """print what a block of the volume holds"""
        d = self.disk
        if not d.firstreserved <= blocknr <= d.lastreserved:
            if blocknr < d.firstreserved:
                print("block %d: boot block" % blocknr)
            else:
                print("block %d: data block" % blocknr)
            return
        if blocknr < d.firstreserved + d.rblkcluster:
            print("block %d: root block cluster" % blocknr)
            self.root.dump()
            return
        if (blocknr - d.firstreserved) % d.rescluster:
            print("block %d: inside a reserved block" % blocknr)
            return
        data = d.io.read(blocknr, d.rescluster)
        bid = u16(data, 0)
        kind = BLOCK_ID_NAMES.get(bid)
        state = "free" if d.is_res_free(blocknr) else "in use"
        if kind is None:
            print(
                "block %d: reserved block (%s), unknown id 0x%04x"
                % (blocknr, state, bid)
            )
            return
        print("block %d: %s block (%s)" % (blocknr, kind, state))
        if kind == "EX":
            print(" datestamp: %d" % u32(data, 8))
            return
        print(" datestamp: %d" % u32(data, 4))
        if kind == "DB":
            print(" directory: %d  parent: %d" % (u32(data, 12), u32(data, 16)))
            from .Disk import Res

            entries, _ = d.block_entries(Res("DB", blocknr, blocknr, bytearray(data)))
            for off, e in entries:
                print("  @%d %r" % (off, e))
            return
        print(" seqnr:     %d" % u32(data, 8))
        if kind in ("MI", "IB", "SB"):
            for j in range(d.ipb):
                v = u32(data, 12 + 4 * j)
                if v:
                    print("  [%d] -> %d" % (j, v))
        elif kind == "AB":
            for off in range(d.apb):
                cs, bn, nx = struct.unpack_from(">III", data, 16 + 12 * off)
                if cs or bn or nx:
                    nr = d.anode_nr(u32(data, 8), off)
                    print("  #%d: (%d, %d, %d)" % (nr, cs, bn, nx))
        elif kind == "BM":
            free = sum(bin(u32(data, 12 + 4 * j)).count("1") for j in range(d.lpb))
            print(" free bits: %d" % free)

    # ----- paths -----

    def _file_name(self, path_name):
        if not isinstance(path_name, FSString):
            raise ValueError("path must be a FSString")
        fn = FileName(path_name, is_intl=True, is_longname=True)
        if not fn.is_valid():
            raise FSError(INVALID_FILE_NAME, file_name=path_name, node=self)
        return fn

    def get_path_name(self, path_name, allow_file=True, allow_dir=True):
        fn = self._file_name(path_name)
        if fn.is_root_path_alias():
            return self.root_dir
        return self.root_dir.get_path(fn.split_path(), allow_file, allow_dir)

    def get_dir_path_name(self, path_name):
        return self.get_path_name(path_name, allow_file=False)

    def get_file_path_name(self, path_name):
        return self.get_path_name(path_name, allow_dir=False)

    def get_link_path_name(self, path_name):
        """the node of path_name itself, not of what a link there names.
        Paths never follow a link in their last part on PFS3"""
        return self.get_path_name(path_name)

    def _link_parent(self, ami_path):
        """(parent dir node, base name) for a new link at ami_path"""
        fn = self._file_name(ami_path)
        dir_name, base_name = fn.get_dir_and_base_name()
        if base_name is None:
            raise FSError(INVALID_FILE_NAME, file_name=ami_path)
        if dir_name is None:
            return self.root_dir, base_name
        node = self.get_dir_path_name(dir_name)
        if node is None:
            raise FSError(
                INVALID_PARENT_DIRECTORY,
                file_name=ami_path,
                extra="not found: " + dir_name.get_unicode(),
            )
        return node, base_name

    def create_soft_link(self, ami_path, target):
        """create a soft link at ami_path pointing to the path target"""
        if not isinstance(ami_path, FSString):
            raise ValueError("create_soft_link's ami_path must be a FSString")
        if not isinstance(target, FSString):
            raise ValueError("create_soft_link's target must be a FSString")
        parent, name = self._link_parent(ami_path)
        return parent.create_soft_link(name, target)

    def create_hard_link(self, ami_path, target):
        """create a hard link at ami_path to target: a node or the path of
        a file, rollover file or directory"""
        if not isinstance(ami_path, FSString):
            raise ValueError("create_hard_link's ami_path must be a FSString")
        if isinstance(target, FSString):
            node = self.get_path_name(target)
            if node is None:
                raise FSError(FILE_NOT_FOUND, file_name=target)
        elif isinstance(target, PFS3Node):
            node = target
        else:
            raise ValueError("create_hard_link's target must be a node or FSString")
        parent, name = self._link_parent(ami_path)
        return parent.create_hard_link(name, node)

    def rename(self, old_ami_path, new_ami_path):
        """rename or move the object at old_ami_path to new_ami_path"""
        if not isinstance(old_ami_path, FSString):
            raise ValueError("rename's old_ami_path must be a FSString")
        if not isinstance(new_ami_path, FSString):
            raise ValueError("rename's new_ami_path must be a FSString")
        node = self.get_path_name(old_ami_path)
        if node is None:
            raise FSError(FILE_NOT_FOUND, file_name=old_ami_path)
        if node.parent is None:
            raise FSError(DELETE_NOT_ALLOWED, node=node)
        parent_node, new_name = self.get_create_path_name(new_ami_path)
        if parent_node is None:
            raise FSError(INVALID_PARENT_DIRECTORY, file_name=new_ami_path)
        if new_name is None:
            raise FSError(NAME_ALREADY_EXISTS, file_name=new_ami_path)
        parent_node.rename_node(node, new_name)

    def get_create_path_name(self, path_name, suggest_name=None):
        if not isinstance(path_name, FSString):
            raise ValueError("get_create_path_name's path_name must be a FSString")
        if suggest_name is not None and not isinstance(suggest_name, FSString):
            raise ValueError("get_create_path_name's suggest_name must be a FSString")
        fn = self._file_name(path_name)
        if fn.is_root_path_alias():
            return self.root_dir, suggest_name
        node = self.get_dir_path_name(path_name)
        if node is not None:
            return node, suggest_name
        dn, bn = fn.get_dir_and_base_name()
        node = self.get_dir_path_name(dn) if dn is not None else self.root_dir
        return node, (bn if bn is not None else suggest_name)

    # ----- convenience API -----

    def get_volume_name(self):
        return self.name

    def get_root_dir(self):
        return self.root_dir

    def get_dos_type(self):
        return self.disk.disktype

    def get_boot_code(self):
        return None

    def get_free_blocks(self):
        return self.disk.get_blocks_free()

    def get_used_blocks(self):
        return self.get_total_blocks() - self.get_free_blocks()

    def get_total_blocks(self):
        return self.disk.numblocks

    def get_meta_info(self):
        return self.meta_info

    def update_disk_time(self):
        mi = RootMetaInfo()
        mi.set_current_as_disk_time()
        self.change_meta_info(mi)

    def change_meta_info(self, meta_info):
        create_ts = meta_info.get_create_ts()
        disk_ts = meta_info.get_disk_ts()
        mod_ts = meta_info.get_mod_ts()
        if create_ts is None and disk_ts is None and mod_ts is None:
            return True

        def change():
            if create_ts is not None:
                self.disk.set_creation_date(date_from_ts(create_ts))
            if disk_ts is not None:
                self.disk.set_volume_date(date_from_ts(disk_ts))
            if mod_ts is not None:
                self.disk.set_root_date(date_from_ts(mod_ts))

        self.modify(change, update_ts=False)
        self.update_meta_info()
        self.root_dir.meta_info.set_mod_ts(self.meta_info.get_mod_ts())
        return True

    def change_create_ts(self, create_ts):
        return self.change_meta_info(RootMetaInfo(create_ts=create_ts))

    def change_disk_ts(self, disk_ts):
        return self.change_meta_info(RootMetaInfo(disk_ts=disk_ts))

    def change_mod_ts(self, mod_ts):
        return self.change_meta_info(RootMetaInfo(mod_ts=mod_ts))

    def _change_ts_by_string(self, s, **kw):
        t = TimeStamp()
        if not t.parse(s):
            return False
        key = list(kw)[0]
        return self.change_meta_info(RootMetaInfo(**{key: t}))

    def change_create_ts_by_string(self, s):
        return self._change_ts_by_string(s, create_ts=None)

    def change_disk_ts_by_string(self, s):
        return self._change_ts_by_string(s, disk_ts=None)

    def change_mod_ts_by_string(self, s):
        return self._change_ts_by_string(s, mod_ts=None)

    def relabel(self, name):
        if not isinstance(name, FSString):
            raise ValueError("relabel's name must be a FSString")
        ami = self._check_volume_name(name)
        self.modify(lambda: self.disk.set_volume_name(ami), update_ts=False)
        self.name = name
        self.root_dir.name = FileName(name, is_intl=True, is_longname=True)

    def create_dir(self, ami_path):
        if not isinstance(ami_path, FSString):
            raise ValueError("create_dir's ami_path must be a FSString")
        fn = self._file_name(ami_path)
        dir_name, base_name = fn.get_dir_and_base_name()
        if base_name is None:
            raise FSError(INVALID_FILE_NAME, file_name=ami_path)
        if dir_name is None:
            node = self.root_dir
        else:
            node = self.get_dir_path_name(dir_name)
            if node is None:
                raise FSError(
                    INVALID_PARENT_DIRECTORY,
                    file_name=ami_path,
                    extra="not found: " + dir_name.get_unicode(),
                )
        node.create_dir(base_name)

    def write_file(self, data, ami_path, suggest_name=None, cache=False):
        parent_node, file_name = self.get_create_path_name(ami_path, suggest_name)
        if parent_node is None:
            raise FSError(INVALID_PARENT_DIRECTORY, file_name=ami_path)
        if file_name is None:
            raise FSError(INVALID_FILE_NAME, file_name=ami_path)
        node = parent_node.create_file(file_name, data)
        if not cache:
            node.flush()

    def read_file(self, ami_path, cache=False):
        node = self.get_file_path_name(ami_path)
        if node is None:
            raise FSError(FILE_NOT_FOUND, file_name=ami_path)
        data = node.get_file_data()
        if not cache:
            node.flush()
        return data

    def delete(self, ami_path, wipe=False, all=False):
        node = self.get_path_name(ami_path)
        if node is None:
            raise FSError(FILE_NOT_FOUND, file_name=ami_path)
        node.delete(wipe=wipe, all=all)
