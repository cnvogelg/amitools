from amitools.vamos.log import log_exec
from amitools.vamos.error import *
from .Puddle import Puddle


class Pool:
    def __init__(self, mem, alloc, flags, size, thresh, poolid):
        self.alloc = alloc
        self.mem = mem
        self.minsize = size
        self.flags = flags
        self.thresh = thresh
        self.name = " in Pool %x" % poolid
        self.puddles = []

    def __del__(self):
        while len(self.puddles) > 0:
            puddle = self.puddles.pop()
            puddle.__del__()

    def __str__(self):
        poolstr = ""
        for puddle in self.puddles:
            if poolstr == "":
                poolstr = "{%s}" % puddle
            else:
                poolstr = "%s,{%s}" % (poolstr, puddle)
        return poolstr

    def AllocPooled(self, label_mgr, name, size):
        result = None
        if size >= self.thresh:
            puddle = Puddle(self.mem, self.alloc, label_mgr, name, size)
            if puddle != None:
                self.puddles.append(puddle)
                result = puddle.AllocPooled(name + self.name, size)
        else:
            for puddle in self.puddles:
                result = puddle.AllocPooled(name + self.name, size)
                if result != None:
                    break
                # none of the puddles had enough memory
            if result == None:
                puddle = Puddle(self.mem, self.alloc, label_mgr, name, self.minsize)
                if puddle != None:
                    self.puddles.append(puddle)
                    result = puddle.AllocPooled(name + self.name, size)
        if result == None:
            log_exec.info("AllocPooled: Unable to allocate memory (%x)", size)
        return result

    def FreePooled(self, mem, size):
        if mem != 0:
            for puddle in self.puddles:
                if puddle.contains(mem, size):
                    puddle.FreePooled(mem, size)
                    return
            raise VamosInternalError(
                "FreePooled: invalid memory, not in any puddle : ptr=%06x" % mem
            )
