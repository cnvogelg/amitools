from amitools.vamos.lib.lexec.semaphorefunc import SemaphoreMixin
from amitools.vamos.libstructs import (
    ListStruct,
    MessageStruct,
    NodeType,
    SignalSemaphoreStruct,
)
from amitools.vamos.libtypes import List, Message, Node
from lib_exec_helper import ExecHost, make_exec_lib


class Host(ExecHost, SemaphoreMixin):
    """record the obtain/release/reply calls the list/legacy LVOs make."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.obtained = []
        self.released = []
        self.replied = []

    def obtain_semaphore(self, addr):
        self.obtained.append(addr)

    def release_semaphore(self, addr):
        self.released.append(addr)

    def reply_msg(self, msg):
        self.replied.append(msg.addr)


def _host_with_list():
    mem, alloc, el = make_exec_lib()
    host = Host(mem, alloc, el)
    lst_struct = alloc.alloc_astruct(ListStruct, label="semlist")
    lst = List(mem, lst_struct.addr)
    lst.new(NodeType.NT_SIGNALSEM)
    sems = []
    for _ in range(2):
        sem = alloc.alloc_astruct(SignalSemaphoreStruct, label="sem")
        sems.append(sem.addr)
        lst.add_tail(Node(mem, sem.addr))
    return host, lst, sems


def exec_semaphore_list_test():
    host, lst, sems = _host_with_list()
    host.ObtainSemaphoreList(host.ctx, lst)
    assert host.obtained == sems
    host.ReleaseSemaphoreList(host.ctx, lst)
    assert host.released == sems


def exec_attempt_semaphore_shared_test():
    host, lst, sems = _host_with_list()
    # no contention: a shared attempt always wins
    assert host.AttemptSemaphoreShared(host.ctx, Node(host.mem, sems[0])) == 1


def exec_procure_vacate_test():
    host, lst, sems = _host_with_list()
    sem = Node(host.mem, sems[0])
    msg_struct = host.alloc.alloc_astruct(MessageStruct, label="bid")
    msg = Message(host.mem, msg_struct.addr)
    host.Procure(host.ctx, sem, msg)
    assert host.obtained == [sem.addr]
    assert host.replied == [msg.addr]
    host.Vacate(host.ctx, sem, msg)
    assert host.released == [sem.addr]
    assert host.replied == [msg.addr, msg.addr]
