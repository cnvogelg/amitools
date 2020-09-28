import time
from .TimeStamp import *


class RootMetaInfo:
    def __init__(self, create_ts=None, disk_ts=None, mod_ts=None):
        self.set_create_ts(create_ts)
        self.set_disk_ts(disk_ts)
        self.set_mod_ts(mod_ts)

    def __str__(self):
        res = []
        res.append(self.get_create_time_str())
        res.append(self.get_disk_time_str())
        res.append(self.get_mod_time_str())
        return "  ".join(res)

    # create_ts
    def set_create_time(self, create_time):
        self.create_time = create_time
        if self.create_time != None:
            self.create_ts = TimeStamp()
            self.create_ts.from_secs(create_time)
        else:
            self.create_ts = None

    def set_create_ts(self, create_ts):
        self.create_ts = create_ts
        if self.create_ts != None:
            self.create_time = self.create_ts.get_secsf()
        else:
            self.create_time = None

    def get_create_time(self):
        return self.create_time

    def get_create_ts(self):
        return self.create_ts

    def get_create_time_str(self):
        if self.create_ts != None:
            return str(self.create_ts)
        else:
            return ts_empty_string

    def set_current_as_create_time(self):
        create_time = time.mktime(time.localtime())
        self.set_create_time(create_time)

    # disk_ts
    def set_disk_time(self, disk_time):
        self.disk_time = disk_time
        if self.disk_time != None:
            self.disk_ts = TimeStamp()
            self.disk_ts.from_secs(disk_time)
        else:
            self.disk_ts = None

    def set_disk_ts(self, disk_ts):
        self.disk_ts = disk_ts
        if self.disk_ts != None:
            self.disk_time = self.disk_ts.get_secsf()
        else:
            self.disk_time = None

    def get_disk_time(self):
        return self.disk_time

    def get_disk_ts(self):
        return self.disk_ts

    def get_disk_time_str(self):
        if self.disk_ts != None:
            return str(self.disk_ts)
        else:
            return ts_empty_string

    def set_current_as_disk_time(self):
        disk_time = time.mktime(time.localtime())
        self.set_disk_time(disk_time)

    # mod_ts
    def set_mod_time(self, mod_time):
        self.mod_time = mod_time
        if self.mod_time != None:
            self.mod_ts = TimeStamp()
            self.mod_ts.from_secs(mod_time)
        else:
            self.mod_ts = None

    def set_mod_ts(self, mod_ts):
        self.mod_ts = mod_ts
        if self.mod_ts != None:
            self.mod_time = self.mod_ts.get_secsf()
        else:
            self.mod_time = None

    def get_mod_time(self):
        return self.mod_time

    def get_mod_ts(self):
        return self.mod_ts

    def get_mod_time_str(self):
        if self.mod_ts != None:
            return str(self.mod_ts)
        else:
            return ts_empty_string

    def set_current_as_mod_time(self):
        mod_time = time.mktime(time.localtime())
        self.set_mod_time(mod_time)
