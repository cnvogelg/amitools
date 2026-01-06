from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libtypes import List, MinList, Node, MinNode, Task, Process
from amitools.vamos.libstructs import ListStruct, MinListStruct, NodeType


def new_list():
    mem = MockMemory()
    l = List(mem, 0x40)
    l.new(NodeType.NT_DEVICE)
    return l


def new_min_list():
    mem = MockMemory()
    l = MinList(mem, 0x40)
    l.new()
    return l


def libtypes_list_new_test():
    l = new_list()
    assert str(l) == "[List:@000040,h=000044,t=000000,tp=000040,NT_DEVICE(00000003/3)]"
    assert len(l) == 0
    assert [a for a in l] == []
    assert l.get_head() is None
    assert l.get_tail() is None
    assert l.rem_head() is None
    assert l.rem_tail() is None


def libtypes_list_min_new_test():
    l = new_min_list()
    assert str(l) == "[MinList:@000040,h=000044,t=000000,tp=000040]"
    assert len(l) == 0
    assert [a for a in l] == []
    assert l.get_head() is None
    assert l.get_tail() is None
    assert l.rem_head() is None
    assert l.rem_tail() is None


def libtypes_list_add_head_test():
    l = new_list()
    n1 = Node(l.mem, 0x50)
    assert len(l) == 0
    l.add_head(n1)
    assert l.get_head() == n1
    assert l.get_tail() == n1
    assert len(l) == 1
    assert [a for a in l] == [n1]
    n2 = Node(l.mem, 0x60)
    l.add_head(n2)
    assert l.get_head() == n2
    assert l.get_tail() == n1
    assert len(l) == 2
    assert [a for a in l] == [n2, n1]


def libtypes_list_add_tail_test():
    l = new_list()
    n1 = Node(l.mem, 0x50)
    assert len(l) == 0
    l.add_tail(n1)
    assert l.get_head() == n1
    assert l.get_tail() == n1
    assert len(l) == 1
    assert [a for a in l] == [n1]
    n2 = Node(l.mem, 0x60)
    l.add_tail(n2)
    assert l.get_head() == n1
    assert l.get_tail() == n2
    assert len(l) == 2
    assert [a for a in l] == [n1, n2]


def libtypes_list_rem_head_test():
    l = new_list()
    n1 = Node(l.mem, 0x50)
    l.add_tail(n1)
    n2 = Node(l.mem, 0x60)
    l.add_tail(n2)
    assert len(l) == 2
    assert [a for a in l] == [n1, n2]
    assert l.get_head() == n1
    r1 = l.rem_head()
    assert l.get_head() == n2
    assert r1 == n1
    assert len(l) == 1
    assert [a for a in l] == [n2]
    r2 = l.rem_head()
    assert r2 == n2
    assert len(l) == 0


def libtypes_list_rem_tail_test():
    l = new_list()
    n1 = Node(l.mem, 0x50)
    l.add_tail(n1)
    n2 = Node(l.mem, 0x60)
    l.add_tail(n2)
    assert len(l) == 2
    assert [a for a in l] == [n1, n2]
    assert l.get_tail() == n2
    r1 = l.rem_tail()
    assert l.get_tail() == n1
    assert r1 == n2
    assert len(l) == 1
    assert [a for a in l] == [n1]
    r2 = l.rem_tail()
    assert r2 == n1
    assert len(l) == 0


def libtypes_list_remove_node_test():
    l = new_list()
    n1 = Node(l.mem, 0x50)
    l.add_tail(n1)
    n2 = Node(l.mem, 0x60)
    l.add_tail(n2)
    assert len(l) == 2
    assert [a for a in l] == [n1, n2]
    n1.remove()
    assert len(l) == 1
    assert [a for a in l] == [n2]
    n2.remove()
    assert len(l) == 0


def libtypes_list_insert_node_test():
    l = new_list()
    n1 = Node(l.mem, 0x50)
    l.add_tail(n1)
    n2 = Node(l.mem, 0x60)
    l.add_tail(n2)
    assert len(l) == 2
    assert [a for a in l] == [n1, n2]
    # inside list
    n3 = Node(l.mem, 0x70)
    l.insert(n3, n1)
    assert len(l) == 3
    assert [a for a in l] == [n1, n3, n2]
    # tail
    n4 = Node(l.mem, 0x80)
    l.insert(n4, n2)
    assert len(l) == 4
    assert [a for a in l] == [n1, n3, n2, n4]
    # head
    n5 = Node(l.mem, 0x90)
    l.insert(n5, Node(l.mem, 0x40))
    assert len(l) == 5
    assert [a for a in l] == [n5, n1, n3, n2, n4]


def libtypes_list_enqueue_node_test():
    l = new_list()
    n1 = Node(l.mem, 0x50, pri=0)
    l.enqueue(n1)
    assert len(l) == 1
    assert [a for a in l] == [n1]
    # same pri
    n2 = Node(l.mem, 0x60, pri=0)
    l.enqueue(n2)
    assert len(l) == 2
    assert [a for a in l] == [n1, n2]
    # higher pri
    n3 = Node(l.mem, 0x70, pri=1)
    l.enqueue(n3)
    assert len(l) == 3
    assert [a for a in l] == [n3, n1, n2]
    # lower pri
    n4 = Node(l.mem, 0x80, pri=-1)
    l.enqueue(n4)
    assert len(l) == 4
    assert [a for a in l] == [n3, n1, n2, n4]


def libtypes_list_iter_at_test():
    l = new_list()
    n1 = Node(l.mem, 0x50)
    l.add_tail(n1)
    n2 = Node(l.mem, 0x60)
    l.add_tail(n2)
    assert len(l) == 2
    assert [a for a in l] == [n1, n2]
    assert [a for a in l.iter_at(n1)] == [n1, n2]
    assert [a for a in l.iter_at(n2)] == [n2]


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
    l = new_list()
    addr = 0x60
    n1, addr = add_node(l, addr, "hello")
    n2, addr = add_node(l, addr, "world")
    n3, addr = add_node(l, addr, "hello")
    assert n1.name.str == "hello"
    assert n2.name.str == "world"
    assert n3.name.str == "hello"
    assert len(l) == 3
    assert [a for a in l] == [n1, n2, n3]
    assert [a for a in l.find_names("bla")] == []
    assert [a for a in l.find_names("hello")] == [n1, n3]
    assert [a for a in l.find_names("world")] == [n2]
    # work like in exec: get first match and continue there
    n = l.find_name("hello")
    assert n == n1
    assert n.find_name("hello") == n3
    # get path
    assert l.get_path("") is l
    assert l.get_path("[world]") == n2
    assert l.get_path("[world].type") == n2.get("type")


def libtypes_list_find_name_promote_test():
    l = new_list()
    addr = 0x60
    n1, addr = add_node(l, addr, "hello", type=NodeType.NT_TASK)
    n2, addr = add_node(l, addr, "world", type=NodeType.NT_PROCESS)
    task = l.find_name("hello", promote=True)
    assert type(task) is Task
    proc = l.find_name("world", promote=True)
    assert type(proc) is Process
    task = l.get_head(promote=True)
    assert type(task) is Task
    proc = l.get_tail(promote=True)
    assert type(proc) is Process


def libtypes_list_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    l = List.alloc(alloc)
    assert type(l) is List
    assert l.get_size() == ListStruct.get_size()
    l.free()


def libtypes_list_alloc_min_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    l = MinList.alloc(alloc)
    assert type(l) is MinList
    assert l.get_size() == MinListStruct.get_size()
    l.free()
    assert alloc.is_all_free()
