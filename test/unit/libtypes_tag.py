from enum import IntEnum
from amitools.vamos.libtypes import Tag, TagArray, TagItem, TagList, CommonTag
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


class MyTag(IntEnum):
    FOO_TAG = 1000
    BAR_TAG = 1001
    BAZ_TAG = 1002


def build_tag_list(*tag_list, base=0x10, mem=None):
    if not mem:
        mem = MockMemory()
    base = base
    addr = base
    for entry in tag_list:
        mem.w32(addr, entry)
        addr += 4
    return mem, base


def build_tag_array(*tag_array, base=0x10, mem=None):
    if not mem:
        mem = MockMemory()
    base = base
    addr = base
    for entry in tag_array:
        mem.w32(addr, entry)
        addr += 4
    return mem, base


# --- TAG_DONE ---


def libtypes_tag_done_test():
    mem, addr = build_tag_list(CommonTag.TAG_DONE, 0)
    # check end tag
    tag = TagItem(mem, addr)
    assert tag.tag.val == CommonTag.TAG_DONE
    assert tag.data.val == 0
    assert tag.get_tuple() == (CommonTag.TAG_DONE, 0)
    # no "real" tag
    assert tag.next_real_tag() is None
    assert tag.succ_tag() is None
    assert tag.succ_real_tag() is None


def libtypes_tag_list_done_test():
    mem, addr = build_tag_list(CommonTag.TAG_DONE, 0)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 0
    assert [a for a in tag_list] == []


# --- TAG_IGNORE ---


def libtypes_tag_ignore_test():
    """empty tag list with TAG_DONE only"""
    mem, addr = build_tag_list(CommonTag.TAG_IGNORE, 0, CommonTag.TAG_DONE, 0)
    # check tag
    tag = TagItem(mem, addr)
    assert tag.tag.val == CommonTag.TAG_IGNORE
    assert tag.data.val == 0
    assert tag.get_tuple() == (CommonTag.TAG_IGNORE, 0)
    # no "real" tag
    assert tag.next_real_tag() is None
    assert tag.succ_tag() == TagItem(mem, 0x18)
    assert tag.succ_real_tag() is None


def libtypes_tag_list_ignore_test():
    """empty tag list with TAG_DONE only"""
    mem, addr = build_tag_list(CommonTag.TAG_IGNORE, 0, CommonTag.TAG_DONE, 0)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 0
    assert [a for a in tag_list] == []

    mem, addr = build_tag_list(
        MyTag.FOO_TAG,
        12,
        CommonTag.TAG_IGNORE,
        0,
        MyTag.BAR_TAG,
        13,
        CommonTag.TAG_DONE,
        0,
    )
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 2
    assert [a for a in tag_list] == [TagItem(mem, 0x10), TagItem(mem, 0x20)]
    assert tag_list.to_list() == [(MyTag.FOO_TAG, 12), (MyTag.BAR_TAG, 13)]


# --- TAG_MORE ---


def libtypes_tag_more_test():
    mem, addr = build_tag_list(CommonTag.TAG_MORE, 0x40, CommonTag.TAG_DONE, 0)
    build_tag_list(CommonTag.TAG_DONE, 0, mem=mem, base=0x40)
    # check tag
    tag = TagItem(mem, addr)
    assert tag.tag.val == CommonTag.TAG_MORE
    assert tag.data.val == 0x40
    assert tag.get_tuple() == (CommonTag.TAG_MORE, 0x40)
    # no "real" tag
    assert tag.next_real_tag() is None
    assert tag.succ_tag() == TagItem(mem, 0x40)
    assert tag.succ_real_tag() is None


def libtypes_tag_list_more_test():
    mem, addr = build_tag_list(CommonTag.TAG_MORE, 0x40, CommonTag.TAG_DONE, 0)
    build_tag_list(CommonTag.TAG_DONE, 0, mem=mem, base=0x40)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 0
    assert [a for a in tag_list] == []

    mem, addr = build_tag_list(
        MyTag.FOO_TAG, 12, CommonTag.TAG_MORE, 0x40, CommonTag.TAG_DONE, 0
    )
    build_tag_list(MyTag.BAR_TAG, 13, CommonTag.TAG_DONE, 0, mem=mem, base=0x40)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 2
    assert [a for a in tag_list] == [TagItem(mem, 0x10), TagItem(mem, 0x40)]
    assert tag_list.to_list() == [(MyTag.FOO_TAG, 12), (MyTag.BAR_TAG, 13)]


# --- TAG_SKIP ---


def libtypes_tag_skip_test():
    mem, addr = build_tag_list(
        CommonTag.TAG_SKIP,
        2,
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
        MyTag.BAZ_TAG,
        14,
        CommonTag.TAG_DONE,
        0,
    )
    # check tag
    tag = TagItem(mem, addr)
    assert tag.tag.val == CommonTag.TAG_SKIP
    assert tag.data.val == 2
    assert tag.get_tuple() == (CommonTag.TAG_SKIP, 2)
    # no "real" tag
    assert tag.next_real_tag() == TagItem(mem, 0x28)
    assert tag.succ_tag() == TagItem(mem, 0x28)
    assert tag.succ_real_tag() == TagItem(mem, 0x28)


