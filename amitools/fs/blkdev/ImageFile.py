import os
import stat
import amitools.util.BlkDevTools as BlkDevTools


class ImageFile:
    def __init__(self, file_name, read_only=False, block_bytes=512, fobj=None):
        self.file_name = file_name
        self.read_only = read_only
        self.block_bytes = block_bytes
        self.fobj = fobj
        self.size = 0
        self.num_blocks = 0

    @staticmethod
    def get_image_size(file_name):
        # is it a block/char device?
        st = os.stat(file_name)
        mode = st.st_mode
        if stat.S_ISBLK(mode) or stat.S_ISCHR(mode):
            return BlkDevTools.getblkdevsize(file_name)
        else:
            # get size and make sure its not empty
            return os.path.getsize(file_name)

    def open(self):
        # file obj?
        if self.fobj:
            # get size via seek
            self.fobj.seek(0, 2)  # end of file
            self.size = self.fobj.tell()
            self.fobj.seek(0, 0)  # return to begin
            self.num_blocks = self.size // self.block_bytes
        # file name given
        else:
            # is readable?
            if not os.access(self.file_name, os.R_OK):
                raise IOError("Can't read from image file")
            # is writeable?
            if not os.access(self.file_name, os.W_OK):
                self.read_only = True
            # get image size
            self.size = ImageFile.get_image_size(self.file_name)
            if self.size == 0:
                raise IOError("Empty image file detected!")
            self.num_blocks = self.size // self.block_bytes
            # open raw file
            if self.read_only:
                flags = "rb"
            else:
                flags = "r+b"
            self.fobj = open(self.file_name, flags)

    def read_blk(self, blk_num, num_blks=1):
        if blk_num >= self.num_blocks:
            raise IOError(
                "Invalid image file block num: got %d but max is %d"
                % (blk_num, self.num_blocks)
            )
        off = blk_num * self.block_bytes
        if off != self.fobj.tell():
            self.fobj.seek(off, os.SEEK_SET)
        num = self.block_bytes * num_blks
        data = self.fobj.read(num)
        return data

    def write_blk(self, blk_num, data, num_blks=1):
        if self.read_only:
            raise IOError("Can't write block: image file is read-only")
        if blk_num >= self.num_blocks:
            raise IOError(
                "Invalid image file block num: got %d but max is %d"
                % (blk_num, self.num_blocks)
            )
        if len(data) != (self.block_bytes * num_blks):
            raise IOError(
                "Invalid block size written: got %d but size is %d"
                % (len(data), self.block_bytes)
            )
        off = blk_num * self.block_bytes
        if off != self.fobj.tell():
            self.fobj.seek(off, os.SEEK_SET)
        self.fobj.write(data)

    def flush(self):
        self.fobj.flush()

    def close(self):
        self.fobj.close()
        self.fobj = None

    def create(self, num_blocks):
        if self.read_only:
            raise IOError("Can't create image file in read only mode")
        total_size = num_blocks * self.block_bytes
        if self.fobj is not None:
            self.fobj.truncate(total_size)
            self.fobj.seek(0, 0)
        else:
            fh = open(self.file_name, "wb")
            fh.truncate(total_size)
            fh.close()

    def resize(self, new_blocks):
        if self.read_only:
            raise IOError("Can't grow image file in read only mode")
        total_size = new_blocks * self.block_bytes
        if self.fobj is not None:
            self.fobj.truncate(total_size)
            self.fobj.seek(0, 0)  # seek start
        else:
            fh = open(self.file_name, "ab")
            fh.truncate(total_size)
            fh.close()


# --- mini test ---
if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        # read image
        im = ImageFile(a)
        im.open()
        d = im.read_blk(0)
        im.write_blk(0, d)
        im.close()
        # read fobj
        fobj = open(a, "r+b")
        im = ImageFile(a, fobj=fobj)
        im.open()
        d = im.read_blk(0)
        im.write_blk(0, d)
        im.close()
