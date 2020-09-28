from .MetaInfo import MetaInfo
from .RootMetaInfo import RootMetaInfo
from .ProtectFlags import ProtectFlags
from .TimeStamp import TimeStamp
from amitools.fs.block.BootBlock import BootBlock
from . import DosType
from .FSString import FSString


class MetaDB:
    def __init__(self):
        self.metas = {}
        self.vol_name = None
        self.vol_meta = None
        self.dos_type = DosType.DOS0

    def set_root_meta_info(self, meta):
        self.vol_meta = meta

    def get_root_meta_info(self):
        return self.vol_meta

    def set_volume_name(self, name):
        if type(name) != str:
            raise ValueError("set_volume_name must be unicode")
        self.vol_name = name

    def get_volume_name(self):
        return self.vol_name

    def set_dos_type(self, dos_type):
        self.dos_type = dos_type

    def get_dos_type(self):
        return self.dos_type

    def set_meta_info(self, path, meta_info):
        if type(path) != str:
            raise ValueError("set_meta_info: path must be unicode")
        self.metas[path] = meta_info

    def get_meta_info(self, path):
        if path in self.metas:
            return self.metas[path]
        else:
            return None

    def dump(self):
        print(self.vol_name, self.vol_meta, self.dos_type)
        for m in self.metas:
            print(m)

    # ----- load -----

    def load(self, file_path):
        self.metas = {}
        f = open(file_path, "r")
        first = True
        for line in f:
            if first:
                self.load_header(line)
                first = False
            else:
                self.load_entry(line)
        f.close()

    def load_header(self, line):
        pos = line.find(":")
        if pos == -1:
            raise IOError("Invalid xdfmeta header! (no colon in line)")
        # first extract volume name
        vol_name = line[:pos]
        self.vol_name = vol_name
        line = line[pos + 1 :]
        # now get parameters
        comp = line.split(",")
        if len(comp) != 4:
            raise IOError("Invalid xdfmeta header! (wrong number of parameters found)")
        # first dos type
        dos_type_str = comp[0]
        if len(dos_type_str) != 4:
            raise IOError("Invalid xdfmeta dostype string")
        num = ord(dos_type_str[3]) - ord("0")
        if num < 0 or num > 7:
            raise IOError("Invalid xdfmeta dostype number")
        self.dos_type = DosType.DOS0 + num
        # then time stamps
        create_ts = TimeStamp()
        ok1 = create_ts.parse(comp[1])
        disk_ts = TimeStamp()
        ok2 = disk_ts.parse(comp[2])
        mod_ts = TimeStamp()
        ok3 = mod_ts.parse(comp[3])
        if not ok1 or not ok2 or not ok3:
            raise IOError("Invalid xdfmeta header! (invalid timestamp found)")
        self.vol_meta = RootMetaInfo(create_ts, disk_ts, mod_ts)

    def load_entry(self, line):
        line = line.strip()
        # path
        pos = line.find(":")
        if pos == -1:
            raise IOError("Invalid xdfmeta file! (no colon in line)")
        path = line[:pos]
        # prot
        line = line[pos + 1 :]
        pos = line.find(",")
        if pos == -1:
            raise IOError("Invalid xdfmeta file! (no first comma)")
        prot_str = line[:pos]
        prot = ProtectFlags()
        prot.parse(prot_str)
        # time
        line = line[pos + 1 :]
        pos = line.find(",")
        if pos == -1:
            raise IOError("Invalid xdfmeta file! (no second comma)")
        time_str = line[:pos]
        time = TimeStamp()
        time.parse(time_str)
        # comment
        comment = FSString(line[pos + 1 :])
        # meta info
        mi = MetaInfo(protect_flags=prot, mod_ts=time, comment=comment)
        self.set_meta_info(path, mi)

    # ----- save -----

    def save(self, file_path):
        f = open(file_path, "w")
        # header
        mi = self.vol_meta
        num = self.dos_type - DosType.DOS0 + ord("0")
        dos_type_str = "DOS%c" % num
        vol_name = self.vol_name
        line = "%s:%s,%s,%s,%s\n" % (
            vol_name,
            dos_type_str,
            mi.get_create_ts(),
            mi.get_disk_ts(),
            mi.get_mod_ts(),
        )
        f.write(line)
        # entries
        for path in sorted(self.metas):
            meta_info = self.metas[path]
            protect = meta_info.get_protect_short_str()
            mod_time = meta_info.get_mod_time_str()
            comment = meta_info.get_comment_unicode_str()
            path_name = path
            line = "%s:%s,%s,%s\n" % (path_name, protect, mod_time, comment)
            f.write(line)
        f.close()
