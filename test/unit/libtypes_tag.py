from amitools.vamos.libtypes import Tag, TagList, CommonTags
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc

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


# --- TAG_DONE ---


def libtypes_tag_done_test():
    mem, addr = build_tag_list(CommonTags.TAG_DONE, 0)
    # check end tag
    tag = Tag(mem, addr)
    assert tag.tag.val == CommonTags.TAG_DONE
    assert tag.data.val == 0
    assert tag.get_tuple() == (CommonTags.TAG_DONE, 0)
    # no "real" tag
    assert tag.next_real_tag() is None
    assert tag.succ_tag() is None
    assert tag.succ_real_tag() is None


def libtypes_tag_list_done_test():
    mem, addr = build_tag_list(CommonTags.TAG_DONE, 0)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 0
    assert [a for a in tag_list] == []


# --- TAG_IGNORE ---


def libtypes_tag_ignore_test():
    """empty tag list with TAG_DONE only"""
    mem, addr = build_tag_list(CommonTags.TAG_IGNORE, 0, CommonTags.TAG_DONE, 0)
    # check tag
    tag = Tag(mem, addr)
    assert tag.tag.val == CommonTags.TAG_IGNORE
    assert tag.data.val == 0
    assert tag.get_tuple() == (CommonTags.TAG_IGNORE, 0)
    # no "real" tag
    assert tag.next_real_tag() is None
    assert tag.succ_tag() == Tag(mem, 0x18)
    assert tag.succ_real_tag() is None


def libtypes_tag_list_ignore_test():
    """empty tag list with TAG_DONE only"""
    mem, addr = build_tag_list(CommonTags.TAG_IGNORE, 0, CommonTags.TAG_DONE, 0)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 0
    assert [a for a in tag_list] == []

    mem, addr = build_tag_list(
        FOO_TAG, 12, CommonTags.TAG_IGNORE, 0, BAR_TAG, 13, CommonTags.TAG_DONE, 0
    )
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 2
    assert [a for a in tag_list] == [Tag(mem, 0x10), Tag(mem, 0x20)]
    assert tag_list.to_list() == [(FOO_TAG, 12), (BAR_TAG, 13)]


# --- TAG_MORE ---


def libtypes_tag_more_test():
    mem, addr = build_tag_list(CommonTags.TAG_MORE, 0x40, CommonTags.TAG_DONE, 0)
    build_tag_list(CommonTags.TAG_DONE, 0, mem=mem, base=0x40)
    # check tag
    tag = Tag(mem, addr)
    assert tag.tag.val == CommonTags.TAG_MORE
    assert tag.data.val == 0x40
    assert tag.get_tuple() == (CommonTags.TAG_MORE, 0x40)
    # no "real" tag
    assert tag.next_real_tag() is None
    assert tag.succ_tag() == Tag(mem, 0x40)
    assert tag.succ_real_tag() is None


def libtypes_tag_list_more_test():
    mem, addr = build_tag_list(CommonTags.TAG_MORE, 0x40, CommonTags.TAG_DONE, 0)
    build_tag_list(CommonTags.TAG_DONE, 0, mem=mem, base=0x40)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 0
    assert [a for a in tag_list] == []

    mem, addr = build_tag_list(
        FOO_TAG, 12, CommonTags.TAG_MORE, 0x40, CommonTags.TAG_DONE, 0
    )
    build_tag_list(BAR_TAG, 13, CommonTags.TAG_DONE, 0, mem=mem, base=0x40)
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 2
    assert [a for a in tag_list] == [Tag(mem, 0x10), Tag(mem, 0x40)]
    assert tag_list.to_list() == [(FOO_TAG, 12), (BAR_TAG, 13)]


# --- TAG_SKIP ---


def libtypes_tag_skip_test():
    mem, addr = build_tag_list(
        CommonTags.TAG_SKIP,
        2,
        FOO_TAG,
        12,
        BAR_TAG,
        13,
        BAZ_TAG,
        14,
        CommonTags.TAG_DONE,
        0,
    )
    # check tag
    tag = Tag(mem, addr)
    assert tag.tag.val == CommonTags.TAG_SKIP
    assert tag.data.val == 2
    assert tag.get_tuple() == (CommonTags.TAG_SKIP, 2)
    # no "real" tag
    assert tag.next_real_tag() == Tag(mem, 0x28)
    assert tag.succ_tag() == Tag(mem, 0x28)
    assert tag.succ_real_tag() == Tag(mem, 0x28)


def libtypes_tag_skip_more_test():
    mem, addr = build_tag_list(
        CommonTags.TAG_SKIP,
        2,
        FOO_TAG,
        12,
        BAR_TAG,
        13,
        BAZ_TAG,
        14,
        CommonTags.TAG_DONE,
        0,
    )
    tag_list = TagList(mem, addr)
    assert len(tag_list) == 1
    assert [a for a in tag_list] == [Tag(mem, 0x28)]
    assert tag_list.to_list() == [(BAZ_TAG, 14)]


# --- alloc tag list


def libtypes_tag_alloc_empty_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # empty list
    tl = TagList.alloc(alloc)
    assert len(tl) == 0
    tl.free()
    assert alloc.is_all_free()


def libtypes_tag_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    tl = TagList.alloc(alloc, (FOO_TAG, 1), (BAR_TAG, 2))
    assert len(tl) == 2
    assert tl.to_list() == [(FOO_TAG, 1), (BAR_TAG, 2)]
    tl.free()
    assert alloc.is_all_free()
