import pytest
from amitools.vamos.libtypes import List, Node
from amitools.vamos.libstructs import NodeType


def pytask_exec_list_alloc_free_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # alloc new list
        list = List.alloc(ctx.alloc)
        list.new(NodeType.NT_MESSAGE)

        assert list.is_empty()

        # free list
        list.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


class ListHelper:
    def __init__(self, alloc):
        self.list = List.alloc(alloc)
        self.list.new(NodeType.NT_MESSAGE)
        assert self.list.is_empty()

        self.node1 = Node.alloc(alloc)
        self.node1.name.alloc_str(alloc, "node1")
        self.node1.pri.val = 10
        self.node2 = Node.alloc(alloc)
        self.node2.name.alloc_str(alloc, "node2")
        self.node2.pri.val = 1

    def free(self):
        self.node1.name.free_str()
        self.node1.free()
        self.node2.name.free_str()
        self.node2.free()
        self.list.free()


def pytask_exec_list_add_rem_head_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        h = ListHelper(ctx.alloc)

        # add head
        exec_lib.AddHead(h.list, h.node1)
        assert h.list.to_list() == [h.node1]

        # rem head
        node = exec_lib.RemHead(h.list)
        assert node == h.node1

        # free list
        h.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_list_add_rem_tail_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        h = ListHelper(ctx.alloc)

        # add tail
        exec_lib.AddTail(h.list, h.node1)
        assert h.list.to_list() == [h.node1]

        # rem tail
        node = exec_lib.RemTail(h.list)
        assert node == h.node1

        # free list
        h.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_list_find_name_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        h = ListHelper(ctx.alloc)

        # find name
        node = exec_lib.FindName(h.list, "node1")
        assert node is None

        # add tail
        exec_lib.AddTail(h.list, h.node1)
        assert h.list.to_list() == [h.node1]

        # find name
        node = exec_lib.FindName(h.list, "node1")
        assert node == h.node1

        # free list
        h.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_list_insert_remove_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        h = ListHelper(ctx.alloc)

        # add tail
        exec_lib.AddTail(h.list, h.node1)
        assert h.list.to_list() == [h.node1]

        # insert
        exec_lib.Insert(h.list, h.node2, h.node1)
        assert h.list.to_list() == [h.node1, h.node2]

        # remove
        exec_lib.Remove(h.node2)
        assert h.list.to_list() == [h.node1]
        exec_lib.Remove(h.node1)
        assert h.list.to_list() == []

        # free list
        h.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_list_enqueue_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        h = ListHelper(ctx.alloc)

        # add tail
        exec_lib.AddTail(h.list, h.node1)
        exec_lib.AddTail(h.list, h.node2)
        assert h.list.to_list() == [h.node1, h.node2]

        n = Node.alloc(ctx.alloc)
        n.pri.val = 5

        # enqueue
        exec_lib.Enqueue(h.list, n)
        assert h.list.to_list() == [h.node1, n, h.node2]

        n.free()

        # free list
        h.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
