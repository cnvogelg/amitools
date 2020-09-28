from .BlockDevice import BlockDevice


class ADFBlockDevice(BlockDevice):

    # number of total sectors for DD/HD disks
    DD_SECS = 80 * 2 * 11
    HD_SECS = 80 * 2 * 22

    # byte size (without/with error code byte)
    DD_IMG_SIZES = (DD_SECS * 512, DD_SECS * 513)
    HD_IMG_SIZES = (HD_SECS * 512, HD_SECS * 513)

    def __init__(self, adf_file, read_only=False, fobj=None, hd=False):
        self.adf_file = adf_file
        self.read_only = read_only
        self.fobj = fobj
        self.dirty = False
        self.hd = hd

    def create(self):
        if self.read_only:
            raise IOError("ADF creation not allowed in read-only mode!")
        sectors = 22 if self.hd else 11
        self._set_geometry(sectors=sectors)  # set default geometry
        # allocate image in memory
        self.data = bytearray(self.num_bytes)
        self.dirty = True

    def open(self):
        sectors = 22 if self.hd else 11
        self._set_geometry(sectors=sectors)  # set default geometry
        # read from fobj or open adf file
        if self.fobj:
            data = self.fobj.read(self.num_bytes)
        else:
            fh = open(self.adf_file, "rb")
            data = fh.read(self.num_bytes)
            fh.close()
        # check size
        if len(data) != self.num_bytes:
            raise IOError(
                "Invalid ADF Size: got %d but expected %d" % (len(data), self.num_bytes)
            )
        # create modifyable data
        if self.read_only:
            self.data = data
        else:
            self.data = bytearray(data)

    def flush(self):
        # write dirty adf
        if self.dirty and not self.read_only:
            # write to fobj
            if self.fobj:
                # seek fobj to beginning
                self.fobj.seek(0, 0)
                self.fobj.write(self.data)
            # write to file
            else:
                fh = open(self.adf_file, "wb")
                fh.write(self.data)
                fh.close()
            self.dirty = False

    def close(self):
        self.flush()
        self.data = None
        # now close fobj
        if self.fobj:
            self.fobj.close()

    def read_block(self, blk_num):
        if blk_num >= self.num_blocks:
            raise ValueError(
                "Invalid ADF block num: got %d but max is %d"
                % (blk_num, self.num_blocks)
            )
        off = self._blk_to_offset(blk_num)
        return self.data[off : off + self.block_bytes]

    def write_block(self, blk_num, data):
        if self.read_only:
            raise IOError("ADF File is read-only!")
        if blk_num >= self.num_blocks:
            raise ValueError(
                "Invalid ADF block num: got %d but max is %d"
                % (blk_num, self.num_blocks)
            )
        if len(data) != self.block_bytes:
            raise ValueError(
                "Invalid ADF block size written: got %d but size is %d"
                % (len(data), self.block_bytes)
            )
        off = self._blk_to_offset(blk_num)
        self.data[off : off + self.block_bytes] = data
        self.dirty = True


# --- mini test ---
if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        # write to file device
        adf = ADFBlockDevice(a)
        adf.open()
        d = adf.read_block(0)
        adf.write_block(0, d)
        adf.close()
        # write via fobj
        fobj = open(a, "rb")
        adf = ADFBlockDevice(a, fobj=fobj)
        adf.open()
        d = adf.read_block(0)
        adf.write_block(0, d)
        adf.close()
