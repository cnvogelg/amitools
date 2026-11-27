"""The PFS3 metadata engine: reads and writes the on-disk structures of a
PFS3 volume.

Changes are made in memory and committed the way the PFS3 handler does it:
every changed reserved block is written to a block that is free on disk,
its parent is changed to point to the new location, and the write of the
root block cluster at its fixed location commits all of it.
Freed blocks only become free with the commit, so nothing that the volume
on disk refers to is overwritten before the commit, and a write that fails
before it leaves the volume as it was. rollback() then drops the changes
in memory."""

import struct
import time

from .BlockIO import PFS3BlockIO
from .Const import (
    ANODE_BADBLOCKS,
    ANODE_EMPTY_BLOCKNR,
    ANODE_ROOTDIR,
    BOOTBLOCK1,
    DEFAULT_FNSIZE,
    DELENTRIES_PER_BLOCK,
    DELENTRY_PROT,
    DELENTRY_SIZE,
    DISK_TYPES,
    DNSIZE,
    FNSIZE,
    ID_AB,
    ID_BM,
    ID_DB,
    ID_DD,
    ID_EX,
    ID_IB,
    ID_MI,
    ID_PFS1,
    ID_PFS2,
    ID_PFS3,
    ID_SB,
    MAXBITMAPINDEX,
    MAXDELDIR,
    MAXDISKSIZE,
    MAXDISKSIZE1K,
    MAXDISKSIZE2K,
    MAXNUMRESERVED,
    MAXRBLKCLUSTER,
    MAXSMALLBITMAPINDEX,
    MAXSMALLDISK,
    MAXSMALLINDEXNR,
    MAXSUPER,
    MAX_ANODE_SEQNR,
    MAX_FILE_SIZE,
    MAX_FNSIZE,
    MAX_LARGE_FILE_SIZE,
    MAX_VOLNAME,
    MODE_DATESTAMP,
    MODE_DELDIR,
    MODE_DIR_EXTENSION,
    MODE_EXTENSION,
    MODE_EXTROVING,
    MODE_HARDDISK,
    MODE_KNOWN,
    MODE_LARGEFILE,
    MODE_LONGFN,
    MODE_SIZEFIELD,
    MODE_SPLITTED_ANODES,
    MODE_STORED_GEOM,
    MODE_SUPERDELDIR,
    MODE_SUPERINDEX,
    PFS2VERSION,
    PP_NONE,
    RESERVEDANODES,
    ROOTBLOCK,
)
from .DirEntry import DirEntry, DirEntryError, name_upper
from amitools.fs.FSError import (
    FILE_DATA_BLOCK_COUNT_MISMATCH,
    FSError,
    INTERNAL_ERROR,
    INVALID_ANODE,
    INVALID_BITMAP_BLOCK,
    INVALID_FILE_DATA_BLOCK,
    INVALID_RESERVED_BLOCK,
    INVALID_ROOT_BLOCK,
    INVALID_USER_DIR_BLOCK,
    INVALID_VOLUME_NAME,
    NO_FREE_BLOCKS,
    VOLUME_READ_ONLY,
)


def u16(b, o):
    return struct.unpack_from(">H", b, o)[0]


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def p16(b, o, v):
    struct.pack_into(">H", b, o, v & 0xFFFF)


def p32(b, o, v):
    struct.pack_into(">I", b, o, v & 0xFFFFFFFF)


def amiga_now():
    """the current time as an AmigaDOS date triple"""
    from amitools.fs.TimeStamp import TimeStamp

    ts = TimeStamp()
    ts.from_secs(time.mktime(time.localtime()))
    return (ts.days, ts.mins, ts.ticks)


# root block fields
RB_DISKTYPE = 0x00
RB_OPTIONS = 0x04
RB_DATESTAMP = 0x08
RB_CREATION = 0x0C
RB_PROTECTION = 0x12
RB_DISKNAME = 0x14
RB_LASTRESERVED = 0x34
RB_FIRSTRESERVED = 0x38
RB_RESERVED_FREE = 0x3C
RB_RESERVED_BLKSIZE = 0x40
RB_RBLKCLUSTER = 0x42
RB_BLOCKSFREE = 0x44
RB_ALWAYSFREE = 0x48
RB_ROVING_PTR = 0x4C
RB_DELDIR = 0x50
RB_DISKSIZE = 0x54
RB_EXTENSION = 0x58
RB_BITMAPINDEX = 0x60
RB_INDEXBLOCKS = 0x74
# reserved bitmap in the root block cluster
RB_RESBITMAP = 0x200
RB_RESBITMAP_BITS = 0x20C

# root block extension fields
EX_EXT_OPTIONS = 0x04
EX_DATESTAMP = 0x08
EX_PFS2VERSION = 0x0C
EX_ROOT_DATE = 0x10
EX_VOLUME_DATE = 0x16
EX_TOBEDONE = 0x1C
EX_RESERVED_ROVING = 0x2C
EX_ROVINGBIT = 0x30
EX_CURRANSEQNR = 0x32
EX_DELDIRROVING = 0x34
EX_DELDIRSIZE = 0x36
EX_FNSIZE = 0x38
EX_SUPERINDEX = 0x40
EX_DD_UID = 0x80
EX_DD_GID = 0x82
EX_DD_PROTECTION = 0x84
EX_DD_CREATION = 0x88
EX_DELDIR = 0x90
EX_DOSENVEC = 0x110

# common reserved block fields
BLK_ID = 0x00
BLK_DATESTAMP = 0x04
BLK_SEQNR = 0x08
BLK_INDEX = 0x0C
AB_NODES = 0x10
DB_ANODENR = 0x0C
DB_PARENT = 0x10
DB_ENTRIES = 0x14
DD_PROTECTION = 0x16
DD_CREATION = 0x1A
DD_ENTRIES = 0x20

# kinds of reserved blocks, in the order a commit moves them: a block is
# moved before its parent, which moving it changes
COMMIT_ORDER = ("DB", "AB", "IB", "SB", "DD", "BM", "MI", "EX")
KIND_IDS = {
    "EX": ID_EX,
    "MI": ID_MI,
    "BM": ID_BM,
    "SB": ID_SB,
    "IB": ID_IB,
    "AB": ID_AB,
    "DB": ID_DB,
    "DD": ID_DD,
}


class Res:
    """a reserved block in memory"""

    __slots__ = ("kind", "key", "blocknr", "data", "dirty", "new", "owner")

    def __init__(self, kind, key, blocknr, data, new=False):
        self.kind = kind
        # seqnr, or the block number a dir block was read from
        self.key = key
        self.blocknr = blocknr
        self.data = data
        self.dirty = new
        self.new = new
        # dir blocks: the anode of the directory's chain that points here
        self.owner = 0

    def __repr__(self):
        return "Res(%s %s @%d%s%s)" % (
            self.kind,
            self.key,
            self.blocknr,
            " dirty" if self.dirty else "",
            " new" if self.new else "",
        )


