from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.BinImage import BIN_IMAGE_TYPE_PY
from amitools.binfmt.Relocate import Relocate
from amitools.vamos.log import log_segload
from amitools.vamos.path.amipath import AmiPath
from amitools.vamos.cmdcore.pycmd import strip_py_ext
from .seglist import SegList
from .overlay import OverlayInfo


class SegLoadInfo(object):
    def __init__(
        self,
        seglist,
        bin_img=None,
        ami_file=None,
        overlay=None,
        name=None,
        command=None,
    ):
        self.seglist = seglist
        self.bin_img = bin_img
        self.ami_file = ami_file
        self.overlay = overlay
        self.name = name
        # for a Python command: the PyCommand owning the stub and trap
        self.command = command

    def __str__(self):
        return "[SegLoad:%s,ami=%s,name=%s]" % (
            self.seglist,
            self.ami_file,
            self.name,
        )

    def has_overlay(self):
        return self.overlay is not None


class SegmentLoader(object):
    def __init__(self, alloc, file_opener=None, command_manager=None):
        self.alloc = alloc
        self.file_opener = file_opener
        # optional command manager used to load Python commands
        self.command_manager = command_manager
        self.mem = alloc.get_mem()
        self.binfmt = BinFmt()
        # map seglist baddr to bin_img
        self.infos = {}

    def set_file_opener(self, file_opener):
        self.file_opener = file_opener

    def get_file_opener(self):
        return self.file_opener

    def set_command_manager(self, command_manager):
        self.command_manager = command_manager

    def get_command_manager(self):
        return self.command_manager

    def load_seglist(self, fobj, name=None, ami_file=None, lock=None, file_opener=None):
        """load seglist from an already opened file object and register it.

        Return the seglist baddr or 0. The caller keeps ownership of fobj
        and is responsible for closing it.

        If a file opener is available, binaries with an overlay table get
        their overlay manager data set up. The overlay needs its own file
        handle that stays open, so it is opened again via the opener.
        """
        info = self.int_load_seglist(fobj, name=name, ami_file=ami_file)
        if info:
            opener = file_opener or self.file_opener
            if opener is not None and OverlayInfo.has_overlay(info.bin_img):
                try:
                    info.overlay = OverlayInfo.create(
                        self.alloc,
                        opener,
                        info.seglist,
                        info.ami_file or info.name,
                        lock,
                    )
                except ValueError as e:
                    log_segload.warning("overlay setup failed: %s", e)
                    self._free_segload_info(info)
                    info = None
                # None means no supported setup needed (e.g. custom
                # manager) - keep seglist
        if info:
            baddr = info.seglist.get_baddr()
            self.infos[baddr] = info
            log_segload.info("loaded seglist: %s", info)
            return baddr
        else:
            log_segload.info("can't load seglist: %s", name)
            return 0

    def load_ami_seglist(self, ami_bin_file, lock=None, file_opener=None):
        """load seglist from an Amiga path and register it.

        Return the seglist baddr or 0."""
        opener = file_opener or self.file_opener
        if opener is None:
            log_segload.error("no file opener set to load: %s", ami_bin_file)
            return 0
        fobj = opener.open(ami_bin_file, lock)
        if fobj is None:
            log_segload.info("can't open ami seglist: %s", ami_bin_file)
            return 0
        try:
            return self.load_seglist(
                fobj,
                name=ami_bin_file,
                ami_file=ami_bin_file,
                lock=lock,
                file_opener=opener,
            )
        finally:
            fobj.close()

    def _free_segload_info(self, info):
        """release the resources of a SegLoadInfo.

        A Python command owns its stub seglist and trap in the command
        manager, so it is freed there instead of freeing the seglist
        directly.
        """
        if info.overlay:
            info.overlay.free()
        if info.command is not None and self.command_manager is not None:
            self.command_manager.free_stub(info.command)
        else:
            info.seglist.free()

    def unload_seglist(self, seglist_baddr):
        """unregister given seglist baddr and free seglist.
        return True if seglist was unloaded"""
        if seglist_baddr not in self.infos:
            log_segload.error("unknown seglist at @%06x", seglist_baddr)
            return False
        info = self.infos[seglist_baddr]
        log_segload.info("unload seglist: %s", info)
        del self.infos[seglist_baddr]
        self._free_segload_info(info)
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
            self._free_segload_info(info)
        return len(self.infos)

    def int_load_seglist(self, fobj, name=None, ami_file=None):
        """load seglist from the given file object and return SegLoadInfo.

        The file object is read from its current position. It is not
        closed by this method.
        """
        # derive a label base name from the Amiga file name
        if name is not None:
            base_name = AmiPath(str(name)).filename()
        else:
            base_name = None
        if not base_name:
            base_name = "seglist"

        # try to load bin image in supported format (e.g. HUNK or ELF)
        bin_img = self.binfmt.load_image_fobj(fobj)
        if bin_img is None:
            log_segload.debug("load_image failed: %s", name)
            return None

        # a Python command has no segments; synthesize a minimal stub
        if bin_img.file_type == BIN_IMAGE_TYPE_PY:
            if self.command_manager is None:
                log_segload.error("no command manager to load python command: %s", name)
                return None
            cmd_name = strip_py_ext(base_name)
            cmd = self.command_manager.make_command(
                cmd_name, source=bin_img.get_file_data()
            )
            seg_list = self.command_manager.make_stub(cmd)
            log_segload.info("loaded python command: %s", cmd_name)
            return SegLoadInfo(
                seg_list, None, ami_file=ami_file, name=name, command=cmd
            )

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
                label = "%s_%d:%s" % (base_name, i, names[i].lower())
                labels.append(label)
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

        return SegLoadInfo(seg_list, bin_img, ami_file=ami_file, name=name)
