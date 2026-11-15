import os.path

from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.Relocate import Relocate
from amitools.vamos.log import log_segload
from .seglist import SegList
from .overlay import OverlayInfo


class SegLoadInfo(object):
    def __init__(
        self, seglist, bin_img=None, sys_file=None, ami_file=None, overlay=None
    ):
        self.seglist = seglist
        self.bin_img = bin_img
        self.sys_file = sys_file
        self.ami_file = ami_file
        self.overlay = overlay

    def __str__(self):
        return "[SegLoad:%s,sys=%s,ami=%s]" % (
            self.seglist,
            self.sys_file,
            self.ami_file,
        )

    def has_overlay(self):
        return self.overlay is not None


class SegmentLoader(object):
    def __init__(self, alloc, path_mgr=None):
        self.alloc = alloc
        self.path_mgr = path_mgr
        self.mem = alloc.get_mem()
        self.binfmt = BinFmt()
        # map seglist baddr to bin_img
        self.infos = {}

    def load_sys_seglist(self, sys_bin_file, file_mgr=None, ami_file=None, lock=None):
        """load seglist, register it, and return seglist baddr or 0.

        If a file_mgr is given, binaries with an overlay table get their
        overlay manager data set up. ami_file and lock are used to reopen the
        binary for the overlay manager. Without a file_mgr overlay tables are
        not set up."""
        info = self.int_load_sys_seglist(sys_bin_file)
        if info and file_mgr is not None and OverlayInfo.has_overlay(info.bin_img):
            try:
                info.overlay = OverlayInfo.create(
                    self.alloc,
                    file_mgr,
                    info.seglist,
                    sys_bin_file,
                    ami_file or sys_bin_file,
                    lock,
                )
            except ValueError as e:
                log_segload.warning("overlay setup failed: %s", e)
                info.seglist.free()
                info = None
            # None means no supported setup needed (e.g. custom manager) - keep seglist
        if info:
            baddr = info.seglist.get_baddr()
            self.infos[baddr] = info
            log_segload.info("loaded sys seglist: %s", info)
            return baddr
        else:
            log_segload.info("can't load sys seglist: %s", sys_bin_file)
            return 0

    def load_ami_seglist(self, ami_bin_file, lock=None):
        """load seglist, register it, and return seglist baddr or 0"""
        info = self.int_load_ami_seglist(ami_bin_file, lock)
        if info:
            baddr = info.seglist.get_baddr()
            self.infos[baddr] = info
            log_segload.info("loaded ami seglist: %s", info)
            return baddr
        else:
            log_segload.info("can't load ami seglist: %s", ami_bin_file)
            return 0

    def unload_seglist(self, seglist_baddr):
        """unregister given seglist baddr and free seglist.
        return True if seglist was unloaded"""
        if seglist_baddr not in self.infos:
            log_segload.error("unknown seglist at @%06x", seglist_baddr)
            return False
        info = self.infos[seglist_baddr]
        log_segload.info("unload seglist: %s", info)
        del self.infos[seglist_baddr]
        if info.overlay:
            info.overlay.free()
        info.seglist.free()
        return True

    def get_info(self, seglist_baddr):
        """return associated bin_img for given registered seglist baddr or None"""
        if seglist_baddr in self.infos:
            return self.infos[seglist_baddr]

    def register_seglist(self, baddr):
        """register custom seglist"""
        info = SegLoadInfo(SegList(self.alloc, baddr))
        log_segload.info("register seglist: %s", info)
        self.infos[baddr] = info

    def unregister_seglist(self, baddr):
        """remove custom seglist"""
        info = self.infos[baddr]
        log_segload.info("unregister seglist: %s", info)
        del self.infos[baddr]

    def shutdown(self):
        """check orphan seglists on shutdown and return number of orphans"""
        log_segload.info("shutdown")
        for baddr in self.infos:
            info = self.infos[baddr]
            log_segload.warning("orphaned seglist: %s", info)
            # try to free list
            if info.overlay:
                info.overlay.free()
            info.seglist.free()
        return len(self.infos)

    def int_load_ami_seglist(self, ami_bin_file, lock=None):
        """load seglist given by ami binary path and return SegLoadInfo"""
        if self.path_mgr is None:
            return None
        # try to map path
        sys_path = self.path_mgr.ami_to_sys_path(lock, ami_bin_file, mustExist=True)
        if sys_path:
            info = self.int_load_sys_seglist(sys_path)
            info.ami_file = ami_bin_file
            return info

    def int_load_sys_seglist(self, sys_bin_file):
        """load seglist given by sys binary path and return SegLoadInfo"""
        base_name = os.path.basename(sys_bin_file)

        # does file exist?
        if not os.path.isfile(sys_bin_file):
            log_segload.debug("no file: %s", sys_bin_file)
            return None

        # try to load bin image in supported format (e.g. HUNK or ELF)
        bin_img = self.binfmt.load_image(sys_bin_file)
        if bin_img is None:
            log_segload.debug("load_image failed: %s", sys_bin_file)
            return None

        # create relocator
        relocator = Relocate(bin_img)

        # get info about segments to allocate
        sizes = relocator.get_sizes()
        names = bin_img.get_segment_names()
        bin_img_segs = bin_img.get_segments()

        # build label names
        if self.alloc.label_mgr:
            labels = []
            for i in range(len(sizes)):
                name = "%s_%d:%s" % (base_name, i, names[i].lower())
                labels.append(name)
        else:
            labels = None

        # allocate seg list
        seg_list = SegList.alloc(self.alloc, sizes, labels, bin_img_segs)

        # retrieve addr
        addrs = seg_list.get_all_addrs()

        # relocate to addresses and return data
        datas = relocator.relocate(addrs)

        # write contents to allocated memory
        for i in range(len(sizes)):
            # write data to segments
            self.mem.w_block(addrs[i], bytes(datas[i]))

        return SegLoadInfo(seg_list, bin_img, sys_bin_file)
