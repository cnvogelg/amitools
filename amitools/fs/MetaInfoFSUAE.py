from __future__ import absolute_import

import time

from .ProtectFlags import ProtectFlags
from .TimeStamp import TimeStamp
from .MetaInfo import MetaInfo
from .FSString import FSString

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


class MetaInfoFSUAE:
    @staticmethod
    def is_meta_file(path):
        return path.lower().endswith(".uaem")

    @staticmethod
    def get_suffix():
        return ".uaem"

    def load_meta(self, path):
        with open(path, "rb") as fh:
            data = fh.read().decode("utf-8")
            return self.parse_data(data)

    def parse_data(self, data):
        if data.endswith("\n"):
            data = data[:-1]
        # first protect flags
        if len(data) > 8:
            protect = data[0:8]
            flags = ProtectFlags()
            flags.parse_full(protect)
            data = data[9:]
        else:
            raise ValueError("no protect flags in .uaem file!")
        # time stamp (unix) with ticks
        # 2019-02-22 22:36:14.24
        # 0123456789012345678901
        if len(data) >= 22:
            time_stamp = data[0:19]
            ticks = int(data[20:22])
            data = data[23:]
            ts = time.strptime(time_stamp, TS_FORMAT)
            secs = int(time.mktime(ts))
            mod_ts = TimeStamp()
            mod_ts.from_secs(secs, ticks)
        else:
            raise ValueError("no timestamp in .uaem file!")
        # comment
        if len(data) > 0:
            comment = FSString(data)
        else:
            comment = None
        # create meta info
        return MetaInfo(flags.get_mask(), mod_ts, comment)

    def generate_data(self, meta_info):
        protect = meta_info.get_protect_str()
        time_stamp = meta_info.get_mod_ts()
        ts = time_stamp.format(TS_FORMAT)
        ts += ".%02d" % time_stamp.get_sub_secs()
        comment = meta_info.get_comment_unicode_str()
        return "%s %s %s\n" % (protect, ts, comment)

    def save_meta(self, path, meta_info):
        with open(path, "wb") as fh:
            txt = self.generate_data(meta_info)
            fh.write(txt.encode("utf-8"))
