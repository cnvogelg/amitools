from amitools.binfmt.hunk import Hunk, HunkReader
from amitools.vamos.log import log_segload


class OverlayInfo(object):
    """resources needed by the overlay manager of a loaded overlay binary"""

    def __init__(self, alloc, file_mgr, fh, table=None, hunk_table=None):
        self.alloc = alloc
        self.file_mgr = file_mgr
        self.fh = fh
        self.table = table
        self.hunk_table = hunk_table

    def __str__(self):
        table = self.table.addr if self.table else 0
        hunks = self.hunk_table.addr if self.hunk_table else 0
        return "[Overlay:fh=%06x,table=%06x,hunks=%06x]" % (
            self.fh.b_addr,
            table,
            hunks,
        )

    @staticmethod
    def has_overlay(bin_img):
        hunk_file = getattr(bin_img, "file_data", None)
        return getattr(hunk_file, "overlay_blk", None) is not None

    @staticmethod
    def create(alloc, file_mgr, seglist, sys_file, ami_file, lock=None):
        """setup the overlay manager data of a loaded seglist.

        The binary is opened again via the file manager, so the overlay
        manager can load overlay nodes on demand.
        Returns an OverlayInfo, or None if this overlay type needs no setup.
        Raises ValueError on setup failure."""
        reader = HunkReader.HunkReader()
        result = reader.read_file(sys_file)
        if result != Hunk.RESULT_OK:
            raise ValueError(
                "can't read overlay metadata for '%s': %s"
                % (sys_file, reader.error_string)
            )
        overlay = next(
            (hunk for hunk in reader.hunks if hunk["type"] == Hunk.HUNK_OVERLAY),
            None,
        )
        if overlay is None:
            raise ValueError("overlay metadata missing for '%s'" % sys_file)
        ov_data = overlay["ov_data"]
        overlay_file_pos = overlay["hunk_file_offset"] + 8 + len(ov_data)

        fh = file_mgr.open(lock, str(ami_file), "rb")
        if fh is None:
            raise ValueError("can't open overlay binary '%s'" % ami_file)
        if fh.seek(overlay_file_pos, 0) < 0:
            file_mgr.close(fh)
            raise ValueError(
                "can't seek overlay binary '%s' to %06x" % (ami_file, overlay_file_pos)
            )

        if not overlay.get("ov_std"):
            log_segload.info(
                "custom overlay manager in '%s', using standard layout setup", sys_file
            )

        table = alloc.alloc_memory(len(ov_data) + 4, "LoadSegOverlayTable", False)
        if table is None:
            file_mgr.close(fh)
            raise ValueError("can't allocate overlay table")
        segments = seglist.get_all_addrs()
        hunk_table = alloc.alloc_memory(
            len(segments) * 4, "LoadSegOverlayHunkTable", False
        )
        if hunk_table is None:
            alloc.free_memory(table)
            file_mgr.close(fh)
            raise ValueError("can't allocate overlay hunk table")

        mem = alloc.get_mem()
        mem.w_block(table.addr, ov_data)
        mem.w32(table.addr + len(ov_data), 0)
        for index, segment_addr in enumerate(segments):
            mem.w32(hunk_table.addr + index * 4, (segment_addr - 4) >> 2)

        # fill in the data fields of the overlay manager in the first segment
        manager_addr = segments[0]
        mem.w32(manager_addr + 8, fh.b_addr)
        mem.w32(manager_addr + 12, table.addr)
        mem.w32(manager_addr + 16, hunk_table.addr >> 2)
        return OverlayInfo(alloc, file_mgr, fh, table, hunk_table)

    def free(self):
        self.file_mgr.close(self.fh)
        if self.table:
            self.alloc.free_memory(self.table)
        if self.hunk_table:
            self.alloc.free_memory(self.hunk_table)
