import struct
import ctypes
from ..TimeStamp import TimeStamp
from ..FSString import FSString


class Block:
    # mark end of block list
    no_blk = 0xFFFFFFFF

    # special blocks
    RDSK = 0x5244534B  # Rigid Disk Block
    BADB = 0x42414442  # Bad Blocks Block
    PART = 0x50415254  # Partition Block
    FSHD = 0x46534844  # FileSystem Header Block
    LSEG = 0x4C534547  # LoadSeg Block

    # block types
    T_SHORT = 2
    T_DATA = 8
    T_LIST = 16
    T_DIR_CACHE = 33
    T_COMMENT = 64
    # block sub types
    ST_ROOT = 1
    ST_USERDIR = 2
    ST_FILE = -3 & 0xFFFFFFFF

    def __init__(self, blkdev, blk_num, is_type=0, is_sub_type=0, chk_loc=5):
        self.valid = False
        self.blkdev = blkdev
        self.blk_num = blk_num
        self.block_longs = blkdev.block_longs
        self.type = 0
        self.sub_type = 0
        self.data = None
        self.is_type = is_type
        self.is_sub_type = is_sub_type
        self.chk_loc = chk_loc

    def __str__(self):
        return "%s:@%d" % (self.__class__.__name__, self.blk_num)

    def create(self):
        self.type = self.is_type
        self.sub_type = self.is_sub_type

    def is_root_block(self):
        return self.type == Block.T_SHORT and self.sub_type == Block.ST_ROOT

    def is_user_dir_block(self):
        return self.type == Block.T_SHORT and self.sub_type == Block.ST_USERDIR

    def is_file_header_block(self):
        return self.type == Block.T_SHORT and self.sub_type == Block.ST_FILE

    def is_file_list_block(self):
        return self.type == Block.T_LIST and self.sub_type == Block.ST_FILE

    def is_file_data_block(self):
        return self.type == Block.T_DATA

    def is_comment_block(self):
        return self.type == Block.T_COMMENT

    def read(self):
        if self.data == None:
            self._read_data()
        self._get_types()
        self._get_chksum()
        self.valid = self.valid_types and self.valid_chksum

    def write(self):
        if self.data == None:
            self._create_data()
        self._put_types()
        self._put_chksum()
        self._write_data()

    def _set_data(self, data):
        self.data = data

    def _read_data(self):
        data = self.blkdev.read_block(self.blk_num)
        if len(data) != self.blkdev.block_bytes:
            raise ValueError(
                "Invalid Block Data: size=%d but expected %d"
                % (len(data), self.blkdev.block_bytes)
            )
        self._create_data()
        self.data[:] = data

    def _write_data(self):
        if self.data != None:
            self.blkdev.write_block(self.blk_num, self.data)

    def _free_data(self):
        self.data = None

    def _create_data(self):
        num_bytes = self.blkdev.block_bytes
        self.data = ctypes.create_string_buffer(num_bytes)

    def _put_long(self, num, val):
        if num < 0:
            num = self.block_longs + num
        struct.pack_into(">I", self.data, num * 4, val)

    def _get_long(self, num):
        if num < 0:
            num = self.block_longs + num
        return struct.unpack_from(">I", self.data, num * 4)[0]

    def _put_slong(self, num, val):
        if num < 0:
            num = self.block_longs + num
        struct.pack_into(">i", self.data, num * 4, val)

    def _get_slong(self, num):
        if num < 0:
            num = self.block_longs + num
        return struct.unpack_from(">i", self.data, num * 4)[0]

    def _get_types(self):
        self.type = self._get_long(0)
        self.sub_type = self._get_long(-1)
        self.valid_types = True
        if self.is_type != 0:
            if self.type != self.is_type:
                self.valid_types = False
        if self.is_sub_type != 0:
            if self.sub_type != self.is_sub_type:
                self.valid_types = False

    def _put_types(self):
        if self.is_type != 0:
            self._put_long(0, self.is_type)
        if self.is_sub_type != 0:
            self._put_long(-1, self.is_sub_type)

    def _get_chksum(self):
        self.got_chksum = self._get_long(self.chk_loc)
        self.calc_chksum = self._calc_chksum()
        self.valid_chksum = self.got_chksum == self.calc_chksum

    def _put_chksum(self):
        self.calc_chksum = self._calc_chksum()
        self.got_chksum = self.calc_chksum
        self.valid_chksum = True
        self._put_long(self.chk_loc, self.calc_chksum)

    def _calc_chksum(self):
        chksum = 0
        for i in range(self.block_longs):
            if i != self.chk_loc:
                chksum += self._get_long(i)
        return (-chksum) & 0xFFFFFFFF

    def _get_timestamp(self, loc):
        days = self._get_long(loc)
        mins = self._get_long(loc + 1)
        ticks = self._get_long(loc + 2)
        return TimeStamp(days, mins, ticks)

    def _put_timestamp(self, loc, ts):
        if ts == None:
            ts = TimeStamp()
        self._put_long(loc, ts.days)
        self._put_long(loc + 1, ts.mins)
        self._put_long(loc + 2, ts.ticks)

    def _get_bytes(self, loc, size):
        if loc < 0:
            loc = self.block_longs + loc
        loc = loc * 4
        return self.data[loc : loc + size]

    def _put_bytes(self, loc, data):
        if loc < 0:
            loc = self.block_longs + loc
        loc = loc * 4
        size = len(data)
        self.data[loc : loc + size] = data

    def _get_bstr(self, loc, max_size):
        if loc < 0:
            loc = self.block_longs + loc
        loc = loc * 4
        size = ord(self.data[loc])
        if size > max_size:
            return None
        if size == 0:
            return FSString()
        name = self.data[loc + 1 : loc + 1 + size]
        return FSString(name)

    def _put_bstr(self, loc, max_size, fs_str):
        if fs_str is None:
            fs_str = FSString()
        assert isinstance(fs_str, FSString)
        bstr = fs_str.get_ami_str()
        assert len(bstr) < 256
        n = len(bstr)
        if n > max_size:
            bstr = bstr[:max_size]
        if loc < 0:
            loc = self.block_longs + loc
        loc = loc * 4
        self.data[loc] = len(bstr)
        if len(bstr) > 0:
            self.data[loc + 1 : loc + 1 + len(bstr)] = bstr

    def _get_cstr(self, loc, max_size):
        n = 0
        s = b""
        loc = loc * 4
        while n < max_size:
            c = self.data[loc + n]
            if ord(c) == 0:
                break
            s += c
            n += 1
        return FSString(s)

    def _put_cstr(self, loc, max_size, fs_str):
        if fs_str is None:
            fs_str = FSString()
        assert isinstance(fs_str, FSString)
        cstr = fs_str.get_ami_str()
        n = min(max_size, len(cstr))
        loc = loc * 4
        if n > 0:
            self.data[loc : loc + n] = cstr

    def _dump_ptr(self, ptr):
        if ptr == self.no_blk:
            return "none"
        else:
            return "%d" % ptr

    def dump(self, name, details=True):
        print("%sBlock(%d):" % (name, self.blk_num))
        if details:
            print(
                " types:     %x/%x (valid: %x/%x)"
                % (self.type, self.sub_type, self.is_type, self.is_sub_type)
            )
            print(
                " chksum:    0x%08x (got) 0x%08x (calc)"
                % (self.got_chksum, self.calc_chksum)
            )
            print(" valid:     %s" % self.valid)