def libtypes_tag_skip_more_test():
    mem, addr = build_tag_list(
        CommonTag.TAG_SKIP,
        2,
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
        MyTag.BAZ_TAG,
        14,
        CommonTag.TAG_DONE,
        0,
    )
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 1
    assert [a for a in tag_list] == [TagItem(mem, 0x28)]
    assert tag_list.to_list() == [(MyTag.BAZ_TAG, 14)]


# --- alloc tag list ---


def libtypes_tag_list_alloc_empty_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # empty list
    tl = TagList.alloc(alloc)
    assert len(tl) == 0
    tl.free()
    assert alloc.is_all_free()


def libtypes_tag_list_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    tl = TagList.alloc(alloc, (MyTag.FOO_TAG, 1), (MyTag.BAR_TAG, 2))
    assert len(tl) == 2
    assert tl.to_list() == [(MyTag.FOO_TAG, 1), (MyTag.BAR_TAG, 2)]
    tl.free()
    assert alloc.is_all_free()


# --- tag ops ---


def libtypes_tag_get_set_test():
    mem = MockMemory()
    tag = Tag(mem=mem, addr=0x10)
    tag.set_tag(CommonTag.TAG_IGNORE)
    assert tag.get_tag() is CommonTag.TAG_IGNORE
    assert tag.get_tag(do_map=False) == CommonTag.TAG_IGNORE


# --- tag item ops ---


def libtypes_tag_item_get_set_test():
    mem, addr = build_tag_list(
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
    )
    tag = TagItem(mem, addr)
    assert tag.get_tag() == MyTag.FOO_TAG
    assert tag.get_tag(map_enum=MyTag) is MyTag.FOO_TAG
    assert tag.get_data() == 12
    tag.set_tag(MyTag.BAZ_TAG)
    assert tag.get_tag() == MyTag.BAZ_TAG
    tag.set_data(21)
    assert tag.get_data() == 21
    # test control tags
    tag.set_tag(CommonTag.TAG_IGNORE)
    assert tag.get_tag() is CommonTag.TAG_IGNORE
    assert tag.get_tag(do_map=False) == CommonTag.TAG_IGNORE


# --- tag list ops ---


def libtypes_tag_list_find_test():
    mem, addr = build_tag_list(
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
    )
    tl = TagList(mem, addr)
    tag = tl.find_tag(MyTag.BAZ_TAG)
    assert tag is None
    tag = tl.find_tag(MyTag.FOO_TAG)
    assert tag == TagItem(mem, addr)
    # find by tag
    tag = TagItem(mem, addr)
    assert tl.find_tag(tag) == TagItem(mem, addr)


def libtypes_tag_list_set_test():
    mem, addr = build_tag_list(
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
    )
    tl = TagList(mem, addr)
    assert not tl.set_tag(MyTag.BAZ_TAG, 20)
    assert tl.set_tag(MyTag.FOO_TAG, 20)
    tag = TagItem(mem, addr)
    assert tag.data.val == 20


def libtypes_tag_list_delete_test():
    mem, addr = build_tag_list(
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
    )
    tl = TagList(mem, addr)
    assert not tl.delete_tag(MyTag.BAZ_TAG)
    assert tl.delete_tag(MyTag.FOO_TAG)
    assert tl.to_list() == [(MyTag.BAR_TAG, 13)]


def libtypes_tag_list_get_tag_data_test():
    mem, addr = build_tag_list(
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
    )
    tl = TagList(mem, addr)
    assert tl.get_tag_data(MyTag.BAZ_TAG, 42) == 42
    assert tl.get_tag_data(MyTag.FOO_TAG, 42) == 12


def libtypes_tag_list_clone_to_test():
    mem, addr = build_tag_list(
        MyTag.FOO_TAG,
        12,
        MyTag.BAR_TAG,
        13,
        CommonTag.TAG_DONE,
        0,
    )
    tl = TagList(mem, addr)
    build_tag_list(0, 0, 0, 0, 0, 0, mem=mem, base=0x040)
    tl2 = TagList(mem, 0x40)
    tl.clone_to(tl2)
    assert tl2.to_list() == [(MyTag.FOO_TAG, 12), (MyTag.BAR_TAG, 13)]


# --- tag array ops ---


def libtypes_tag_array_find_test():
    mem, addr = build_tag_array(
        MyTag.FOO_TAG,
        MyTag.BAR_TAG,
    )
    tl = TagArray(mem, addr)
    assert tl.find_tag(MyTag.BAZ_TAG) is False
    assert tl.find_tag(MyTag.FOO_TAG) is True
    assert tl.to_list() == [MyTag.FOO_TAG, MyTag.BAR_TAG]


# --- alloc tag array ---


def libtypes_tag_array_alloc_empty_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # empty list
    tl = TagArray.alloc(alloc)
    assert len(tl) == 0
    tl.free()
    assert alloc.is_all_free()


def libtypes_tag_array_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    tl = TagArray.alloc(alloc, MyTag.FOO_TAG, MyTag.BAR_TAG)
    assert len(tl) == 2
    assert tl.to_list() == [MyTag.FOO_TAG, MyTag.BAR_TAG]
    tl.free()
    assert alloc.is_all_free()
