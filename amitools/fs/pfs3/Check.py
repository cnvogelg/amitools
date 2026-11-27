"""Check the consistency of a PFS3 volume: the bitmaps agree with the
blocks in use, anodes are in use exactly when something refers to them,
directories and files are consistent, and so are the lists of hard links.
Read-only."""

import struct

from amitools.fs.FSError import FSError
from amitools.fs.fsck.FsckResult import FsckResult, IssueType, Severity

from .Const import (
    ANODE_BADBLOCKS,
    ANODE_EMPTY_BLOCKNR,
    ANODE_ROOTDIR,
    MAXBITMAPINDEX,
    MAXSMALLBITMAPINDEX,
    MAXSMALLINDEXNR,
    MAXSUPER,
    ST_LINKDIR,
    ST_ROLLOVERFILE,
    ST_SOFTLINK,
    ST_USERDIR,
    VALID_TYPES,
)
from .DirEntry import name_upper
from .Disk import (
    BLK_INDEX,
    DB_PARENT,
    EX_SUPERINDEX,
    RB_BITMAPINDEX,
    RB_INDEXBLOCKS,
    RB_RESERVED_FREE,
    u32,
)

# report at most this many issues of one kind one by one
MAX_REPORT = 20


class PFS3Check:
    def __init__(self, disk):
        self.disk = disk
        self.result = FsckResult()
        self._counts = {}

    def _add(self, itype, severity, blk, msg, key=None):
        key = key or (itype, severity)
        n = self._counts.get(key, 0) + 1
        self._counts[key] = n
        if n <= MAX_REPORT:
            self.result.add_issue(itype, severity, blk, msg)
        elif n == MAX_REPORT + 1:
            self.result.add_issue(
                itype, severity, -1, "... more issues of this kind not shown"
            )

    def error(self, itype, msg, blk=-1, key=None):
        self._add(itype, Severity.ERROR, blk, msg, key)

    def warn(self, itype, msg, blk=-1, key=None):
        self._add(itype, Severity.WARN, blk, msg, key)

    def info(self, msg):
        self.result.add_issue(IssueType.UNKNOWN, Severity.INFO, -1, msg)

    def run(self):
        d = self.disk
        self.res_refs = {}
        self.anode_refs = {}
        self.data_refs = bytearray(((d.data_bits + 31) // 32) * 4)
        self.dead_deldir_anodes = set()
        try:
            self._check_reserved_structures()
            self._check_tree()
            self._check_deldir()
            self._check_anodes()
            self._check_reserved_bitmap()
            self._check_data_bitmap()
        except FSError as e:
            self.error(IssueType.READ_ERROR, "check aborted: %s" % e)
        return self.result

    # ----- references -----

    def ref_res(self, blocknr, what):
        d = self.disk
        if (
            blocknr < d.firstreserved
            or blocknr > d.lastreserved
            or (blocknr - d.firstreserved) % d.rescluster
        ):
            self.error(
                IssueType.BLOCK_OUT_OF_RANGE,
                "%s at %d is no reserved block" % (what, blocknr),
                blocknr,
            )
            return False
        other = self.res_refs.get(blocknr)
        if other is not None:
            self.error(
                IssueType.BLOCK_ALREADY_USED,
                "%s at %d is also %s" % (what, blocknr, other),
                blocknr,
            )
            return False
        self.res_refs[blocknr] = what
        return True

    def ref_anode(self, nr, what):
        other = self.anode_refs.get(nr)
        if other is not None:
            self.error(
                IssueType.BLOCK_ALREADY_USED,
                "anode %d of %s is also %s" % (nr, what, other),
            )
            return False
        self.anode_refs[nr] = what
        return True

    def ref_data(self, blocknr, count, what):
        d = self.disk
        k0 = blocknr - d.bitmapstart
        if k0 < 0 or k0 + count > d.data_bits:
            self.error(
                IssueType.BLOCK_OUT_OF_RANGE,
                "%s: blocks %d+%d outside the data area" % (what, blocknr, count),
                blocknr,
            )
            return
        refs = self.data_refs
        for k in range(k0, k0 + count):
            byte, mask = k >> 3, 0x80 >> (k & 7)
            if refs[byte] & mask:
                self.error(
                    IssueType.BLOCK_ALREADY_USED,
                    "%s: data block %d used twice" % (what, d.bitmapstart + k),
                    d.bitmapstart + k,
                )
            refs[byte] |= mask

    # ----- reserved structures -----

    def _check_reserved_structures(self):
        d = self.disk
        nroot = (d.rblkcluster + d.rescluster - 1) // d.rescluster
        for k in range(nroot):
            self.ref_res(d.firstreserved + k * d.rescluster, "root block cluster")
        if d.has_ext:
            self.ref_res(d.get_ext().blocknr, "root block extension")
        # bitmap
        num_mi = (d.no_bmb + d.ipb - 1) // d.ipb
        num_bmi = MAXBITMAPINDEX + 1 if d.supermode else MAXSMALLBITMAPINDEX + 1
        for i in range(num_bmi):
            blk = d._r32(RB_BITMAPINDEX + 4 * i)
            if i >= num_mi:
                if blk:
                    self.warn(
                        IssueType.BITMAP_BLOCK_ERROR,
                        "unneeded bitmap index block %d" % i,
                        blk,
                    )
                continue
            try:
                mi = d._get_mi(i)
            except FSError as e:
                self.error(IssueType.BITMAP_BLOCK_ERROR, str(e), blk)
                continue
            self.ref_res(mi.blocknr, "bitmap index block %d" % i)
            for j in range(d.ipb):
                s = i * d.ipb + j
                if s >= d.no_bmb:
                    break
                try:
                    bm = d._get_bm(s)
                except FSError as e:
                    self.error(IssueType.BITMAP_BLOCK_ERROR, str(e))
                    continue
                self.ref_res(bm.blocknr, "bitmap block %d" % s)
        # anode index
        if d.supermode:
            for k in range(MAXSUPER + 1):
                if not u32(d.get_ext().data, EX_SUPERINDEX + 4 * k):
                    continue
                try:
                    sb = d._get_sb(k)
                except FSError as e:
                    self.error(IssueType.INVALID_DIR_BLOCK, str(e))
                    continue
                self.ref_res(sb.blocknr, "super block %d" % k)
                for j in range(d.ipb):
                    if u32(sb.data, BLK_INDEX + 4 * j):
                        self._check_index_block(k * d.ipb + j)
        else:
            for i in range(MAXSMALLINDEXNR + 1):
                if d._r32(RB_INDEXBLOCKS + 4 * i):
                    self._check_index_block(i)
        # deldir
        for s in range(d.get_deldir_size()):
            try:
                dd = d._get_dd(s)
            except FSError as e:
                self.error(IssueType.INVALID_DIR_BLOCK, str(e))
                continue
            if dd is None:
                self.error(IssueType.INVALID_DIR_BLOCK, "deldir block %d missing" % s)
                continue
            self.ref_res(dd.blocknr, "deldir block %d" % s)

    def _check_index_block(self, i):
        d = self.disk
        try:
            ib = d._get_ib(i)
        except FSError as e:
            self.error(IssueType.INVALID_DIR_BLOCK, str(e))
            return
        self.ref_res(ib.blocknr, "index block %d" % i)
        for j in range(d.ipb):
            if not u32(ib.data, BLK_INDEX + 4 * j):
                continue
            seqnr = i * d.ipb + j
            try:
                ab = d._get_ab(seqnr)
            except FSError as e:
                self.error(IssueType.INVALID_DIR_BLOCK, str(e))
                continue
            self.ref_res(ab.blocknr, "anode block %d" % seqnr)

    # ----- directory tree -----

    def _check_tree(self):
        self.visited_dirs = set()
        self.objects = {}
        self.links = []
        self._check_dir(ANODE_ROOTDIR, 0, "")
        self._check_links()

    def _chain(self, head, what):
        try:
            return self.disk.get_chain(head)
        except FSError as e:
            self.error(IssueType.CIRCULAR_CHAIN, "%s: %s" % (what, e))
            return None

    def _check_dir(self, dir_anode, parent, path):
        d = self.disk
        where = path or "root directory"
        if dir_anode in self.visited_dirs:
            self.error(
                IssueType.CIRCULAR_CHAIN,
                "%s: directory %d reached twice" % (where, dir_anode),
            )
            return
        self.visited_dirs.add(dir_anode)
        chain = self._chain(dir_anode, where)
        if chain is None:
            return
        names = {}
        subdirs = []
        for nr, cs, bn, nx in chain:
            self.ref_anode(nr, "directory %s" % where)
            if cs != 1:
                self.error(
                    IssueType.INVALID_DIR_BLOCK,
                    "%s: anode %d has clustersize %d" % (where, nr, cs),
                )
                continue
            if not self.ref_res(bn, "dir block of %s" % where):
                continue
            try:
                res = d.get_dir_block(bn, nr, dir_anode)
                entries, _ = d.block_entries(res)
            except FSError as e:
                self.error(IssueType.INVALID_DIR_BLOCK, "%s: %s" % (where, e), bn)
                continue
            if u32(res.data, DB_PARENT) != parent:
                self.error(
                    IssueType.INVALID_PARENT_PTR,
                    "%s: dir block %d has parent %d, not %d"
                    % (where, bn, u32(res.data, DB_PARENT), parent),
                    bn,
                )
            for off, e in entries:
                ename = e.name.decode("latin-1")
                epath = path + "/" + ename if path else ename
                up = name_upper(e.name)
                if up in names:
                    self.error(
                        IssueType.DUPLICATE_NAME, "%s: name used twice" % epath, bn
                    )
                names[up] = True
                if b":" in e.name or b"/" in e.name or not e.name:
                    self.error(
                        IssueType.INVALID_DIR_BLOCK, "%s: invalid name" % epath, bn
                    )
                self._check_entry(e, dir_anode, epath, subdirs)
        for anode, epath in subdirs:
            self._check_dir(anode, dir_anode, epath)

    def _check_entry(self, e, dir_anode, path, subdirs):
        d = self.disk
        B = d.B
        t = e.type
        if t not in VALID_TYPES:
            self.error(IssueType.INVALID_DIR_BLOCK, "%s: invalid type %d" % (path, t))
            return
        if e.is_link():
            self.ref_anode(e.anode, "link node of %s" % path)
            self.links.append((e, dir_anode, path))
            return
        if e.link:
            if not d.has_dir_extension():
                self.error(
                    IssueType.INVALID_DIR_BLOCK,
                    "%s: links without dir extension" % path,
                )
            self.objects[e.anode] = (e, dir_anode, path)
        if t == ST_USERDIR:
            subdirs.append((e.anode, path))
            return
        size = e.get_size(d.is_largefile())
        if t == ST_ROLLOVERFILE:
            size = e.fsize
            if size % B:
                self.error(
                    IssueType.SIZE_MISMATCH,
                    "%s: rollover size no multiple of blocks" % path,
                )
            if size and (e.virtualsize >= size or e.rollpointer > size):
                self.error(IssueType.SIZE_MISMATCH, "%s: invalid rollover state" % path)
        if t == ST_SOFTLINK and e.fsize >= B:
            self.error(IssueType.SIZE_MISMATCH, "%s: soft link target too long" % path)
        chain = self._chain(e.anode, path)
        if chain is None:
            return
        blocks = 0
        for nr, cs, bn, nx in chain:
            self.ref_anode(nr, path)
            if cs:
                self.ref_data(bn, cs, path)
                blocks += cs
            elif bn not in (0, ANODE_EMPTY_BLOCKNR):
                self.error(
                    IssueType.BAD_DATA_BLOCK,
                    "%s: anode %d with blocknr but no blocks" % (path, nr),
                )
        want = 1 if t == ST_SOFTLINK else (size + B - 1) // B
        if blocks != want:
            self.error(
                IssueType.SIZE_MISMATCH,
                "%s: %d blocks for %d bytes, want %d" % (path, blocks, size, want),
            )

    def _check_links(self):
        d = self.disk
        # every link entry: its node points to its directory and its object
        nodes = {}
        for e, dir_anode, path in self.links:
            obj_dir, link_dir, nx = d.get_anode(e.anode)
            if link_dir != dir_anode:
                self.error(
                    IssueType.INVALID_PARENT_PTR,
                    "%s: link node names directory %d" % (path, link_dir),
                )
            obj = self.objects.get(e.link)
            if obj is None:
                self.error(
                    IssueType.ORPHAN_FILE,
                    "%s: hard link to missing object %d" % (path, e.link),
                )
                continue
            oe, odir, opath = obj
            if obj_dir != odir:
                self.error(
                    IssueType.INVALID_PARENT_PTR,
                    "%s: link node names object directory %d, not %d"
                    % (path, obj_dir, odir),
                )
            if (e.type == ST_LINKDIR) != (oe.type == ST_USERDIR):
                self.error(
                    IssueType.INVALID_DIR_BLOCK,
                    "%s: link type does not match %s" % (path, opath),
                )
            nodes[e.anode] = e
        # every object: its list holds exactly its link nodes
        listed = set()
        for anode, (oe, odir, opath) in self.objects.items():
            nr = oe.link
            seen = set()
            while nr:
                if nr in seen:
                    self.error(IssueType.CIRCULAR_CHAIN, "%s: link list loops" % opath)
                    break
                seen.add(nr)
                e = nodes.get(nr)
                if e is None or e.link != anode:
                    self.error(
                        IssueType.ORPHAN_FILE,
                        "%s: link list holds anode %d, no link to it" % (opath, nr),
                    )
                    break
                listed.add(nr)
                nr = d.get_anode(nr)[2]
        for nr, e in nodes.items():
            if nr not in listed:
                self.error(
                    IssueType.ORPHAN_FILE,
                    "link node %d not in the list of its object" % nr,
                )

    # ----- deldir -----

    def _check_deldir(self):
        d = self.disk
        for slot, dd, o, anodenr, fsize, date, name in d.deldir_slots():
            if not anodenr:
                continue
            chain = None
            try:
                chain = d.get_chain(anodenr)
            except FSError:
                pass
            if chain is not None and d.deldir_slot_valid(anodenr):
                for nr, cs, bn, nx in chain:
                    self.ref_anode(nr, "deleted file %r" % name)
            elif chain is not None:
                # recovered no more: the handler frees it when it looks at it
                for nr, cs, bn, nx in chain:
                    self.dead_deldir_anodes.add(nr)

    # ----- anodes -----

    def _check_anodes(self):
        d = self.disk
        for seqnr in range(d.get_max_anode_seqnr() + 1):
            ab = d._get_ab(seqnr)
            if ab is None:
                continue
            for off in range(d.apb):
                nr = d.anode_nr(seqnr, off)
                cs, bn, nx = struct.unpack_from(">III", ab.data, 16 + 12 * off)
                free = cs == 0 and bn == 0 and nx == 0
                if nr <= ANODE_BADBLOCKS:
                    if (cs, bn, nx) != (0, ANODE_EMPTY_BLOCKNR, 0):
                        self.error(
                            IssueType.INVALID_DIR_BLOCK,
                            "reserved anode %d is (%d,%d,%d)" % (nr, cs, bn, nx),
                        )
                    continue
                ref = nr in self.anode_refs
                if ref and free:
                    self.error(
                        IssueType.BITMAP_MISMATCH,
                        "anode %d of %s is free" % (nr, self.anode_refs[nr]),
                    )
                elif not ref and not free and nr not in self.dead_deldir_anodes:
                    self.warn(
                        IssueType.ORPHAN_BLOCK,
                        "anode %d (%d,%d,%d) in use, but not referenced"
                        % (nr, cs, bn, nx),
                    )
        for nr, what in self.anode_refs.items():
            try:
                seqnr, off = d.anode_loc(nr)
            except FSError:
                self.error(
                    IssueType.BLOCK_OUT_OF_RANGE, "invalid anode %d of %s" % (nr, what)
                )
                continue
            if d._get_ab(seqnr) is None:
                self.error(
                    IssueType.BLOCK_OUT_OF_RANGE,
                    "anode %d of %s in missing anode block" % (nr, what),
                )

    # ----- bitmaps -----

    def _check_reserved_bitmap(self):
        d = self.disk
        free = 0
        for i in range(d.numreserved):
            blk = d.firstreserved + i * d.rescluster
            is_free = d.is_res_free(blk)
            if is_free:
                free += 1
            ref = blk in self.res_refs
            if ref and is_free:
                self.error(
                    IssueType.BITMAP_MISMATCH,
                    "%s at %d marked free" % (self.res_refs[blk], blk),
                    blk,
                )
            elif not ref and not is_free:
                self.warn(
                    IssueType.ORPHAN_BLOCK,
                    "reserved block %d in use, but not referenced" % blk,
                    blk,
                )
        want = d._r32(RB_RESERVED_FREE)
        if free != want:
            self.error(
                IssueType.BITMAP_MISMATCH,
                "reserved_free is %d, bitmap has %d free" % (want, free),
            )
        # no bits past the end
        last = d.numreserved
        nwords = (d.rblkcluster * d.B - 524) // 4
        for i in range(last, min(nwords * 32, (last + 31) // 32 * 32)):
            if d.is_res_free(d.firstreserved + i * d.rescluster):
                self.warn(
                    IssueType.BITMAP_INVALID_FLAG,
                    "reserved bitmap bit %d past the end is set" % i,
                )
                break

    def _check_data_bitmap(self):
        d = self.disk
        refs = self.data_refs
        nwords = (d.data_bits + 31) // 32
        free = 0
        for L in range(nwords):
            s, j = divmod(L, d.lpb)
            bm = d._get_bm(s)
            free_w = u32(bm.data, BLK_INDEX + 4 * j)
            ref_w = int.from_bytes(refs[4 * L : 4 * L + 4], "big")
            nbits = min(32, d.data_bits - 32 * L)
            mask = (0xFFFFFFFF << (32 - nbits)) & 0xFFFFFFFF
            free += bin(free_w & mask).count("1")
            bad = ref_w & free_w & mask
            leak = ~free_w & ~ref_w & mask & 0xFFFFFFFF
            for w, err in ((bad, True), (leak, False)):
                while w:
                    bit = 32 - w.bit_length()
                    w &= ~(1 << (31 - bit))
                    blk = d.bitmapstart + 32 * L + bit
                    if err:
                        self.error(
                            IssueType.BITMAP_MISMATCH,
                            "data block %d in use, but marked free" % blk,
                            blk,
                        )
                    else:
                        self.warn(
                            IssueType.ORPHAN_BLOCK,
                            "data block %d marked in use, but not referenced" % blk,
                            blk,
                        )
        want = d.get_blocks_free()
        if free != want:
            self.error(
                IssueType.BITMAP_MISMATCH,
                "blocksfree is %d, bitmap has %d free" % (want, free),
            )
