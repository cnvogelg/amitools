import os
import os.path
import stat
import gzip
from .ADFBlockDevice import ADFBlockDevice
from .HDFBlockDevice import HDFBlockDevice
from .RawBlockDevice import RawBlockDevice
from .DiskGeometry import DiskGeometry
from amitools.fs.rdb.RDisk import RDisk
import amitools.util.BlkDevTools as BlkDevTools


class BlkDevFactory:
    """the block device factory opens or creates image files suitable as a block device for file system access."""

    GZIP_MASK = 0x10
    TYPE_MASK = 0x0F

    TYPE_ADF = 1
    TYPE_HDF = 2
    TYPE_RDB = 3
    TYPE_ADF_HD = 4

    TYPE_ADF_GZ = TYPE_ADF | GZIP_MASK
    TYPE_HDF_GZ = TYPE_HDF | GZIP_MASK
    TYPE_RDB_GZ = TYPE_RDB | GZIP_MASK
    TYPE_ADF_HD_GZ = TYPE_ADF_HD | GZIP_MASK

    TYPE_MAP = {
        "adf": TYPE_ADF,
        "hdf": TYPE_HDF,
        "rdb": TYPE_RDB,
        "adf_hd": TYPE_ADF_HD,
        "adf.gz": TYPE_ADF_GZ,
        "hdf.gz": TYPE_HDF_GZ,
        "adf_hd.gz": TYPE_ADF_HD_GZ,
    }

    EXT_MAP = {
        ".adf": TYPE_ADF,
        ".adz": TYPE_ADF_GZ,
        ".adf.gz": TYPE_ADF_GZ,
        ".hdf": TYPE_HDF,
        ".hdz": TYPE_HDF_GZ,
        ".hdf.gz": TYPE_HDF_GZ,
        ".rdb": TYPE_RDB,
        ".rdisk": TYPE_RDB,
        ".rdb.gz": TYPE_RDB_GZ,
        ".rdisk.gz": TYPE_RDB_GZ,
    }

    def detect_type(self, img_file, fobj, options=None):
        """try to detect the type of a given img_file name"""
        # 1. take type from options
        t = self.type_from_options(options)
        if not t:
            # 2. look in file
            t = self.type_from_contents(img_file, fobj)
            if not t:
                # 3. from extension
                t = self.type_from_extension(img_file)
        return t

    def type_from_options(self, options):
        """look in options for type"""
        if options:
            if "type" in options:
                t = options["type"].lower()
                if t in self.TYPE_MAP:
                    return self.TYPE_MAP[t]
                else:
                    raise ValueError("invalid 'type' given: %s" % t)
        return None

    def type_from_contents(self, img_file, fobj):
        """look in first 4 bytes for type of image"""
        # load 4 bytes
        if fobj is None:
            # make sure file exists
            if not os.path.exists(img_file):
                return None
            f = open(img_file, "rb")
            hdr = f.read(4)
            f.close()
        else:
            hdr = fobj.read(4)
            fobj.seek(0, 0)
        # check for 'RDISK':
        if hdr == b"RDSK":
            return self.TYPE_RDB
        return None

    def type_from_extension(self, img_file):
        """look at file extension for type of image"""
        lo_name = img_file.lower()
        for ext, typ in self.EXT_MAP.items():
            if lo_name.endswith(ext):
                return typ
        return None

    def _get_block_size(self, options):
        if options and "bs" in options:
            bs = int(options["bs"])
            if bs % 512 != 0 and bs < 512:
                raise ValueError("invalid block size given: %d" % bs)
            return bs
        else:
            return 512

    def open(
        self, img_file, read_only=False, options=None, fobj=None, none_if_missing=False
    ):
        """open an existing image file"""
        # file base check
        if not fobj:
            # make sure image file exists
            if not os.path.exists(img_file):
                if none_if_missing:
                    return None
                raise IOError("image file not found")
            # is readable?
            if not os.access(img_file, os.R_OK):
                raise IOError("can't read from image file")
            # is writeable? -> no: enforce read_only
            if not os.access(img_file, os.W_OK):
                read_only = True

        # detect type
        t = self.detect_type(img_file, fobj, options)
        if t is None:
            raise IOError("can't detect type of image file")

        # is gzipped?
        if t & self.GZIP_MASK:
            # only supported for read access for now
            if not read_only:
                raise IOError("can't write gzip'ed image files!")
            # automatically wrap a fobj to unzip
            fobj = gzip.GzipFile(img_file, "rb", fileobj=fobj)
            # remove gzip flag from type
            t = t & self.TYPE_MASK

        # retrieve size
        if fobj:
            # get size from fobj
            fobj.seek(0, 2)
            size = fobj.tell()
            fobj.seek(0, 0)
        else:
            # get size from file/blk dev/char dev
            st = os.stat(img_file)
            mode = st.st_mode
            if stat.S_ISBLK(mode) or stat.S_ISCHR(mode):
                size = BlkDevTools.getblkdevsize(img_file)
            else:
                size = os.path.getsize(img_file)
            if size == 0:
                raise IOError("image file is empty")

        # get block size
        bs = self._get_block_size(options)

        # now create blkdev
        if t in (self.TYPE_ADF, self.TYPE_ADF_HD):
            # check sizes
            if size in ADFBlockDevice.DD_IMG_SIZES:
                hd = False
            elif size in ADFBlockDevice.HD_IMG_SIZES:
                hd = True
            else:
                raise IOError("invalid ADF images size: %d" % size)
            blkdev = ADFBlockDevice(img_file, read_only, fobj=fobj, hd=hd)
            blkdev.open()
        elif t == self.TYPE_HDF:
            # detect geometry
            geo = DiskGeometry(block_bytes=bs)
            if not geo.detect(size, options):
                raise IOError("can't detect geometry of HDF image file")
            blkdev = HDFBlockDevice(img_file, read_only, fobj=fobj, block_size=bs)
            blkdev.open(geo)
        else:
            rawdev = RawBlockDevice(img_file, read_only, fobj=fobj, block_bytes=bs)
            rawdev.open()
            # check block size stored in rdb
            rdisk = RDisk(rawdev)
            rdb_bs = rdisk.peek_block_size()
            if rdb_bs != bs:
                # adjust block size and re-open
                rawdev.close()
                bs = rdb_bs
                rawdev = RawBlockDevice(img_file, read_only, fobj=fobj, block_bytes=bs)
                rawdev.open()
                rdisk = RDisk(rawdev)
            if not rdisk.open():
                raise IOError("can't open rdisk of image file")
            # determine partition
            p = "0"
            if options != None and "part" in options:
                p = str(options["part"])
            part = rdisk.find_partition_by_string(p)
            if part == None:
                raise IOError("can't find partition in image file")
            blkdev = part.create_blkdev(True)  # auto_close rdisk
            blkdev.open()
        return blkdev

    def create(self, img_file, force=True, options=None, fobj=None):
        if fobj is None:
            # make sure we are allowed to overwrite existing file
            if os.path.exists(img_file):
                if not force:
                    raise IOError("can't overwrite existing image file")
                # not writeable?
                if not os.access(img_file, os.W_OK):
                    raise IOError("can't write image file")

        # detect type
        t = self.detect_type(img_file, fobj, options)
        if t is None:
            raise IOError("can't detect type of image file")
        if t & self.GZIP_MASK:
            raise IOError("can't create gzip'ed image files")
        if t == self.TYPE_RDB:
            raise IOError("can't create rdisk. use rdbtool first")

        # get block size
        bs = self._get_block_size(options)

        # create blkdev
        if t == self.TYPE_ADF:
            blkdev = ADFBlockDevice(img_file, fobj=fobj)
            blkdev.create()
        elif t == self.TYPE_ADF_HD:
            blkdev = ADFBlockDevice(img_file, fobj=fobj, hd=True)
            blkdev.create()
        else:
            # determine geometry from size or chs
            geo = DiskGeometry()
            if not geo.setup(options):
                raise IOError("can't determine geometry of HDF image file")
            blkdev = HDFBlockDevice(img_file, fobj=fobj, block_size=bs)
            blkdev.create(geo)
        return blkdev


# --- mini test ---
if __name__ == "__main__":
    import sys
    import io

    bdf = BlkDevFactory()
    for a in sys.argv[1:]:
        # open by file
        blkdev = bdf.open(a)
        print(a, blkdev.__class__.__name__)
        blkdev.close()
        # open via fobj
        fobj = open(a, "rb")
        data = fobj.read()
        nobj = io.StringIO(data)
        blkdev = bdf.open("bluna" + a, fobj=nobj)
        print(a, blkdev.__class__.__name__)
        blkdev.close()
