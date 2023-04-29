from amitools.util import SlotArray


def util_slotarray_slot_getset_test():
    s = SlotArray(3)
    assert len(s) == 3
    assert s.num_free() == 3
    # alloc and set value
    id1 = s.alloc("bla")
    assert len(s) == 3
    assert s.num_free() == 2
    assert s[id1] == "bla"
    # change value
    s[id1] = "foo"
    assert s[id1] == "foo"


def util_slotarray_alloc_ordered_test():
    s = SlotArray(3)
    # alloc all 3 slots
    id1 = s.alloc("foo")
    assert id1 is not None
    id2 = s.alloc("bar")
    assert id2 is not None
    id3 = s.alloc("baz")
    assert id3 is not None
    # no more alloc possible
    assert not s.alloc("bau")
    assert s.num_free() == 0
    assert s[id1] == "foo"
    assert s[id2] == "bar"
    assert s[id3] == "baz"
    # free all slots
    s.free(id3)
    s.free(id2)
    s.free(id1)
    assert s.num_free() == 3
    # alloc again
    id1 = s.alloc("hello")
    assert id1 is not None
    assert s[id1] == "hello"
    s.free(id1)
    assert s.num_free() == 3


def util_slotarray_alloc_unordered_test():
    s = SlotArray(3)
    # alloc all 3 slots
    id1 = s.alloc("foo")
    id2 = s.alloc("bar")
    id3 = s.alloc("baz")
    # free all slots
    s.free(id1)
    s.free(id2)
    s.free(id3)
    assert s.num_free() == 3


def util_slotarray_alloc_unordered2_test():
    s = SlotArray(3)
    # alloc all 3 slots
    id1 = s.alloc("foo")
    id2 = s.alloc("bar")
    id3 = s.alloc("baz")
    # free all slots
    s.free(id2)
    s.free(id3)
    assert s.num_free() == 2
    id4 = s.alloc("hello")
    assert id4 is not None
    s.free(id1)
    s.free(id4)
    assert s.num_free() == 3
