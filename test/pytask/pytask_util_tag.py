from enum import IntEnum
from amitools.vamos.libtypes import TagList, TagItem
from amitools.vamos.astructs import APTR


class MyTag(IntEnum):
    FOO_TAG = 1000
    BAR_TAG = 1001
    BAZ_TAG = 1002


def run_util_func(vamos_task, func):
    def task(ctx, task):
        # try to open utility lib
        lib = ctx.proxies.open_lib_proxy("utility.library")
        assert lib is not None
        # call lib func
        func(ctx, lib)
        # close lib
        ctx.proxies.close_lib_proxy(lib)
        return 0

    exit_codes = vamos_task.run([task], args=["-l", "utility:info"])
    assert exit_codes[0] == 0


def pytask_util_tag_find_tag_item_test(vamos_task):
    def func(ctx, lib):
        # build tag list
        tl = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 1), (MyTag.BAR_TAG, 2))
        assert tl is not None
        # test func
        tag = lib.FindTagItem(MyTag.BAR_TAG, tl, wrap_res=TagItem)
        assert type(tag) is TagItem
        assert tag.get_addr() == tl.get_addr() + 8
        assert tag.get_tag() == MyTag.BAR_TAG
        tag = lib.FindTagItem(MyTag.BAZ_TAG, tl, wrap_res=TagItem)
        assert tag is None
        # free tag list
        tl.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_get_tag_data_test(vamos_task):
    def func(ctx, lib):
        # build tag list
        tl = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 1), (MyTag.BAR_TAG, 2))
        assert tl is not None
        # test func
        val = lib.GetTagData(MyTag.BAR_TAG, 21, tl)
        assert val == 2
        val = lib.GetTagData(MyTag.BAZ_TAG, 42, tl)
        assert val == 42
        # free tag list
        tl.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_next_tag_item_test(vamos_task):
    def func(ctx, lib):
        # build tag list
        tl = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 1), (MyTag.BAR_TAG, 2))
        assert tl is not None
        # get a ptr
        tag = tl.get_first_tag()
        aptr = APTR(TagItem).alloc(ctx.alloc)
        aptr.ref = tag

        # no list?
        assert lib.NextTagItem(0) == 0

        # first entry
        res = lib.NextTagItem(aptr)
        assert res == tl.get_addr()
        # ptr points to next
        assert aptr.aptr == tl.get_addr() + 8

        # next entry
        res = lib.NextTagItem(aptr)
        assert res == tl.get_addr() + 8
        assert aptr.aptr == tl.get_addr() + 16

        # no more
        assert lib.NextTagItem(aptr) == 0

        # aptr free
        aptr.free()
        # free tag list
        tl.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_pack_bool_tags_test(vamos_task):
    def func(ctx, lib):
        # build tag list
        bool_map = TagList.alloc(
            ctx.alloc, (MyTag.FOO_TAG, 0x2), (MyTag.BAR_TAG, 0x4), (MyTag.BAZ_TAG, 0x8)
        )
        assert bool_map is not None
        tag_list = TagList.alloc(
            ctx.alloc, (MyTag.FOO_TAG, True), (MyTag.BAR_TAG, False)
        )
        assert tag_list is not None

        # map
        val = lib.PackBoolTags(0x4, tag_list, bool_map)
        assert val == 0x2

        # free tag list
        tag_list.free()
        bool_map.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_filter_tag_changes_test(vamos_task):
    def func(ctx, lib):
        # build tag list
        orig_list = TagList.alloc(
            ctx.alloc, (MyTag.FOO_TAG, 2), (MyTag.BAR_TAG, 4), (MyTag.BAZ_TAG, 8)
        )
        assert orig_list is not None
        change_list = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 2), (MyTag.BAR_TAG, 8))
        assert change_list is not None

        lib.FilterTagChanges(change_list, orig_list, 0)

        assert orig_list.to_list() == [
            (MyTag.FOO_TAG, 2),
            (MyTag.BAR_TAG, 4),
            (MyTag.BAZ_TAG, 8),
        ]
        assert change_list.to_list() == [(MyTag.BAR_TAG, 8)]

        # free tag list
        change_list.free()
        orig_list.free()

    run_util_func(vamos_task, func)
