from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libtypes import List, MinList, Node, Task, Process
from amitools.vamos.libstructs import ListStruct, MinListStruct, NodeType


def new_list():
    mem = MockMemory()
    lst = List(mem, 0x40)
    lst.new(NodeType.NT_DEVICE)
    return lst


def new_min_list():
    mem = MockMemory()
    lst = MinList(mem, 0x40)
    lst.new()
    return lst


def new_uninit_list():
    # a zeroed list that was never initialized with new()
    mem = MockMemory()
    return List(mem, 0x40)


def libtypes_list_new_test():
    lst = new_list()
    assert (
        str(lst) == "[List:@000040,h=000044,t=000000,tp=000040,NT_DEVICE(00000003/3)]"
    )
    assert len(lst) == 0
    assert [a for a in lst] == []
    assert lst.get_head() is None
    assert lst.get_tail() is None
    assert lst.rem_head() is None
    assert lst.rem_tail() is None


def libtypes_list_min_new_test():
    lst = new_min_list()
    assert str(lst) == "[MinList:@000040,h=000044,t=000000,tp=000040]"
    assert len(lst) == 0
    assert [a for a in lst] == []
    assert lst.get_head() is None
    assert lst.get_tail() is None
    assert lst.rem_head() is None
    assert lst.rem_tail() is None


def libtypes_list_add_head_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50)
    assert len(lst) == 0
    lst.add_head(n1)
    assert lst.get_head() == n1
    assert lst.get_tail() == n1
    assert len(lst) == 1
    assert [a for a in lst] == [n1]
    n2 = Node(lst.mem, 0x60)
    lst.add_head(n2)
    assert lst.get_head() == n2
    assert lst.get_tail() == n1
    assert len(lst) == 2
    assert [a for a in lst] == [n2, n1]


def libtypes_list_add_tail_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50)
    assert len(lst) == 0
    lst.add_tail(n1)
    assert lst.get_head() == n1
    assert lst.get_tail() == n1
    assert len(lst) == 1
    assert [a for a in lst] == [n1]
    n2 = Node(lst.mem, 0x60)
    lst.add_tail(n2)
    assert lst.get_head() == n1
    assert lst.get_tail() == n2
    assert len(lst) == 2
    assert [a for a in lst] == [n1, n2]


def libtypes_list_rem_head_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50)
    lst.add_tail(n1)
    n2 = Node(lst.mem, 0x60)
    lst.add_tail(n2)
    assert len(lst) == 2
    assert [a for a in lst] == [n1, n2]
    assert lst.get_head() == n1
    r1 = lst.rem_head()
    assert lst.get_head() == n2
    assert r1 == n1
    assert len(lst) == 1
    assert [a for a in lst] == [n2]
    r2 = lst.rem_head()
    assert r2 == n2
    assert len(lst) == 0


def libtypes_list_rem_tail_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50)
    lst.add_tail(n1)
    n2 = Node(lst.mem, 0x60)
    lst.add_tail(n2)
    assert len(lst) == 2
    assert [a for a in lst] == [n1, n2]
    assert lst.get_tail() == n2
    r1 = lst.rem_tail()
    assert lst.get_tail() == n1
    assert r1 == n2
    assert len(lst) == 1
    assert [a for a in lst] == [n1]
    r2 = lst.rem_tail()
    assert r2 == n1
    assert len(lst) == 0


def libtypes_list_remove_node_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50)
    lst.add_tail(n1)
    n2 = Node(lst.mem, 0x60)
    lst.add_tail(n2)
    assert len(lst) == 2
    assert [a for a in lst] == [n1, n2]
    n1.remove()
    assert len(lst) == 1
    assert [a for a in lst] == [n2]
    n2.remove()
    assert len(lst) == 0


def libtypes_list_insert_node_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50)
    lst.add_tail(n1)
    n2 = Node(lst.mem, 0x60)
    lst.add_tail(n2)
    assert len(lst) == 2
    assert [a for a in lst] == [n1, n2]
    # inside list
    n3 = Node(lst.mem, 0x70)
    lst.insert(n3, n1)
    assert len(lst) == 3
    assert [a for a in lst] == [n1, n3, n2]
    # tail
    n4 = Node(lst.mem, 0x80)
    lst.insert(n4, n2)
    assert len(lst) == 4
    assert [a for a in lst] == [n1, n3, n2, n4]
    # head
    n5 = Node(lst.mem, 0x90)
    lst.insert(n5, Node(lst.mem, 0x40))
    assert len(lst) == 5
    assert [a for a in lst] == [n5, n1, n3, n2, n4]


def libtypes_list_enqueue_node_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50, pri=0)
    lst.enqueue(n1)
    assert len(lst) == 1
    assert [a for a in lst] == [n1]
    # same pri
    n2 = Node(lst.mem, 0x60, pri=0)
    lst.enqueue(n2)
    assert len(lst) == 2
    assert [a for a in lst] == [n1, n2]
    # higher pri
    n3 = Node(lst.mem, 0x70, pri=1)
    lst.enqueue(n3)
    assert len(lst) == 3
    assert [a for a in lst] == [n3, n1, n2]
    # lower pri
    n4 = Node(lst.mem, 0x80, pri=-1)
    lst.enqueue(n4)
    assert len(lst) == 4
    assert [a for a in lst] == [n3, n1, n2, n4]


