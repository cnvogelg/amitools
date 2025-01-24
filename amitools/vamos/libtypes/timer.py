from amitools.vamos.astructs import AmigaClassDef
from amitools.vamos.libstructs import TimeValStruct


@AmigaClassDef
class TimeVal(TimeValStruct):
    def new_time_val(self, secs, micro):
        self.secs.val = secs
        self.micro.val = micro

    def set_time_val(self, secs, micro):
        self.secs.val = secs
        self.micro.val = micro

    def get_time_val(self):
        return (self.secs.val, self.micro.val)
