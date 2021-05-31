from amitools.vamos.log import log_libmgr
from .initresident import InitRes
from amitools.vamos.libtypes import Resident
from amitools.vamos.loader import SegmentLoader, SegList


class LibLoader(object):
    def __init__(self, machine, alloc, segloader):
        self.machine = machine
        self.mem = machine.get_mem()
        self.alloc = alloc
        self.segloader = segloader
        self.initres = InitRes(machine, alloc)

    def load_sys_lib(self, sys_bin_file, run_sp=None):
        """try to load native lib from sys path
        return (lib_base_addr, seglist_baddr) or (0,0)"""
        # load seglist
        seglist_baddr = self.segloader.load_sys_seglist(sys_bin_file)
        if seglist_baddr:
            return self._load_common(sys_bin_file, seglist_baddr, run_sp)
        else:
            return 0, 0

    def _load_common(self, lib_name, seglist_baddr, run_sp):
        # find resident in first hunk
        seglist = SegList(self.alloc, seglist_baddr)
        seg = seglist.get_segment()
        res = Resident.find(self.mem, seg.get_addr(), seg.get_size())
        # unload seglist if no resident was found
        if not res:
            log_libmgr.warning("%s: no resident found!", lib_name)
            self.segloader.unload_seglist(seglist_baddr)
            return 0, 0
        # init resident
        lib_base, _ = self.initres.init_resident(
            res.get_addr(), seglist.get_baddr(), run_sp=run_sp
        )
        # unload seglist on error
        if lib_base == 0:
            log_libmgr.warning("%s: init resident failed!", lib_name)
            self.segloader.unload_seglist(seglist_baddr)
            return 0, 0
        return lib_base, seglist_baddr

    def load_ami_lib(self, lib_name, cwd_lock=None, run_sp=None, progdir_lock=None):
        """try to load native lib from ami path
        return (lib_base_addr, seglist_baddr) or (0,0)"""
        search_paths = self.get_lib_search_paths(lib_name)
        # now try search paths
        prog_dir = "PROGDIR:"
        for ami_path in search_paths:
            # handle PROGDIR
            if ami_path.startswith(prog_dir):
                path = ami_path[len(prog_dir) :]
                lock = progdir_lock
            else:
                path = ami_path
                lock = cwd_lock
            seglist_baddr = self.segloader.load_ami_seglist(path, lock)
            log_libmgr.debug(
                "load_ami_lib: path=%s, lock=%s -> seglist=%08x",
                path,
                lock,
                seglist_baddr,
            )
            if seglist_baddr > 0:
                return self._load_common(lib_name, seglist_baddr, run_sp)
        return 0, 0

    @staticmethod
    def get_lib_base_name(lib_name):
        result = lib_name
        pos = result.rfind("/")
        if pos != -1:
            result = result[pos + 1 :]
        pos = result.rfind(":")
        if pos != -1:
            result = result[pos + 1 :]
        return result.lower()

    @staticmethod
    def get_lib_search_paths(lib_name, base_dir=None):
        """return list of Amiga paths where to search for library"""
        if base_dir is None:
            base_dir = "libs"
        # relative path
        if lib_name.find(":") == -1:
            base_name = base_dir + "/" + lib_name
            return [
                lib_name,
                base_name,
                "PROGDIR:" + lib_name,
                "PROGDIR:" + base_name,
                base_dir.upper() + ":" + lib_name,
            ]
        # absolute path
        else:
            return [lib_name]
