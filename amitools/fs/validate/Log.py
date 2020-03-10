class LogEntry:
    """A class for a log entry"""

    names = ("debug", "info ", "WARN ", "ERROR")

    def __init__(self, level, msg, blk_num=-1):
        self.blk_num = blk_num
        self.level = level
        self.msg = msg

    def __str__(self):
        if self.blk_num == -1:
            return "%s%s:%s" % (" " * 8, self.names[self.level], self.msg)
        else:
            return "@%06d:%s:%s" % (self.blk_num, self.names[self.level], self.msg)


class Log:
    """Store a log of entries"""

    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3

    def __init__(self, min_level):
        self.entries = []
        self.min_level = min_level

    def msg(self, level, msg, blk_num=-1):
        if level < self.min_level:
            return
        e = LogEntry(level, msg, blk_num)
        self.entries.append(e)

    def dump(self):
        for e in self.entries:
            print(e)

    def get_num_level(self, level):
        num = 0
        for e in self.entries:
            if e.level == level:
                num += 1
        return num
