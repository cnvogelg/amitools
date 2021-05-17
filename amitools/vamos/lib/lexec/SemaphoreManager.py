from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import SignalSemaphoreStruct
from amitools.vamos.error import *


class SemaphoreManager:

    NT_SIGNALSEM = 15

    def __init__(self, alloc, mem):
        self.alloc = alloc
        self.mem = mem
        self.semaphores = {}
        self.semaphores_by_name = {}

    def InitSemaphore(self, addr):
        semaphore = AccessStruct(self.mem, SignalSemaphoreStruct, struct_addr=addr)
        semaphore.w_s("ss_Owner", 0)
        semaphore.w_s("ss_NestCount", 0)
        semaphore.w_s("ss_QueueCount", -1)
        semaphore.w_s("ss_Link.ln_Type", self.NT_SIGNALSEM)
        semaphore.w_s(
            "ss_WaitQueue.mlh_Head", semaphore.s_get_addr("ss_WaitQueue.mlh_Tail")
        )
        semaphore.w_s("ss_WaitQueue.mlh_Tail", 0)
        semaphore.w_s(
            "ss_WaitQueue.mlh_TailPred", semaphore.s_get_addr("ss_WaitQueue.mlh_Head")
        )
        return self.register_semaphore(addr)

    def AddSemaphore(self, addr, name):
        semaphore = self.InitSemaphore(addr)
        semaphore.name = name
        self.semaphores_by_name[name] = semaphore
        return semaphore

    def RemSemaphore(self, addr):
        if self.has_semaphore(addr):
            semaphore = self.semaphores[addr]
            del self.semaphores_by_name[semaphore.name]

    def FindSemaphore(self, name):
        if name in self.semaphores_by_name:
            semaphore = self.semaphores_by_name[name]
            return semaphore
        else:
            return None

    def has_semaphore(self, addr):
        return addr in self.semaphores

    def register_semaphore(self, addr):
        if not self.has_semaphore(addr):
            name = "Semaphore@%06x" % addr
            semaphore = Semaphore(name, self, addr=addr)
            self.semaphores[addr] = semaphore
            return semaphore
        else:
            return self.semaphores[addr]

    def unregister_semaphore(self, addr):
        if addr in self.semaphores:
            semaphore = self.semaphores[addr]
            del self.semaphores_by_name[semaphore.name]
            del self.semaphores[addr]
        else:
            raise VamosInternalError("Invalid Semaphore remove: %06x" % addr)


class Semaphore:
    def __init__(self, name, semaphore_mgr, addr=None, mem=None):
        self.name = name
        self.semaphore_mgr = semaphore_mgr
        if mem is None:
            self.addr = addr
        else:
            self.addr = mem.addr
        self.mem = mem

    def __str__(self):
        return "<Semaphore:name=%s,addr=%06x>" % (self.name, self.addr)
