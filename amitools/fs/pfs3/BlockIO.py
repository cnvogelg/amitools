"""Logical block access for PFS3.

PFS3 addresses the volume in logical blocks of B bytes, which can be larger
than a device sector, and aligns the partition to B in absolute device
sectors. This reads and writes physical sectors of the block device
directly to follow those rules."""

# read and write at most this many bytes at once
CHUNK_BYTES = 1024 * 1024

BLOCK_SIZES = (512, 1024, 2048, 4096)


def _round_down_pow2(b):
    for size in reversed(BLOCK_SIZES):
        if b >= size:
            return size
    return BLOCK_SIZES[0]


class PFS3BlockIO:
    def __init__(self, blkdev):
        self.blkdev = blkdev
        part_blk = getattr(blkdev, "part_blk", None)
        raw = getattr(blkdev, "raw_blkdev", None)
        if part_blk is not None and raw is not None:
            # a partition of an RDB disk: take the geometry from the DosEnvec
            de = part_blk.dos_env
            self.dos_env = de
            self.sector_size = de.block_size * 4
            self.env_sec_per_blk = max(de.sec_per_blk, 1)
            cyl_secs = de.surfaces * de.blk_per_trk
            self.first_sector = de.low_cyl * cyl_secs
            self.end_sector = (de.high_cyl + 1) * cyl_secs
            if raw.block_bytes != self.sector_size:
                raise IOError(
                    "PFS3: device block size %d differs from partition sector size %d"
                    % (raw.block_bytes, self.sector_size)
                )
            self._read_secs = raw.read_block
            self._write_secs = raw.write_block
        else:
            # a whole image: an HDF or ADF holds one volume from sector 0
            self.dos_env = None
            self.sector_size = blkdev.block_bytes
            self.env_sec_per_blk = 1
            self.first_sector = 0
            self.end_sector = blkdev.num_blocks
            img_file = getattr(blkdev, "img_file", None)
            if img_file is not None and img_file.block_bytes == self.sector_size:
                self._read_secs = img_file.read_blk
                self._write_secs = img_file.write_blk
            else:
                self._read_secs = self._read_secs_single
                self._write_secs = self._write_secs_single
        self.set_block_size(self.get_default_block_size())

    def _read_secs_single(self, sec, num):
        return b"".join(self.blkdev.read_block(sec + i) for i in range(num))

    def _write_secs_single(self, sec, data, num):
        ss = self.sector_size
        for i in range(num):
            self.blkdev.write_block(sec + i, bytes(data[i * ss : (i + 1) * ss]))

    def get_default_block_size(self):
        """the logical block size the partition asks for"""
        b = _round_down_pow2(self.sector_size * self.env_sec_per_blk)
        return max(b, self.sector_size)

    def get_probe_block_sizes(self):
        """the block sizes to try to find the root block, the configured one
        first. A partition can only fall back to the sector size, as PFS3
        before v20 formatted it. A whole image has no geometry to go by"""
        sizes = [self.block_size]
        if self.dos_env is not None:
            if self.sector_size not in sizes:
                sizes.append(self.sector_size)
        else:
            for b in BLOCK_SIZES:
                if b > self.sector_size and b % self.sector_size == 0:
                    if b not in sizes:
                        sizes.append(b)
        return sizes

    def set_block_size(self, block_size):
        if block_size % self.sector_size != 0:
            raise IOError("PFS3: invalid block size %d" % block_size)
        self.block_size = block_size
        spb = block_size // self.sector_size
        self.sec_per_blk = spb
        # align to the block size in absolute sectors
        first = (self.first_sector + spb - 1) // spb * spb
        last_start = (self.end_sector - spb) // spb * spb
        self.first_block = first // spb
        if last_start < first:
            self.num_blocks = 0
        else:
            self.num_blocks = last_start // spb - self.first_block + 1

    def get_num_sectors(self):
        """partition size in physical sectors (disksize of the root block)"""
        return self.end_sector - self.first_sector

    def read(self, blk, num=1):
        if blk < 0 or num < 0 or blk + num > self.num_blocks:
            raise IOError(
                "PFS3: read of blocks %d+%d beyond volume of %d blocks"
                % (blk, num, self.num_blocks)
            )
        spb = self.sec_per_blk
        sec = (self.first_block + blk) * spb
        total = num * spb
        chunk = max(CHUNK_BYTES // self.sector_size, spb)
        if total <= chunk:
            data = self._read_secs(sec, total)
        else:
            parts = []
            done = 0
            while done < total:
                n = min(chunk, total - done)
                parts.append(self._read_secs(sec + done, n))
                done += n
            data = b"".join(parts)
        if len(data) != num * self.block_size:
            raise IOError("PFS3: short read at block %d" % blk)
        return data

    def write(self, blk, data):
        bs = self.block_size
        if len(data) % bs != 0:
            raise IOError(
                "PFS3: write of %d bytes is no multiple of blocks" % len(data)
            )
        num = len(data) // bs
        if blk < 0 or blk + num > self.num_blocks:
            raise IOError(
                "PFS3: write of blocks %d+%d beyond volume of %d blocks"
                % (blk, num, self.num_blocks)
            )
        spb = self.sec_per_blk
        ss = self.sector_size
        sec = (self.first_block + blk) * spb
        total = num * spb
        chunk = max(CHUNK_BYTES // ss, spb)
        done = 0
        while done < total:
            n = min(chunk, total - done)
            self._write_secs(sec + done, bytes(data[done * ss : (done + n) * ss]), n)
            done += n

    def flush(self):
        self.blkdev.flush()