class PFS3Disk:
    def __init__(self, blkdev):
        self.blkdev = blkdev
        self.io = PFS3BlockIO(blkdev)
        self.read_only_reason = None
        self.root = None
        self._reset_state()

    # ----- state -----

    def _reset_state(self):
        self._cache = {}
        # the blocks changed since the last commit
        self._dirty_res = set()
        self._pending_res_free = []
        self._pending_data_free = []
        self._pending_wipe = []
        self._data_allocated = False
        self._dirty = False
        self._max_ab_seqnr = None
        self._set_volume_date = None

    def _block_error(self, code, msg, blocknr=None):
        if blocknr is not None:
            msg = "%s (block %d)" % (msg, blocknr)
        return FSError(code, extra="PFS3: " + msg)

    # ----- open -----

    def open(self):
        """read the root block cluster of a PFS3 volume and check it as the
        handler does when it mounts the volume"""
        errors = []
        for b in self.io.get_probe_block_sizes():
            self.io.set_block_size(b)
            if self.io.num_blocks < 3:
                continue
            boot = self.io.read(BOOTBLOCK1)
            rb = self.io.read(ROOTBLOCK)
            if u32(boot, 0) not in DISK_TYPES:
                errors.append("no PFS3 boot block at %d byte blocks" % b)
                continue
            if (
                u32(rb, RB_DISKTYPE) not in DISK_TYPES
                or u32(rb, RB_OPTIONS) == 0
                or u16(rb, RB_RESERVED_BLKSIZE) == 0
            ):
                errors.append("no PFS3 root block at %d byte blocks" % b)
                continue
            break
        else:
            raise FSError(INVALID_ROOT_BLOCK, extra="PFS3: " + "; ".join(errors))
        self._load_root()

    def _load_root(self):
        io = self.io
        B = io.block_size
        rb = io.read(ROOTBLOCK)
        disktype = u32(rb, RB_DISKTYPE)
        options = u32(rb, RB_OPTIONS)
        R = u16(rb, RB_RESERVED_BLKSIZE)
        rblkcluster = u16(rb, RB_RBLKCLUSTER)

        def bad(msg):
            return FSError(INVALID_ROOT_BLOCK, extra="PFS3: " + msg)

        if not 1 <= rblkcluster <= MAXRBLKCLUSTER:
            raise bad("invalid rblkcluster %d" % rblkcluster)
        if not options & MODE_HARDDISK:
            raise bad("floppy mode volumes are not supported")
        if disktype == ID_PFS1 and (options & MODE_LARGEFILE or R > 1024):
            raise bad("PFS\\1 volume with PFS\\2 features")
        if R & (R - 1) or R < B or R > 4096:
            raise bad("invalid reserved block size %d" % R)
        if ROOTBLOCK + rblkcluster > io.num_blocks:
            raise bad("root block cluster beyond the volume")
        root = bytearray(io.read(ROOTBLOCK, rblkcluster))
        if rb[RB_DISKNAME] >= DNSIZE:
            raise bad("invalid volume name length")

        self.disktype = disktype
        self.root = root
        self.B = B
        self.R = R
        self.rescluster = R // B
        self.rblkcluster = rblkcluster
        self.ipb = R // 4 - 3
        self.lpb = R // 4 - 3
        self.apb = (R - 16) // 12
        self.options = options
        self.split = bool(options & MODE_SPLITTED_ANODES)
        self.supermode = bool(options & MODE_SUPERINDEX)
        self.firstreserved = self._r32(RB_FIRSTRESERVED)
        self.lastreserved = self._r32(RB_LASTRESERVED)
        self.read_only_reason = None

        # the size of the volume: the root block knows it
        num_sectors = io.get_num_sectors()
        self.numblocks = io.num_blocks
        if options & MODE_SIZEFIELD:
            disksize = self._r32(RB_DISKSIZE)
            if disksize != num_sectors:
                spb = io.sec_per_blk
                first = (io.first_sector + spb - 1) // spb * spb
                last_start = (io.first_sector + disksize - spb) // spb * spb
                self.numblocks = max(0, (last_start - first) // spb + 1)
                if self.numblocks > io.num_blocks:
                    self._set_read_only(
                        "volume of %d sectors larger than the image of %d"
                        % (disksize, num_sectors)
                    )

        # allocation geometry
        fr, lr = self.firstreserved, self.lastreserved
        if fr < ROOTBLOCK or fr > lr or lr >= self.numblocks:
            raise bad("invalid reserved area %d..%d" % (fr, lr))
        if (lr - fr + 1) % self.rescluster:
            raise bad("reserved area no multiple of reserved blocks")
        self.numreserved = (lr - fr + 1) // self.rescluster
        if rblkcluster * B < 524:
            raise bad("root block cluster too small")
        if rblkcluster > self.numreserved * self.rescluster:
            raise bad("root block cluster larger than the reserved area")
        capacity = (rblkcluster * B - 524) // 4 * 32
        if self.numreserved > capacity:
            raise bad("reserved bitmap too small")
        if self._r32(RB_RESERVED_FREE) > self.numreserved:
            raise bad("invalid reserved_free")
        self.bitmapstart = lr + 1
        self.data_bits = self.numblocks - self.bitmapstart
        longs = (self.data_bits + 31) // 32
        self.no_bmb = (longs + self.lpb - 1) // self.lpb
        num_bmi = MAXBITMAPINDEX + 1 if self.supermode else MAXSMALLBITMAPINDEX + 1
        for i in range(num_bmi):
            blk = self._r32(RB_BITMAPINDEX + 4 * i)
            if blk and not fr <= blk <= lr:
                raise bad("bitmap index %d outside the reserved area" % i)
        if (self.no_bmb + self.ipb - 1) // self.ipb > num_bmi:
            raise bad("volume too large for its bitmap index")

        if options & ~MODE_KNOWN:
            self._set_read_only("unknown option flags 0x%x" % (options & ~MODE_KNOWN))
        if self._r32(RB_BLOCKSFREE) > self.data_bits:
            self._set_read_only("invalid number of free blocks")

        # root block extension
        self.has_ext = False
        if options & MODE_EXTENSION:
            ext = self._r32(RB_EXTENSION)
            if not fr <= ext <= lr:
                raise bad("root block extension outside the reserved area")
            data = bytearray(io.read(ext, self.rescluster))
            if u16(data, BLK_ID) == ID_EX:
                self._cache[("EX", 0)] = Res("EX", 0, ext, data)
                self.has_ext = True
        if not self.has_ext:
            if self.supermode:
                raise bad("supermode volume without root block extension")
            self._set_read_only("no root block extension")
        else:
            ext = self.get_ext().data
            if self.supermode and not any(
                u32(ext, EX_SUPERINDEX + 4 * k) for k in range(MAXSUPER + 1)
            ):
                raise bad("supermode volume without super blocks")
            if u32(ext, EX_TOBEDONE) != PP_NONE:
                self._set_read_only(
                    "an interrupted operation (%d) is pending: mount the volume"
                    " with the PFS3 handler once to complete it" % u32(ext, EX_TOBEDONE)
                )
        if not self.split and self.supermode:
            raise bad("supermode volume without split anodes")

    def _set_read_only(self, reason):
        if self.read_only_reason is None:
            self.read_only_reason = reason

    def check_writable(self):
        if self.read_only_reason is not None:
            raise FSError(VOLUME_READ_ONLY, extra="PFS3: " + self.read_only_reason)

    def rollback(self):
        """drop all changes not committed: read the volume again"""
        self._reset_state()
        self._load_root()

    # ----- root block fields -----

    def _r16(self, off):
        return u16(self.root, off)

    def _r32(self, off):
        return u32(self.root, off)

    def _w16(self, off, v):
        p16(self.root, off, v)

    def _w32(self, off, v):
        p32(self.root, off, v)

    def get_volume_name(self):
        n = self.root[RB_DISKNAME]
        return bytes(self.root[RB_DISKNAME + 1 : RB_DISKNAME + 1 + n])

    def set_volume_name(self, name):
        if not 1 <= len(name) <= MAX_VOLNAME:
            raise ValueError("invalid volume name length")
        self.root[RB_DISKNAME : RB_DISKNAME + DNSIZE] = bytes(DNSIZE)
        self.root[RB_DISKNAME] = len(name)
        self.root[RB_DISKNAME + 1 : RB_DISKNAME + 1 + len(name)] = name
        self._dirty = True

    def get_creation_date(self):
        return struct.unpack_from(">HHH", self.root, RB_CREATION)

    def set_creation_date(self, date):
        struct.pack_into(">HHH", self.root, RB_CREATION, *date)
        self._dirty = True

    def get_root_date(self):
        if self.has_ext:
            return struct.unpack_from(">HHH", self.get_ext().data, EX_ROOT_DATE)
        return self.get_creation_date()

    def set_root_date(self, date):
        if self.has_ext:
            ex = self.get_ext()
            struct.pack_into(">HHH", ex.data, EX_ROOT_DATE, *date)
            self._mark(ex)

    def get_volume_date(self):
        if self.has_ext:
            return struct.unpack_from(">HHH", self.get_ext().data, EX_VOLUME_DATE)
        return None

    def set_volume_date(self, date):
        """set the date of the last commit: the commit keeps it"""
        if self.has_ext:
            self._set_volume_date = tuple(date)
            self._dirty = True

    def get_blocks_free(self):
        return self._r32(RB_BLOCKSFREE)

    def get_always_free(self):
        return self._r32(RB_ALWAYSFREE)

    def get_datestamp(self):
        return self._r32(RB_DATESTAMP)

    def is_largefile(self):
        return bool(self.options & MODE_LARGEFILE)

    def has_dir_extension(self):
        return bool(self.options & MODE_DIR_EXTENSION)

    def get_fnsize(self):
        """the name size: names are at most fnsize - 1 bytes long"""
        fnsize = DEFAULT_FNSIZE
        if self.has_ext and self.options & MODE_LONGFN:
            fnsize = u16(self.get_ext().data, EX_FNSIZE)
            if fnsize < 30:
                fnsize = DEFAULT_FNSIZE
            elif fnsize >= FNSIZE:
                fnsize = MAX_FNSIZE
        return fnsize

    def get_max_name_len(self):
        return self.get_fnsize() - 1

    def get_max_file_size(self):
        return MAX_LARGE_FILE_SIZE if self.is_largefile() else MAX_FILE_SIZE

    def deldir_enabled(self):
        if not (self.options & MODE_DELDIR and self.options & MODE_DIR_EXTENSION):
            return False
        if self.has_ext and self.options & MODE_SUPERDELDIR:
            return u16(self.get_ext().data, EX_DELDIRSIZE) > 0
        return self._r32(RB_DELDIR) != 0

    def get_deldir_size(self):
        """the number of deldir blocks"""
        if not self.deldir_enabled():
            return 0
        if self.has_ext and self.options & MODE_SUPERDELDIR:
            return min(u16(self.get_ext().data, EX_DELDIRSIZE), MAXDELDIR + 1)
        return 1

    # ----- reserved bitmap -----

    def _res_bit_off(self, i):
        return RB_RESBITMAP_BITS + 4 * (i // 32), 1 << (31 - (i % 32))

    def is_res_free(self, blocknr):
        i = (blocknr - self.firstreserved) // self.rescluster
        off, mask = self._res_bit_off(i)
        return bool(u32(self.root, off) & mask)

    def _res_index(self, blocknr):
        if (
            blocknr < self.firstreserved
            or blocknr > self.lastreserved
            or (blocknr - self.firstreserved) % self.rescluster
        ):
            raise self._block_error(
                INVALID_RESERVED_BLOCK, "not a reserved block", blocknr
            )
        return (blocknr - self.firstreserved) // self.rescluster

    def _get_res_roving(self):
        if not self.has_ext:
            return 0
        roving = u32(self.get_ext().data, EX_RESERVED_ROVING)
        if not self.options & MODE_EXTROVING:
            roving *= 32
        return roving if roving < self.numreserved else 0

    def _set_res_roving(self, bit):
        if self.has_ext:
            ex = self.get_ext()
            if not self.options & MODE_EXTROVING:
                bit //= 32
            p32(ex.data, EX_RESERVED_ROVING, bit)

    def alloc_reserved(self):
        """allocate a reserved block that is free on disk: the first free
        one from the roving pointer on, wrapping around"""
        n = self.numreserved
        nwords = (n + 31) // 32
        start = self._get_res_roving()
        w0 = start // 32
        head_mask = 0xFFFFFFFF >> (start % 32)
        root = self.root
        # the first word from start on, all other words, and last the bits
        # of the first word before start
        for step in range(nwords + 1):
            w = (w0 + step) % nwords
            off = RB_RESBITMAP_BITS + 4 * w
            word = u32(root, off)
            if step == 0:
                word &= head_mask
            elif step == nwords:
                word &= ~head_mask & 0xFFFFFFFF
            if not word:
                continue
            bit = 32 - word.bit_length()
            i = w * 32 + bit
            if i >= n:
                continue
            p32(root, off, u32(root, off) & ~(1 << (31 - bit)))
            self._w32(RB_RESERVED_FREE, self._r32(RB_RESERVED_FREE) - 1)
            self._set_res_roving(i + 1 if i + 1 < n else 0)
            self._dirty = True
            return self.firstreserved + i * self.rescluster
        raise FSError(NO_FREE_BLOCKS, extra="PFS3: reserved area full")

    def free_reserved(self, blocknr):
        """free a reserved block once the change is committed"""
        self._res_index(blocknr)
        self._pending_res_free.append(blocknr)
        self._dirty = True

    def _apply_res_frees(self):
        for blocknr in self._pending_res_free:
            i = self._res_index(blocknr)
            off, mask = self._res_bit_off(i)
            word = u32(self.root, off)
            if not word & mask:
                p32(self.root, off, word | mask)
                self._w32(RB_RESERVED_FREE, self._r32(RB_RESERVED_FREE) + 1)
        self._pending_res_free = []

    # ----- reserved blocks -----

    def _read_res(self, kind, key, blocknr, seqnr=None, dir_anode=None):
        self._res_index(blocknr)
        data = bytearray(self.io.read(blocknr, self.rescluster))
        if u16(data, BLK_ID) != KIND_IDS[kind]:
            raise self._block_error(
                INVALID_RESERVED_BLOCK,
                "%s block expected, found id 0x%04x" % (kind, u16(data, BLK_ID)),
                blocknr,
            )
        if seqnr is not None and u32(data, BLK_SEQNR) != seqnr:
            raise self._block_error(
                INVALID_RESERVED_BLOCK,
                "%s block %d has seqnr %d" % (kind, seqnr, u32(data, BLK_SEQNR)),
                blocknr,
            )
        if dir_anode is not None and u32(data, DB_ANODENR) != dir_anode:
            raise self._block_error(
                INVALID_USER_DIR_BLOCK,
                "dir block of directory %d belongs to %d"
                % (dir_anode, u32(data, DB_ANODENR)),
                blocknr,
            )
        res = Res(kind, key, blocknr, data)
        self._cache[(kind, key)] = res
        return res

    def _new_res(self, kind, key, seqnr=None):
        blocknr = self.alloc_reserved()
        data = bytearray(self.R)
        p16(data, BLK_ID, KIND_IDS[kind])
        if seqnr is not None:
            p32(data, BLK_SEQNR, seqnr)
        res = Res(kind, key, blocknr, data, new=True)
        self._cache[(kind, key)] = res
        self._mark(res)
        return res

    def _mark(self, res):
        res.dirty = True
        self._dirty_res.add(res)
        self._dirty = True

    def _drop(self, res):
        """forget a block that is freed: it is not written"""
        del self._cache[(res.kind, res.key)]
        self._dirty_res.discard(res)

    def get_ext(self):
        return self._cache[("EX", 0)]

    def _get_mi(self, i):
        res = self._cache.get(("MI", i))
        if res is None:
            blocknr = self._r32(RB_BITMAPINDEX + 4 * i)
            if not blocknr:
                raise self._block_error(
                    INVALID_BITMAP_BLOCK, "bitmap index block %d missing" % i
                )
            res = self._read_res("MI", i, blocknr, seqnr=i)
        return res

    def _get_bm(self, s):
        res = self._cache.get(("BM", s))
        if res is None:
            mi = self._get_mi(s // self.ipb)
            blocknr = u32(mi.data, BLK_INDEX + 4 * (s % self.ipb))
            if not blocknr:
                raise self._block_error(
                    INVALID_BITMAP_BLOCK, "bitmap block %d missing" % s
                )
            res = self._read_res("BM", s, blocknr, seqnr=s)
        return res

    def _get_sb(self, k, create=False):
        res = self._cache.get(("SB", k))
        if res is None:
            ex = self.get_ext()
            blocknr = u32(ex.data, EX_SUPERINDEX + 4 * k)
            if not blocknr:
                if not create:
                    return None
                res = self._new_res("SB", k, seqnr=k)
                p32(ex.data, EX_SUPERINDEX + 4 * k, res.blocknr)
                self._mark(ex)
                return res
            res = self._read_res("SB", k, blocknr, seqnr=k)
        return res

    def _get_ib(self, i, create=False):
        res = self._cache.get(("IB", i))
        if res is not None:
            return res
        if self.supermode:
            k = i // self.ipb
            if k > MAXSUPER:
                return None
            sb = self._get_sb(k, create)
            if sb is None:
                return None
            off = BLK_INDEX + 4 * (i % self.ipb)
            blocknr = u32(sb.data, off)
            if not blocknr:
                if not create:
                    return None
                res = self._new_res("IB", i, seqnr=i)
                p32(sb.data, off, res.blocknr)
                self._mark(sb)
                return res
        else:
            if i > MAXSMALLINDEXNR:
                return None
            off = RB_INDEXBLOCKS + 4 * i
            blocknr = self._r32(off)
            if not blocknr:
                if not create:
                    return None
                res = self._new_res("IB", i, seqnr=i)
                self._w32(off, res.blocknr)
                return res
        return self._read_res("IB", i, blocknr, seqnr=i)

    def _get_ab(self, seqnr, create=False):
        res = self._cache.get(("AB", seqnr))
        if res is not None:
            return res
        ib = self._get_ib(seqnr // self.ipb, create)
        if ib is None:
            return None
        off = BLK_INDEX + 4 * (seqnr % self.ipb)
        blocknr = u32(ib.data, off)
        if not blocknr:
            if not create:
                return None
            res = self._new_res("AB", seqnr, seqnr=seqnr)
            p32(ib.data, off, res.blocknr)
            self._mark(ib)
            if self._max_ab_seqnr is not None:
                self._max_ab_seqnr = max(self._max_ab_seqnr, seqnr)
            return res
        return self._read_res("AB", seqnr, blocknr, seqnr=seqnr)

    def _get_dd(self, s):
        res = self._cache.get(("DD", s))
        if res is None:
            if self.has_ext and self.options & MODE_SUPERDELDIR:
                blocknr = u32(self.get_ext().data, EX_DELDIR + 4 * s)
            elif s == 0:
                blocknr = self._r32(RB_DELDIR)
            else:
                blocknr = 0
            if not blocknr:
                return None
            res = self._read_res("DD", s, blocknr, seqnr=s)
        return res

    def get_dir_block(self, blocknr, owner, dir_anode):
        res = self._cache.get(("DB", blocknr))
        if res is None:
            res = self._read_res("DB", blocknr, blocknr, dir_anode=dir_anode)
        elif u32(res.data, DB_ANODENR) != dir_anode:
            raise self._block_error(
                INVALID_USER_DIR_BLOCK,
                "dir block of directory %d belongs to %d"
                % (dir_anode, u32(res.data, DB_ANODENR)),
                blocknr,
            )
        res.owner = owner
        return res

    # ----- anodes -----

    def anode_loc(self, nr):
        if self.split:
            seqnr, off = nr >> 16, nr & 0xFFFF
        else:
            seqnr, off = divmod(nr, self.apb)
        if off >= self.apb:
            raise FSError(INVALID_ANODE, extra="PFS3: invalid anode number %d" % nr)
        return seqnr, off

    def anode_nr(self, seqnr, off):
        if self.split:
            return (seqnr << 16) | off
        return seqnr * self.apb + off

    def get_anode(self, nr):
        """(clustersize, blocknr, next) of anode nr. The anodes of a block
        that does not exist are free"""
        seqnr, off = self.anode_loc(nr)
        ab = self._get_ab(seqnr)
        if ab is None:
            return (0, 0, 0)
        return struct.unpack_from(">III", ab.data, AB_NODES + 12 * off)

    def set_anode(self, nr, clustersize, blocknr, next):
        seqnr, off = self.anode_loc(nr)
        ab = self._get_ab(seqnr)
        if ab is None:
            raise FSError(INVALID_ANODE, extra="PFS3: anode block of %d missing" % nr)
        struct.pack_into(
            ">III",
            ab.data,
            AB_NODES + 12 * off,
            clustersize & 0xFFFFFFFF,
            blocknr & 0xFFFFFFFF,
            next & 0xFFFFFFFF,
        )
        self._mark(ab)

    def get_max_anode_seqnr(self):
        """the highest anode block that exists"""
        if self._max_ab_seqnr is None:
            best = -1
            if self.supermode:
                num_ib = (MAXSUPER + 1) * self.ipb
            else:
                num_ib = MAXSMALLINDEXNR + 1
            i = 0
            while i < num_ib:
                if self.supermode and i % self.ipb == 0:
                    if self._get_sb(i // self.ipb) is None:
                        i += self.ipb
                        continue
                ib = self._get_ib(i)
                if ib is not None:
                    for j in range(self.ipb - 1, -1, -1):
                        if u32(ib.data, BLK_INDEX + 4 * j):
                            best = max(best, i * self.ipb + j)
                            break
                i += 1
            self._max_ab_seqnr = best
        return self._max_ab_seqnr

    def _max_seqnr_limit(self):
        if self.supermode:
            limit = (MAXSUPER + 1) * self.ipb * self.ipb - 1
        else:
            limit = (MAXSMALLINDEXNR + 1) * self.ipb - 1
        if self.split:
            limit = min(limit, MAX_ANODE_SEQNR)
        return limit

    def _find_free_anode(self, ab, first, last):
        data = ab.data
        for off in range(first, last):
            o = AB_NODES + 12 * off
            if data[o : o + 12] == bytes(12):
                nr = self.anode_nr(ab.key, off)
                if nr > ANODE_BADBLOCKS:
                    return nr
        return None

    def alloc_anode(self, connect=None):
        """allocate an anode and mark it allocated, but empty. With connect,
        try the block of anode connect first, its reserved slots, too"""
        apb = self.apb
        if connect:
            seqnr, _ = self.anode_loc(connect)
            ab = self._get_ab(seqnr)
            if ab is not None:
                nr = self._find_free_anode(ab, 0, apb)
                if nr is not None:
                    self.set_anode(nr, 0, ANODE_EMPTY_BLOCKNR, 0)
                    return nr
        max_seqnr = self.get_max_anode_seqnr()
        start = 0
        if self.has_ext:
            start = u16(self.get_ext().data, EX_CURRANSEQNR)
        if start > max_seqnr:
            start = 0
        for n in range(max_seqnr + 1):
            seqnr = (start + n) % (max_seqnr + 1)
            ab = self._get_ab(seqnr)
            if ab is None:
                continue
            nr = self._find_free_anode(ab, 0, apb - RESERVEDANODES)
            if nr is not None:
                self.set_anode(nr, 0, ANODE_EMPTY_BLOCKNR, 0)
                self._set_curranseqnr(seqnr)
                return nr
        # a new anode block: after the highest, or in a gap
        seqnr = max_seqnr + 1
        if seqnr > self._max_seqnr_limit():
            seqnr = None
            for s in range(max_seqnr + 1):
                if self._get_ab(s) is None:
                    seqnr = s
                    break
            if seqnr is None:
                raise FSError(NO_FREE_BLOCKS, extra="PFS3: no free anodes")
        ab = self._get_ab(seqnr, create=True)
        nr = self._find_free_anode(ab, 0, apb)
        self.set_anode(nr, 0, ANODE_EMPTY_BLOCKNR, 0)
        self._set_curranseqnr(seqnr)
        return nr

    def _set_curranseqnr(self, seqnr):
        if self.has_ext:
            p16(self.get_ext().data, EX_CURRANSEQNR, seqnr)

    def free_anode(self, nr):
        if nr <= ANODE_BADBLOCKS:
            raise FSError(INVALID_ANODE, extra="PFS3: freeing reserved anode %d" % nr)
        self.set_anode(nr, 0, 0, 0)

    def get_chain(self, head):
        """the anodes of the chain from head: [(nr, clustersize, blocknr, next)]"""
        out = []
        seen = set()
        nr = head
        while True:
            if nr in seen:
                raise FSError(INVALID_ANODE, extra="PFS3: anode chain %d loops" % head)
            seen.add(nr)
            cs, bn, nx = self.get_anode(nr)
            out.append((nr, cs, bn, nx))
            if nx == 0:
                return out
            nr = nx

    # ----- main bitmap -----

    def _bm_pos(self, k):
        L = k // 32
        s, off = divmod(L, self.lpb)
        return s, BLK_INDEX + 4 * off, 1 << (31 - (k % 32))

    def is_data_free(self, blocknr):
        k = blocknr - self.bitmapstart
        if k < 0 or k >= self.data_bits:
            raise FSError(
                INVALID_BITMAP_BLOCK, extra="PFS3: block %d not in data area" % blocknr
            )
        s, off, mask = self._bm_pos(k)
        return bool(u32(self._get_bm(s).data, off) & mask)

    def get_roving(self):
        k = self._r32(RB_ROVING_PTR) * 32
        if self.has_ext:
            k += u16(self.get_ext().data, EX_ROVINGBIT) & 31
        return k if k < self.data_bits else 0

    def _set_roving(self, k):
        if k >= self.data_bits:
            k = 0
        self._w32(RB_ROVING_PTR, k // 32)
        if self.has_ext:
            p16(self.get_ext().data, EX_ROVINGBIT, k % 32)

    def get_alloc_available(self):
        free = self.get_blocks_free()
        reserve = self.get_always_free()
        return free - reserve if free > reserve else 0

    def alloc_data(self, num, near=None):
        """allocate num data blocks that are free on disk.
        Returns runs [(blocknr, count)]"""
        if num == 0:
            return []
        if num > self.get_alloc_available():
            raise FSError(
                NO_FREE_BLOCKS,
                extra="PFS3: want %d blocks, %d available"
                % (num, self.get_alloc_available()),
            )
        total = self.data_bits
        if near is not None and 0 <= near - self.bitmapstart < total:
            k = near - self.bitmapstart
        else:
            k = self.get_roving()
        runs = []
        left = num
        scanned = 0
        while left > 0 and scanned < total:
            s, off, _ = self._bm_pos(k)
            bm = self._get_bm(s)
            data = bm.data
            word = u32(data, off)
            bit = k % 32
            if word & (0xFFFFFFFF >> bit) == 0:
                step = min(32 - bit, total - k)
                k += step
                scanned += step
            else:
                changed = False
                while bit < 32 and left > 0 and k < total:
                    mask = 1 << (31 - bit)
                    if word & mask:
                        word &= ~mask
                        changed = True
                        blk = self.bitmapstart + k
                        if runs and runs[-1][0] + runs[-1][1] == blk:
                            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
                        else:
                            runs.append((blk, 1))
                        left -= 1
                    bit += 1
                    k += 1
                    scanned += 1
                if changed:
                    p32(data, off, word)
                    self._mark(bm)
            if k >= total:
                k = 0
        if left > 0:
            # the free count is wrong: the bitmap has fewer free blocks
            raise FSError(INVALID_BITMAP_BLOCK, extra="PFS3: free block count mismatch")
        self._w32(RB_BLOCKSFREE, self.get_blocks_free() - num)
        self._set_roving(k)
        self._data_allocated = True
        self._dirty = True
        return runs

    def free_data(self, blocknr, count):
        """free count data blocks from blocknr once the change is committed"""
        if count == 0:
            return
        k = blocknr - self.bitmapstart
        if k < 0 or k + count > self.data_bits:
            raise FSError(
                INVALID_ANODE,
                extra="PFS3: blocks %d+%d outside the data area" % (blocknr, count),
            )
        self._pending_data_free.append((blocknr, count))
        self._dirty = True

    def _apply_data_frees(self):
        freed = 0
        for blocknr, count in self._pending_data_free:
            k = blocknr - self.bitmapstart
            for i in range(k, k + count):
                s, off, mask = self._bm_pos(i)
                bm = self._get_bm(s)
                word = u32(bm.data, off)
                if not word & mask:
                    p32(bm.data, off, word | mask)
                    self._mark(bm)
                    freed += 1
        self._pending_data_free = []
        self._w32(RB_BLOCKSFREE, self.get_blocks_free() + freed)

    # ----- data -----

    def read_blocks(self, blocknr, count):
        return self.io.read(blocknr, count)

    def write_blocks(self, blocknr, data):
        self.io.write(blocknr, data)

    def read_chain_data(self, head, size):
        """the first size bytes of the blocks of the anode chain at head"""
        B = self.B
        need = (size + B - 1) // B
        parts = []
        got = 0
        for nr, cs, bn, nx in self.get_chain(head):
            if got >= need:
                break
            if cs == 0:
                continue
            k = bn - self.bitmapstart
            if k < 0 or k + cs > self.data_bits:
                raise FSError(
                    INVALID_FILE_DATA_BLOCK,
                    extra="PFS3: anode %d: blocks %d+%d outside the data area"
                    % (nr, bn, cs),
                )
            n = min(cs, need - got)
            parts.append(self.io.read(bn, n))
            got += n
        if got < need:
            raise FSError(
                FILE_DATA_BLOCK_COUNT_MISMATCH,
                extra="PFS3: anode chain %d holds %d of %d blocks" % (head, got, need),
            )
        return b"".join(parts)[:size]

    def chain_block_count(self, head):
        return sum(cs for nr, cs, bn, nx in self.get_chain(head))

    def create_chain(self, data, connect=None):
        """allocate blocks for data, write it and build an anode chain.
        Returns the head anode"""
        B = self.B
        num = (len(data) + B - 1) // B
        runs = self.alloc_data(num)
        head = self.alloc_anode(connect)
        if not runs:
            return head
        off = 0
        prev = None
        for blocknr, count in runs:
            nbytes = count * B
            chunk = bytes(data[off : off + nbytes])
            if len(chunk) < nbytes:
                chunk += bytes(nbytes - len(chunk))
            self.io.write(blocknr, chunk)
            off += nbytes
            if prev is None:
                nr = head
            else:
                nr = self.alloc_anode(prev)
                cs, bn, _ = self.get_anode(prev)
                self.set_anode(prev, cs, bn, nr)
            self.set_anode(nr, count, blocknr, 0)
            prev = nr
        return head

    def free_chain(self, head, free_blocks=True, wipe=False):
        """free all anodes of the chain at head, and its blocks"""
        chain = self.get_chain(head)
        for nr, cs, bn, nx in chain:
            if free_blocks and cs and bn != ANODE_EMPTY_BLOCKNR:
                self.free_data(bn, cs)
                if wipe:
                    # cleared once the commit made the blocks free
                    self._pending_wipe.append((bn, cs))
        for nr, cs, bn, nx in chain:
            self.free_anode(nr)

    # ----- directories -----

    def dir_blocks(self, dir_anode):
        """the dir blocks of directory dir_anode, in chain order"""
        out = []
        for nr, cs, bn, nx in self.get_chain(dir_anode):
            if cs != 1:
                raise FSError(
                    INVALID_USER_DIR_BLOCK,
                    extra="PFS3: directory %d: anode %d has clustersize %d"
                    % (dir_anode, nr, cs),
                )
            out.append(self.get_dir_block(bn, nr, dir_anode))
        return out

    def block_entries(self, res):
        """[(offset, entry)] of a dir block, and the end of its entries"""
        data = res.data
        end = self.R
        off = DB_ENTRIES
        out = []
        dir_ext = self.has_dir_extension()
        while off < end and data[off] != 0:
            try:
                e, size = DirEntry.parse(data, off, end, dir_ext)
            except DirEntryError as exc:
                raise FSError(
                    INVALID_USER_DIR_BLOCK,
                    extra="PFS3: %s at offset %d" % (exc, off),
                    block=None,
                ) from None
            out.append((off, e))
            off += size
        if off >= end:
            raise FSError(
                INVALID_USER_DIR_BLOCK,
                extra="PFS3: dir block %d has no end of entries" % res.blocknr,
            )
        return out, off

    def dir_entries(self, dir_anode):
        """[(res, offset, entry)] of all entries of a directory"""
        out = []
        for res in self.dir_blocks(dir_anode):
            entries, _ = self.block_entries(res)
            for off, e in entries:
                out.append((res, off, e))
        return out

    def dir_parent(self, dir_anode):
        res = self.dir_blocks(dir_anode)[0]
        return u32(res.data, DB_PARENT)

    def find_entry(self, dir_anode, anode):
        for res, off, e in self.dir_entries(dir_anode):
            if e.anode == anode:
                return res, off, e
        return None

    def find_name(self, dir_anode, name):
        up = name_upper(name)
        for res, off, e in self.dir_entries(dir_anode):
            if len(e.name) == len(name) and name_upper(e.name) == up:
                return res, off, e
        return None

    def add_entry(self, dir_anode, entry):
        """add entry to directory dir_anode"""
        data = entry.build()
        size = len(data)
        area = self.R - DB_ENTRIES
        blocks = self.dir_blocks(dir_anode)
        for res in blocks:
            _, end = self.block_entries(res)
            used = end - DB_ENTRIES
            if used + size + 1 < area:
                res.data[end : end + size] = data
                res.data[end + size] = 0
                self._mark(res)
                return res
        # no room: a new dir block at the front of the chain
        parent = u32(blocks[0].data, DB_PARENT)
        res = self._new_dir_block(dir_anode, parent)
        new_anode = self.alloc_anode(dir_anode)
        cs, bn, nx = self.get_anode(dir_anode)
        self.set_anode(new_anode, cs, bn, nx)
        self.set_anode(dir_anode, 1, res.blocknr, new_anode)
        blocks[0].owner = new_anode
        res.owner = dir_anode
        res.data[DB_ENTRIES : DB_ENTRIES + size] = data
        res.data[DB_ENTRIES + size] = 0
        return res

    def _new_dir_block(self, dir_anode, parent):
        blocknr = self.alloc_reserved()
        data = bytearray(self.R)
        p16(data, BLK_ID, ID_DB)
        p32(data, DB_ANODENR, dir_anode)
        p32(data, DB_PARENT, parent)
        res = Res("DB", blocknr, blocknr, data, new=True)
        self._cache[("DB", blocknr)] = res
        self._mark(res)
        return res

    def remove_entry(self, dir_anode, res, off):
        """remove the entry at off of dir block res. A block that becomes
        empty leaves the chain, but the first"""
        data = res.data
        _, end = self.block_entries(res)
        size = data[off]
        data[off : end + 1 - size] = data[off + size : end + 1]
        data[end + 1 - size : self.R] = bytes(self.R - (end + 1 - size))
        self._mark(res)
        if data[DB_ENTRIES] == 0 and res.owner != dir_anode:
            self._drop_dir_block(dir_anode, res)

    def _drop_dir_block(self, dir_anode, res):
        owner = res.owner
        chain = self.get_chain(dir_anode)
        for i, (nr, cs, bn, nx) in enumerate(chain):
            if nx == owner:
                _, _, onx = self.get_anode(owner)
                self.set_anode(nr, cs, bn, onx)
                self.free_anode(owner)
                self.free_reserved(res.blocknr)
                self._drop(res)
                return
        raise FSError(INTERNAL_ERROR, extra="PFS3: dir block not in its chain")

    def replace_entry(self, dir_anode, res, off, entry):
        """replace the entry at off of dir block res with entry"""
        data = entry.build()
        if len(data) == res.data[off]:
            res.data[off : off + len(data)] = data
            self._mark(res)
            return
        self.remove_entry(dir_anode, res, off)
        self.add_entry(dir_anode, entry)

    def set_dir_parent(self, dir_anode, parent):
        for res in self.dir_blocks(dir_anode):
            if u32(res.data, DB_PARENT) != parent:
                p32(res.data, DB_PARENT, parent)
                self._mark(res)

    def create_dir_chain(self, parent):
        """a new, empty directory: its head anode"""
        nr = self.alloc_anode()
        res = self._new_dir_block(nr, parent)
        res.owner = nr
        self.set_anode(nr, 1, res.blocknr, 0)
        return nr

    def free_dir_chain(self, dir_anode):
        for nr, cs, bn, nx in self.get_chain(dir_anode):
            self.free_reserved(bn)
            res = self._cache.get(("DB", bn))
            if res is not None:
                self._drop(res)
            self.free_anode(nr)

    # ----- deldir -----

    def deldir_slots(self):
        """[(slot, res, offset, anodenr, fsize, date, name)] of the deldir"""
        out = []
        largefile = self.is_largefile()
        for s in range(self.get_deldir_size()):
            dd = self._get_dd(s)
            if dd is None:
                continue
            for j in range(DELENTRIES_PER_BLOCK):
                o = DD_ENTRIES + DELENTRY_SIZE * j
                anodenr = u32(dd.data, o)
                fsize = u32(dd.data, o + 4)
                date = struct.unpack_from(">HHH", dd.data, o + 8)
                nlen = dd.data[o + 14]
                if largefile and nlen < 16:
                    fsize |= u16(dd.data, o + 30) << 32
                nlen = min(nlen, 17)
                name = bytes(dd.data[o + 15 : o + 15 + nlen])
                out.append(
                    (s * DELENTRIES_PER_BLOCK + j, dd, o, anodenr, fsize, date, name)
                )
        return out

    def deldir_slot_valid(self, anodenr):
        """a deleted file can be recovered while all its blocks are free"""
        try:
            for nr, cs, bn, nx in self.get_chain(anodenr):
                if cs == 0:
                    continue
                for b in range(bn, bn + cs):
                    if not self.is_data_free(b):
                        return False
        except FSError:
            return False
        return True

    def _clean_deldir(self):
        """free the anodes of deleted files whose blocks were taken"""
        for slot, dd, o, anodenr, fsize, date, name in self.deldir_slots():
            if anodenr and not self.deldir_slot_valid(anodenr):
                try:
                    chain = self.get_chain(anodenr)
                except FSError:
                    chain = []
                for nr, cs, bn, nx in chain:
                    if nr > ANODE_BADBLOCKS:
                        self.free_anode(nr)
                p32(dd.data, o, 0)
                self._mark(dd)

    # ----- commit -----

    def is_dirty(self):
        return self._dirty

    def _relocate(self, res):
        """move a changed block of the volume on disk to a free block and
        point its parent to it"""
        old = res.blocknr
        new = self.alloc_reserved()
        self.free_reserved(old)
        res.blocknr = new
        kind = res.kind
        if kind == "DB":
            cs, bn, nx = self.get_anode(res.owner)
            if bn != old:
                raise FSError(INTERNAL_ERROR, extra="PFS3: dir block owner mismatch")
            self.set_anode(res.owner, cs, new, nx)
            del self._cache[("DB", res.key)]
            res.key = new
            self._cache[("DB", new)] = res
        elif kind == "AB":
            ib = self._get_ib(res.key // self.ipb)
            p32(ib.data, BLK_INDEX + 4 * (res.key % self.ipb), new)
            self._mark(ib)
        elif kind == "IB":
            if self.supermode:
                sb = self._get_sb(res.key // self.ipb)
                p32(sb.data, BLK_INDEX + 4 * (res.key % self.ipb), new)
                self._mark(sb)
            else:
                self._w32(RB_INDEXBLOCKS + 4 * res.key, new)
        elif kind == "SB":
            ex = self.get_ext()
            p32(ex.data, EX_SUPERINDEX + 4 * res.key, new)
            self._mark(ex)
        elif kind == "DD":
            if self.has_ext and self.options & MODE_SUPERDELDIR:
                ex = self.get_ext()
                p32(ex.data, EX_DELDIR + 4 * res.key, new)
                self._mark(ex)
            else:
                self._w32(RB_DELDIR, new)
        elif kind == "BM":
            mi = self._get_mi(res.key // self.ipb)
            p32(mi.data, BLK_INDEX + 4 * (res.key % self.ipb), new)
            self._mark(mi)
        elif kind == "MI":
            self._w32(RB_BITMAPINDEX + 4 * res.key, new)
        elif kind == "EX":
            self._w32(RB_EXTENSION, new)

    def commit(self, update_ts=True):
        """write all changes. The write of the root block cluster commits
        them; until then, only blocks free on disk are written"""
        if not self._dirty:
            return
        self.check_writable()
        stamp = self.get_datestamp() + 1
        # free data blocks, then the deleted files that lost a block
        self._apply_data_frees()
        if self._data_allocated and self.deldir_enabled() and self.has_ext:
            self._clean_deldir()
        # the extension changes with every commit
        if self.has_ext:
            ex = self.get_ext()
            p32(ex.data, EX_DATESTAMP, stamp)
            if self._set_volume_date is not None:
                struct.pack_into(
                    ">HHH", ex.data, EX_VOLUME_DATE, *self._set_volume_date
                )
            elif update_ts:
                struct.pack_into(">HHH", ex.data, EX_VOLUME_DATE, *amiga_now())
            self._mark(ex)
        # move the changed blocks, children before parents
        writes = []
        for kind in COMMIT_ORDER:
            for res in [r for r in self._dirty_res if r.kind == kind]:
                if not res.new:
                    self._relocate(res)
                writes.append(res)
        for res in writes:
            if res.kind == "EX":
                p32(res.data, EX_DATESTAMP, stamp)
            else:
                p32(res.data, BLK_DATESTAMP, stamp)
            self.io.write(res.blocknr, res.data)
        # commit
        self._w32(RB_DATESTAMP, stamp)
        self._w32(RB_OPTIONS, self._r32(RB_OPTIONS) | MODE_DATESTAMP)
        self.options |= MODE_DATESTAMP
        self.io.write(ROOTBLOCK, self.root)
        for res in writes:
            res.dirty = False
            res.new = False
        self._dirty_res = set()
        self._dirty = False
        self._data_allocated = False
        self._set_volume_date = None
        # the old locations are free now. The change is committed: if this
        # write fails, they only stay in use on disk until the root block
        # cluster is written again
        if self._pending_res_free:
            self._apply_res_frees()
            try:
                self.io.write(ROOTBLOCK, self.root)
            except IOError:
                self._dirty = True
        wipe, self._pending_wipe = self._pending_wipe, []
        for bn, cs in wipe:
            for b in range(bn, bn + cs, 256):
                n = min(256, bn + cs - b)
                self.io.write(b, bytes(n * self.B))
        self.io.flush()

    # ----- format -----

    def format(
        self,
        name,
        date=None,
        disktype=None,
        largefile=False,
        fnsize=DEFAULT_FNSIZE,
        numreserved=None,
        dos_type=ID_PFS3,
        supermode=None,
        resblksize=None,
    ):
        """create a new, empty PFS3 volume as the pfs3aio formatter does.
        supermode and resblksize force a layout that the formatter would
        only choose for larger volumes"""
        force_super = supermode
        io = self.io
        io.set_block_size(io.get_default_block_size())
        B = io.block_size
        sector = io.sector_size
        S = io.get_num_sectors()
        numblocks = io.num_blocks
        if date is None:
            date = amiga_now()
        if not 1 <= len(name) <= MAX_VOLNAME:
            raise FSError(INVALID_VOLUME_NAME, extra="PFS3: 1 to 30 characters")
        if S > MAXDISKSIZE:
            raise FSError(INTERNAL_ERROR, extra="PFS3: volume too large to format")
        for v in (sector, B):
            if v < 512 or v > 4096 or v & (v - 1):
                raise FSError(INTERNAL_ERROR, extra="PFS3: invalid block size %d" % v)
        if not DEFAULT_FNSIZE <= fnsize <= MAX_FNSIZE:
            raise ValueError("fnsize must be in %d..%d" % (DEFAULT_FNSIZE, MAX_FNSIZE))

        # reserved block size and mode
        R = 1024
        supermode = False
        if S > MAXSMALLDISK:
            supermode = True
            if S > MAXDISKSIZE1K:
                R = 2048
                if S > MAXDISKSIZE2K:
                    R = 4096
        R = min(max(R, sector, B), 4096)
        if resblksize is not None:
            if resblksize not in (1024, 2048, 4096) or resblksize < max(sector, B):
                raise ValueError("invalid reserved block size %d" % resblksize)
            R = resblksize
        if force_super is not None and not force_super:
            if R > 1024 or disktype == ID_PFS2:
                raise ValueError("PFS\\2 volumes need supermode")
        if disktype is None:
            disktype = ID_PFS2 if (R > 1024 or B > sector or largefile) else ID_PFS1
        if disktype == ID_PFS1 and (R > 1024 or B > sector or largefile):
            raise FSError(INTERNAL_ERROR, extra="PFS3: this volume needs PFS\\2")
        if disktype == ID_PFS2:
            supermode = True
        elif force_super is not None:
            supermode = force_super
        rescluster = R // B

        # reserved area
        if numreserved is None:
            numreserved = self._calc_num_reserved(S, R)
        else:
            numreserved = min(numreserved, MAXNUMRESERVED)
            numreserved = max((numreserved + 31) & ~31, 32)
        reserved = rescluster * numreserved + ROOTBLOCK
        if numblocks < 128 or numblocks <= reserved:
            raise FSError(NO_FREE_BLOCKS, extra="PFS3: volume too small")

        # root block cluster with the reserved bitmap
        n1k = 1 + len(range(125, numreserved // 32, 256))
        nroot = (1024 * n1k + R - 1) // R
        rblkcluster = rescluster * nroot
        root = bytearray(rblkcluster * B)
        options = (
            MODE_HARDDISK
            | MODE_SPLITTED_ANODES
            | MODE_DIR_EXTENSION
            | MODE_SIZEFIELD
            | MODE_DATESTAMP
            | MODE_EXTROVING
            | MODE_LONGFN
            | MODE_EXTENSION
            | MODE_DELDIR
            | MODE_SUPERDELDIR
        )
        if supermode:
            options |= MODE_SUPERINDEX
        if largefile:
            options |= MODE_LARGEFILE
        low_cyl = io.dos_env.low_cyl if io.dos_env is not None else 0
        if low_cyl == 0 or disktype == ID_PFS2:
            options |= MODE_STORED_GEOM
        p32(root, RB_DISKTYPE, disktype)
        p32(root, RB_OPTIONS, options)
        p32(root, RB_DATESTAMP, 1)
        struct.pack_into(">HHH", root, RB_CREATION, *date)
        p16(root, RB_PROTECTION, 0xF0)
        root[RB_DISKNAME] = len(name)
        root[RB_DISKNAME + 1 : RB_DISKNAME + 1 + len(name)] = name
        p32(root, RB_FIRSTRESERVED, ROOTBLOCK)
        p32(root, RB_LASTRESERVED, reserved - 1)
        p16(root, RB_RESERVED_BLKSIZE, R)
        p16(root, RB_RBLKCLUSTER, rblkcluster)
        blocksfree = numblocks - reserved
        p32(root, RB_BLOCKSFREE, blocksfree)
        p32(root, RB_ALWAYSFREE, blocksfree // 20)
        p32(root, RB_DISKSIZE, S)
        p32(root, RB_EXTENSION, ROOTBLOCK + rblkcluster)
        p16(root, RB_RESBITMAP, ID_BM)
        for i in range(numreserved // 32):
            p32(root, RB_RESBITMAP_BITS + 4 * i, 0xFFFFFFFF)
        # the root block cluster and the extension are taken
        for i in range(nroot + 1):
            off = RB_RESBITMAP_BITS + 4 * (i // 32)
            p32(root, off, u32(root, off) & ~(1 << (31 - i % 32)))
        p32(root, RB_RESERVED_FREE, numreserved - nroot - 1)

        # set up the engine on the new root block
        self._reset_state()
        self.disktype = disktype
        self.root = root
        self.B = B
        self.R = R
        self.rescluster = rescluster
        self.rblkcluster = rblkcluster
        self.ipb = self.lpb = R // 4 - 3
        self.apb = (R - 16) // 12
        self.options = options
        self.split = True
        self.supermode = supermode
        self.firstreserved = ROOTBLOCK
        self.lastreserved = reserved - 1
        self.numreserved = numreserved
        self.numblocks = numblocks
        self.bitmapstart = reserved
        self.data_bits = numblocks - reserved
        self.no_bmb = ((self.data_bits + 31) // 32 + self.lpb - 1) // self.lpb
        self.read_only_reason = None
        self.has_ext = True
        self._max_ab_seqnr = -1

        # extension
        ex = Res("EX", 0, ROOTBLOCK + rblkcluster, bytearray(R), new=True)
        self._cache[("EX", 0)] = ex
        d = ex.data
        p16(d, BLK_ID, ID_EX)
        p32(d, EX_PFS2VERSION, PFS2VERSION)
        struct.pack_into(">HHH", d, EX_ROOT_DATE, *date)
        p32(d, EX_RESERVED_ROVING, nroot + 1)
        p16(d, EX_FNSIZE, fnsize)
        p32(d, EX_DD_PROTECTION, DELENTRY_PROT)
        struct.pack_into(">HHH", d, EX_DD_CREATION, *date)
        env = self._get_format_dosenvec(dos_type)
        p32(d, EX_DOSENVEC, len(env))
        for i, v in enumerate(env):
            p32(d, EX_DOSENVEC + 4 * (i + 1), v)

        # main bitmap: all blocks free
        num_bmi = MAXBITMAPINDEX + 1 if supermode else MAXSMALLBITMAPINDEX + 1
        if (self.no_bmb + self.ipb - 1) // self.ipb > num_bmi:
            raise FSError(INTERNAL_ERROR, extra="PFS3: volume too large")
        for s in range(self.no_bmb):
            i = s // self.ipb
            if s % self.ipb == 0:
                mi = self._new_res("MI", i, seqnr=i)
                p32(root, RB_BITMAPINDEX + 4 * i, mi.blocknr)
            bm = self._new_res("BM", s, seqnr=s)
            bm.data[BLK_INDEX:] = b"\xff" * (R - BLK_INDEX)
            p32(self._cache[("MI", i)].data, BLK_INDEX + 4 * (s % self.ipb), bm.blocknr)

        # anodes 0 to 4 are taken, 5 is the root directory
        self._get_ab(0, create=True)
        self._max_ab_seqnr = 0
        for nr in range(ANODE_ROOTDIR):
            self.set_anode(nr, 0, ANODE_EMPTY_BLOCKNR, 0)
        rootdir = self._new_dir_block(ANODE_ROOTDIR, 0)
        rootdir.owner = ANODE_ROOTDIR
        self.set_anode(ANODE_ROOTDIR, 1, rootdir.blocknr, 0)

        # a deldir of two blocks
        for s in range(2):
            dd = self._new_res("DD", s, seqnr=s)
            p32(dd.data, DD_PROTECTION, DELENTRY_PROT)
            struct.pack_into(">HHH", dd.data, DD_CREATION, *date)
            p32(d, EX_DELDIR + 4 * s, dd.blocknr)
        p16(d, EX_DELDIRSIZE, 2)

        # write the reserved blocks, the boot blocks and last the root block
        for res in self._cache.values():
            p32(res.data, EX_DATESTAMP if res.kind == "EX" else BLK_DATESTAMP, 1)
            io.write(res.blocknr, res.data)
            res.dirty = False
            res.new = False
        boot = bytearray(2 * B)
        p32(boot, 0, ID_PFS1)
        io.write(BOOTBLOCK1, boot)
        io.write(ROOTBLOCK, root)
        io.flush()
        self._dirty_res = set()
        self._dirty = False
        self._data_allocated = False

    @staticmethod
    def _calc_num_reserved(S, R):
        taken = 32
        i = 2048
        while i and i // 2 < S:
            m = 10 if i >= 512 * 2048 else 14
            taken += taken * m // 16
            i = (i << 1) & 0xFFFFFFFF
        taken //= R // 1024
        taken = min(MAXNUMRESERVED, taken - 1)
        return (taken + 31) & ~31

    def _get_format_dosenvec(self, dos_type):
        """the DosEnvec from de_SizeBlock to de_DosType to store"""
        de = self.io.dos_env
        if de is not None:
            env = [
                de.block_size,
                de.sec_org,
                de.surfaces,
                de.sec_per_blk,
                de.blk_per_trk,
                de.reserved,
                de.pre_alloc,
                de.interleave,
                de.low_cyl,
                de.high_cyl,
                de.num_buffer,
                de.buf_mem_type,
                de.max_transfer,
                de.mask,
                de.boot_pri & 0xFFFFFFFF,
                de.dos_type,
            ]
            size = min(de.size, 16) if de.size else 16
            return env[:size]
        # a whole image: describe it with the geometry of the block device
        blkdev = self.blkdev
        sector = self.io.sector_size
        heads = getattr(blkdev, "heads", 1) or 1
        secs = getattr(blkdev, "sectors", 0) or 0
        cyls = getattr(blkdev, "cyls", 0) or 0
        if heads * secs * cyls != self.io.end_sector:
            heads, secs, cyls = 1, 1, self.io.end_sector
        return [
            sector // 4,
            0,
            heads,
            1,
            secs,
            2,
            0,
            0,
            0,
            cyls - 1,
            30,
            0,
            0xFFFFFF,
            0x7FFFFFFE,
            0,
            dos_type,
        ]
