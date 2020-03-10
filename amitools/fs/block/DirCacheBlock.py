import time
import struct

from .Block import Block
from ..ProtectFlags import ProtectFlags
from ..TimeStamp import TimeStamp
from ..FSString import FSString


class DirCacheRecord:
    def __init__(
        self, entry=0, size=0, protect=0, mod_ts=None, sub_type=0, name="", comment=None
    ):
        self.entry = entry
        self.size = size
        self.protect = protect
        self.mod_ts = mod_ts
        self.sub_type = sub_type
        self.name = name
        if comment is None:
            self.comment = FSString()
        else:
            self.comment = comment
        self.offset = None

    def get_size(self):
        total_len = 25 + len(self.name.get_ami_str()) + len(self.comment.get_ami_str())
        align_len = (total_len + 1) & ~1
        return align_len

    def get(self, data, off):
        self.offset = off
        # header
        d = struct.unpack_from(">IIIHHHHH", data, offset=off)
        self.entry = d[0]
        self.size = d[1]
        self.protect = d[2]
        self.mod_ts = TimeStamp(d[5], d[6], d[7])
        self.type = ord(data[off + 22])
        # name
        name_len = ord(data[off + 23])
        name_off = off + 24
        self.name = FSString(data[name_off : name_off + name_len])
        # comment
        comment_len = ord(data[off + name_len + 24])
        comment_off = off + 25 + name_len
        self.comment = FSString(data[comment_off : comment_off + comment_len])
        return off + self.get_size()

    def put(self, data, off):
        self.offset = off
        # header
        ts = self.mod_ts
        struct.pack_into(
            ">IIIHHHHH",
            data,
            off,
            self.entry,
            self.size,
            self.protect,
            0,
            0,
            ts.days,
            ts.mins,
            ts.ticks,
        )
        # name
        name = self.name.get_ami_str()
        name_len = len(name)
        data[off + 23] = name_len
        name_off = off + 24
        data[name_off : name_off + name_len] = name
        # comment
        comment = self.comment.get_ami_str()
        comment_len = len(comment)
        data[off + 24 + name_len] = comment_len
        comment_off = off + 25 + name_len
        data[comment_off : comment_off + comment_len] = comment
        return off + self.get_size()

    def dump(self):
        print("DirCacheRecord(%s)(size=%d)" % (self.offset, self.get_size()))
        print("\tentry:      %s" % self.entry)
        print("\tsize:       %s" % self.size)
        pf = ProtectFlags(self.protect)
        print("\tprotect:    0x%x 0b%s %s" % (self.protect, pf.bin_str(), pf))
        print("\tmod_ts:     %s" % self.mod_ts)
        print("\tsub_type:   0x%x" % self.sub_type)
        print("\tname:       %s" % self.name)
        print("\tcomment:    %s" % self.comment)


class DirCacheBlock(Block):
    def __init__(self, blkdev, blk_num):
        Block.__init__(self, blkdev, blk_num, is_type=Block.T_DIR_CACHE)

    def set(self, data):
        self._set_data(data)
        self._read()

    def read(self):
        self._read_data()
        self._read()

    def _read(self):
        Block.read(self)
        if not self.valid:
            return False

        # fields
        self.own_key = self._get_long(1)
        self.parent = self._get_long(2)
        self.num_records = self._get_long(3)
        self.next_cache = self._get_long(4)
        self.records = []

        # get records
        off = 24
        for i in range(self.num_records):
            r = DirCacheRecord()
            off = r.get(self.data, off)
            if off == -1:
                return False
            self.records.append(r)

        self.valid = True
        return True

    def get_total_record_size(self):
        size = 0
        for r in self.records:
            size += r.get_size()
        return size

    def get_free_record_size(self):
        return self.blkdev.block_bytes - 24 - self.get_total_record_size()

    def create(self, parent, records=None, next_cache=0):
        Block.create(self)
        self.own_key = self.blk_num
        self.parent = parent
        self.next_cache = next_cache
        if records == None:
            self.num_records = 0
            self.records = []
        else:
            self.num_records = len(records)
            self.records = records
        self.valid = True
        return True

    def add_record(self, record):
        self.records.append(record)
        self.num_records = len(self.records)

    def get_record_by_name(self, name):
        for r in self.records:
            if r.name == name:
                return r
        return None

    def remove_record(self, record):
        self.records.remove(record)
        self.num_records = len(self.records)

    def has_record(self, record):
        return record in self.records

    def is_empty(self):
        return self.num_records == 0

    def write(self):
        Block._create_data(self)
        self._put_long(1, self.own_key)
        self._put_long(2, self.parent)
        self._put_long(3, self.num_records)
        self._put_long(4, self.next_cache)

        # put records
        off = 24
        for r in self.records:
            off = r.put(self.data, off)

        Block.write(self)

    def dump(self):
        Block.dump(self, "DirCache")
        print(" own_key:    %d" % (self.own_key))
        print(" parent:     %d" % (self.parent))
        print(" num_records:%d" % (self.num_records))
        print(" next_cache: %d" % (self.next_cache))
        print(" num records:%d" % len(self.records))
        for r in self.records:
            r.dump()