def libtypes_list_iter_at_test():
    lst = new_list()
    n1 = Node(lst.mem, 0x50)
    lst.add_tail(n1)
    n2 = Node(lst.mem, 0x60)
    lst.add_tail(n2)
    assert len(lst) == 2
    assert [a for a in lst] == [n1, n2]
    assert [a for a in lst.iter_at(n1)] == [n1, n2]
    assert [a for a in lst.iter_at(n2)] == [n2]


def add_node(alist, addr, name, type=NodeType.NT_UNKNOWN):
    n = Node(alist.mem, addr)
    n.type.set(type)
    addr += n.get_size()
    name_addr = addr
    alist.mem.w_cstr(addr, name)
    addr += len(name) + 1
    if addr & 3 != 0:
        addr = (addr & ~0x3) + 4
    n.name.aptr = name_addr
    alist.add_tail(n)
    return n, addr


def libtypes_list_find_name_test():
    lst = new_list()
    addr = 0x60
    n1, addr = add_node(lst, addr, "hello")
    n2, addr = add_node(lst, addr, "world")
    n3, addr = add_node(lst, addr, "hello")
    assert n1.name.str == "hello"
    assert n2.name.str == "world"
    assert n3.name.str == "hello"
    assert len(lst) == 3
    assert [a for a in lst] == [n1, n2, n3]
    assert [a for a in lst.find_names("bla")] == []
    assert [a for a in lst.find_names("hello")] == [n1, n3]
    assert [a for a in lst.find_names("world")] == [n2]
    # work like in exec: get first match and continue there
    n = lst.find_name("hello")
    assert n == n1
    assert n.find_name("hello") == n3
    # get path
    assert lst.get_path("") is lst
    assert lst.get_path("[world]") == n2
    assert lst.get_path("[world].type") == n2.get("type")


def libtypes_list_find_name_promote_test():
    lst = new_list()
    addr = 0x60
    n1, addr = add_node(lst, addr, "hello", type=NodeType.NT_TASK)
    n2, addr = add_node(lst, addr, "world", type=NodeType.NT_PROCESS)
    task = lst.find_name("hello", promote=True)
    assert type(task) is Task
    proc = lst.find_name("world", promote=True)
    assert type(proc) is Process
    task = lst.get_head(promote=True)
    assert type(task) is Task
    proc = lst.get_tail(promote=True)
    assert type(proc) is Process


def libtypes_list_uninit_add_tail_test():
    # exec AddTail on a zeroed list writes through the NULL lh_TailPred
    # like real Amiga hardware: tp->ln_Succ = node -> mem[0] = node
    lst = new_uninit_list()
    n1 = Node(lst.mem, 0x50)
    lst.add_tail(n1)
    assert lst.mem.r32(0) == 0x50
    assert n1.pred.aptr == 0
    assert n1.succ.aptr == 0x44
    assert lst.tail_pred.aptr == 0x50
    # a real m68k traversal starts at lh_Head=NULL and follows ln_Succ
    # at addr 0, so it finds the node. Python iteration does the same.
    assert len(lst) == 1
    assert not lst.is_empty()
    assert [a for a in lst] == [n1]
    assert lst.find_name("bla") is None


def libtypes_list_uninit_add_head_test():
    # exec AddHead on a zeroed list writes through the NULL lh_Head
    # like real Amiga hardware: h->ln_Pred = node -> mem[4] = node
    lst = new_uninit_list()
    n1 = Node(lst.mem, 0x50)
    lst.add_head(n1)
    assert lst.mem.r32(4) == 0x50
    assert n1.succ.aptr == 0
    assert n1.pred.aptr == 0x40
    assert lst.head.aptr == 0x50
    # traversal reads ln_Succ at addr 0 which was never written
    assert len(lst) == 0
    assert lst.is_empty()
    assert [a for a in lst] == []


def libtypes_list_uninit_read_ops_test():
    lst = new_uninit_list()
    assert len(lst) == 0
    assert lst.is_empty()
    assert [a for a in lst] == []
    assert lst.get_head() is None
    assert lst.get_tail() is None
    assert lst.rem_head() is None
    assert lst.rem_tail() is None
    assert lst.find_name("bla") is None
    assert lst.to_list() == []


def libtypes_list_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lst = List.alloc(alloc)
    assert type(lst) is List
    assert lst.get_size() == ListStruct.get_size()
    lst.free()


def libtypes_list_alloc_min_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lst = MinList.alloc(alloc)
    assert type(lst) is MinList
    assert lst.get_size() == MinListStruct.get_size()
    lst.free()
    assert alloc.is_all_free()
