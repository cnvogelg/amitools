from .block.BootBlock import BootBlock
from .block.RootBlock import RootBlock
from .ADFSVolDir import ADFSVolDir
from .ADFSBitmap import ADFSBitmap
from .FileName import FileName
from .RootMetaInfo import RootMetaInfo
from .FSError import *
from .FSString import FSString
from .TimeStamp import TimeStamp
from . import DosType
import amitools.util.ByteSize as ByteSize


class ADFSVolume:
    def __init__(self, blkdev):
        self.blkdev = blkdev

        self.boot = None
        self.root = None
        self.root_dir = None
        self.bitmap = None

        self.valid = False
        self.is_ffs = None
        self.is_intl = None
        self.is_dircache = None
        self.is_longname = None
        self.name = None
        self.meta_info = None

    def open(self):
        # read boot block
        self.boot = BootBlock(self.blkdev)
        self.boot.read()
        # valid root block?
        if self.boot.valid:
            # get fs flags
            dos_type = self.boot.dos_type
            self.is_ffs = DosType.is_ffs(dos_type)
            self.is_intl = DosType.is_intl(dos_type)
            self.is_dircache = DosType.is_dircache(dos_type)
            self.is_longname = DosType.is_longname(dos_type)
            # read root
            self.root = RootBlock(self.blkdev, self.boot.calc_root_blk)
            self.root.read()
            if self.root.valid:
                self.name = self.root.name
                # build meta info
                self.meta_info = RootMetaInfo(
                    self.root.create_ts, self.root.disk_ts, self.root.mod_ts
                )
                # create root dir
                self.root_dir = ADFSVolDir(self, self.root)
                self.root_dir.read()
                # create bitmap
                self.bitmap = ADFSBitmap(self.root)
                self.bitmap.read()
                self.valid = True
            else:
                raise FSError(INVALID_ROOT_BLOCK, block=self.root)
        else:
            raise FSError(INVALID_BOOT_BLOCK, block=self.boot)

    def create(
        self,
        name,
        meta_info=None,
        dos_type=None,
        boot_code=None,
        is_ffs=False,
        is_intl=False,
        is_dircache=False,
        is_longname=False,
    ):
        # determine dos_type
        if dos_type == None:
            dos_type = DosType.DOS0
            if is_longname:
                dos_type = DosType.DOS6
            elif is_dircache:
                dos_type |= DosType.DOS_MASK_DIRCACHE
            elif is_intl:
                dos_type |= DosType.DOS_MASK_INTL
            if is_ffs:
                dos_type |= DosType.DOS_MASK_FFS
        # update flags
        self.is_ffs = DosType.is_ffs(dos_type)
        self.is_intl = DosType.is_intl(dos_type)
        self.is_dircache = DosType.is_dircache(dos_type)
        self.is_longname = DosType.is_longname(dos_type)
        # convert and check volume name
        if not isinstance(name, FSString):
            raise ValueError("create's name must be a FSString")
        fn = FileName(
            name, is_intl=self.is_intl, is_longname=False
        )  # Volumes don't support long names
        if not fn.is_valid():
            raise FSError(INVALID_VOLUME_NAME, file_name=name, node=self)
        # create a boot block
        self.boot = BootBlock(self.blkdev)
        self.boot.create(dos_type=dos_type, boot_code=boot_code)
        self.boot.write()
        # create a root block
        self.root = RootBlock(self.blkdev, self.boot.calc_root_blk)
        if meta_info == None:
            meta_info = RootMetaInfo()
            meta_info.set_current_as_create_time()
            meta_info.set_current_as_mod_time()
            meta_info.set_current_as_disk_time()
        create_ts = meta_info.get_create_ts()
        disk_ts = meta_info.get_disk_ts()
        mod_ts = meta_info.get_mod_ts()
        self.meta_info = meta_info
        self.root.create(fn.get_name(), create_ts, disk_ts, mod_ts, fstype=dos_type)
        self.name = name
        # create bitmap
        self.bitmap = ADFSBitmap(self.root)
        self.bitmap.create()
        self.bitmap.write()  # writes root block, too
        # create empty root dir
        self.root_dir = ADFSVolDir(self, self.root)
        self.root_dir.create_extra_blks()
        self.root_dir.read()
        # all ok
        self.valid = True

    def close(self):
        # flush bitmap state (if it was dirty)
        if self.bitmap:
            self.bitmap.write()

    def get_info(self):
        """return an array of strings with information on the volume"""
        res = []
        total = self.get_total_blocks()
        free = self.get_free_blocks()
        used = total - free
        bb = self.blkdev.block_bytes
        btotal = total * bb
        bfree = free * bb
        bused = used * bb
        prc_free = 10000 * free / total
        prc_used = 10000 - prc_free
        res.append(
            "total:  %10d  %s  %12d"
            % (total, ByteSize.to_byte_size_str(btotal), btotal)
        )
        res.append(
            "used:   %10d  %s  %12d  %5.2f%%"
            % (used, ByteSize.to_byte_size_str(bused), bused, prc_used / 100.0)
        )
        res.append(
            "free:   %10d  %s  %12d  %5.2f%%"
            % (free, ByteSize.to_byte_size_str(bfree), bfree, prc_free / 100.0)
        )
        return res

    # ----- Path Queries -----

    def get_path_name(self, path_name, allow_file=True, allow_dir=True):
        """get node for given path"""
        # make sure path name is a FSString
        if not isinstance(path_name, FSString):
            raise ValueError("get_path_name's path must be a FSString")
        # create and check file name
        fn = FileName(path_name, is_intl=self.is_intl, is_longname=self.is_longname)
        if not fn.is_valid():
            raise FSError(INVALID_FILE_NAME, file_name=path_name, node=self)
        # find node
        if fn.is_root_path_alias():
            # its the root node
            return self.root_dir
        else:
            # find a sub node
            path = fn.split_path()
            return self.root_dir.get_path(path, allow_file, allow_dir)

    def get_dir_path_name(self, path_name):
        """get node for given path and ensure its a directory"""
        return self.get_path_name(path_name, allow_file=False)

    def get_file_path_name(self, path_name):
        """get node for given path and ensure its a file"""
        return self.get_path_name(path_name, allow_dir=False)

    def get_create_path_name(self, path_name, suggest_name=None):
        """get a parent node and path name for creation
        return: parent_node_or_none, file_name_or_none
        """
        # make sure input is correct
        if not isinstance(path_name, FSString):
            raise ValueError("get_create_path_name's path_name must be a FSString")
        if suggest_name != None and not isinstance(suggest_name, FSString):
            raise ValueError("get_create_path_name's suggest_name must be a FSString")
        # is root path?
        fn = FileName(path_name, is_intl=self.is_intl, is_longname=self.is_longname)
        if not fn.is_valid():
            raise FSError(INVALID_FILE_NAME, file_name=path_name, node=self)
        # find node
        if fn.is_root_path_alias():
            return self.root_dir, suggest_name
        else:
            # try to get path_name as a directory
            node = self.get_dir_path_name(path_name)
            if node != None:
                return node, suggest_name
            else:
                # split into dir and file name
                dn, fn = fn.get_dir_and_base_name()
                if dn != None:
                    # has a directory -> try to fetch it
                    node = self.get_dir_path_name(dn)
                else:
                    # no dir -> assume root dir
                    node = self.root_dir
                if fn != None:
                    # take given name
                    return node, fn
                else:
                    # use suggested name
                    return node, suggest_name

    # ----- convenience API -----

    def get_volume_name(self):
        return self.name

    def get_root_dir(self):
        return self.root_dir

    def get_dos_type(self):
        return self.boot.dos_type

    def get_boot_code(self):
        return self.boot.boot_code

    def get_free_blocks(self):
        return self.bitmap.get_num_free()

    def get_used_blocks(self):
        free = self.bitmap.get_num_free()
        total = self.blkdev.num_blocks
        return total - free

    def get_total_blocks(self):
        return self.blkdev.num_blocks

    def get_meta_info(self):
        return self.meta_info

    def update_disk_time(self):
        mi = RootMetaInfo()
        mi.set_current_as_disk_time()
        self.change_meta_info(mi)

    def change_meta_info(self, meta_info):
        if self.root != None and self.root.valid:
            dirty = False
            # update create_ts
            create_ts = meta_info.get_create_ts()
            if create_ts != None:
                self.root.create_ts = meta_info.get_create_ts()
                dirty = True
            # update disk_ts
            disk_ts = meta_info.get_disk_ts()
            if disk_ts != None:
                self.root.disk_ts = disk_ts
                dirty = True
            # update mod_ts
            mod_ts = meta_info.get_mod_ts()
            if mod_ts != None:
                self.root.mod_ts = mod_ts
                dirty = True
            # update if something changed
            if dirty:
                self.root.write()
                self.meta_info = RootMetaInfo(
                    self.root.create_ts, self.root.disk_ts, self.root.mod_ts
                )
            return True
        else:
            return False

    def change_create_ts(self, create_ts):
        return self.change_meta_info(RootMetaInfo(create_ts=create_ts))

    def change_disk_ts(self, disk_ts):
        return self.change_meta_info(RootMetaInfo(disk_ts=disk_ts))

    def change_mod_ts(self, mod_ts):
        return self.change_meta_info(RootMetaInfo(mod_ts=mod_ts))

    def change_create_ts_by_string(self, create_ts_str):
        t = TimeStamp()
        t.parse(create_ts_str)
        return self.change_meta_info(RootMetaInfo(create_ts=t))

    def change_disk_ts_by_string(self, disk_ts_str):
        t = TimeStamp()
        t.parse(disk_ts_str)
        return self.change_meta_info(RootMetaInfo(disk_ts=t))

    def change_mod_ts_by_string(self, mod_ts_str):
        t = TimeStamp()
        t.parse(mod_ts_str)
        return self.change_meta_info(RootMetaInfo(mod_ts=t))

    def relabel(self, name):
        """Relabel the volume"""
        # make sure its a FSString
        if not isinstance(name, FSString):
            raise ValueError("relabel's name must be a FSString")
        # validate file name
        fn = FileName(name, is_intl=self.is_intl, is_longname=False)
        if not fn.is_valid():
            raise FSError(INVALID_VOLUME_NAME, file_name=name, node=self)
        # update root block
        self.root.name = name
        self.root.write()
        # store internally
        self.name = name
        self.root_dir.name = name

    def create_dir(self, ami_path):
        """Create a new directory"""
        # make sure its a FSString
        if not isinstance(ami_path, FSString):
            raise ValueError("create_dir's ami_path must be a FSString")
        # check file path
        fn = FileName(ami_path, is_intl=self.is_intl, is_longname=self.is_longname)
        if not fn.is_valid():
            raise FSError(INVALID_FILE_NAME, file_name=ami_path)
        # split into dir and base name
        dir_name, base_name = fn.get_dir_and_base_name()
        if base_name == None:
            raise FSError(INVALID_FILE_NAME, file_name=ami_path)
        # find parent of dir
        if dir_name == None:
            node = self.root_dir
        else:
            # no parent dir found
            node = self.get_dir_path_name(dir_name)
            if node == None:
                raise FSError(
                    INVALID_PARENT_DIRECTORY,
                    file_name=ami_path,
                    extra="not found: " + dir_name,
                )
        node.create_dir(base_name)

    def write_file(self, data, ami_path, suggest_name=None, cache=False):
        """Write given data as a file"""
        # get parent node and file_name
        parent_node, file_name = self.get_create_path_name(ami_path, suggest_name)
        if parent_node == None:
            raise FSError(INVALID_PARENT_DIRECTORY, file_name=ami_path)
        if file_name == None:
            raise FSError(INVALID_FILE_NAME, file_name=file_name)
        # create file
        node = parent_node.create_file(file_name, data)
        if not cache:
            node.flush()

    def read_file(self, ami_path, cache=False):
        """Read a file and return data"""
        # get node of file
        node = self.get_file_path_name(ami_path)
        if node == None:
            raise FSError(FILE_NOT_FOUND, file_name=ami_path)
        data = node.get_file_data()
        if not cache:
            node.flush()
        return data

    def delete(self, ami_path, wipe=False, all=False):
        """Delete a file or directory at given path"""
        node = self.get_path_name(ami_path)
        if node == None:
            raise FSError(FILE_NOT_FOUND, file_name=ami_path)
        node.delete(wipe=wipe, all=all)
