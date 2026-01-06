from enum import IntEnum
from amitools.vamos.libtypes import TagList, TagItem, CommonTag, TagArray
from amitools.vamos.astructs import APTR
from amitools.vamos.lib.util.flags import (
    MapTagsFlag,
    FilterTagItemsFlag,
    PackStructureTagsFlag,
)


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

    exit_codes = vamos_task.run([task], args=["-l", "utility:debug"])
    assert exit_codes[0] == 0


def pytask_util_tag_find_tag_item_test(vamos_task):
    def func(ctx, lib):
        # build tag list
        tl = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 1), (MyTag.BAR_TAG, 2))
        assert tl is not None
        # test func
        tag = lib.FindTagItem(MyTag.BAR_TAG, tl)
        assert type(tag) is TagItem
        assert tag.get_addr() == tl.get_addr() + 8
        assert tag.get_tag() == MyTag.BAR_TAG
        tag = lib.FindTagItem(MyTag.BAZ_TAG, tl)
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


def pytask_util_map_tags_test(vamos_task):
    def func(ctx, lib):
        # build tag list
        orig_list = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 2), (MyTag.BAR_TAG, 4))
        assert orig_list is not None
        map_list = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, MyTag.BAZ_TAG))
        assert map_list is not None

        # MAP_KEEP_NOT_FOUND
        lib.MapTags(orig_list, map_list, MapTagsFlag.MAP_KEEP_NOT_FOUND)
        assert orig_list.to_list() == [
            (MyTag.BAZ_TAG, 2),
            (MyTag.BAR_TAG, 4),
        ]

        # restore list
        orig_list.get_first_tag().set_tag(MyTag.FOO_TAG)

        # MAP_REMOVE_NOT_FOUND
        lib.MapTags(orig_list, map_list, MapTagsFlag.MAP_REMOVE_NOT_FOUND)
        assert orig_list.to_list() == [
            (MyTag.BAZ_TAG, 2),
        ]

        # free tag list
        map_list.free()
        orig_list.free()

    run_util_func(vamos_task, func)


def pytask_util_alloc_free_tag_items_test(vamos_task):
    def func(ctx, lib):
        tag_list = lib.AllocateTagItems(8)
        assert tag_list is not None
        lib.FreeTagItems(tag_list)

    run_util_func(vamos_task, func)


def pytask_util_clone_tag_items_test(vamos_task):
    def func(ctx, lib):
        tag_list = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 2), (MyTag.BAR_TAG, 4))
        assert tag_list is not None

        # clone list
        clone_list = lib.CloneTagItems(tag_list)
        assert clone_list is not None

        # check for equality
        for tag1, tag2 in zip(tag_list, clone_list):
            assert tag1.has_same_tag_data(tag2)

        # clear list
        clone_list.get_first_tag().end_list()
        assert len(clone_list) == 0

        # refresh
        lib.RefreshTagItemClones(clone_list, tag_list)

        # check for equality
        for tag1, tag2 in zip(tag_list, clone_list):
            assert tag1.has_same_tag_data(tag2)

        # free cloned list
        lib.FreeTagItems(clone_list)
        tag_list.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_in_array_test(vamos_task):
    def func(ctx, lib):
        # prepare tag array
        tag_array = TagArray.alloc(ctx.alloc, MyTag.FOO_TAG, MyTag.BAR_TAG)
        assert tag_array is not None

        assert lib.TagInArray(MyTag.FOO_TAG, tag_array) == 1
        assert lib.TagInArray(MyTag.BAZ_TAG, tag_array) == 0

        tag_array.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_filter_tag_items_test(vamos_task):
    def func(ctx, lib):
        # prepare tag array
        tag_list = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 2), (MyTag.BAR_TAG, 4))
        assert tag_list is not None
        tag_array = TagArray.alloc(ctx.alloc, MyTag.BAR_TAG)
        assert tag_array is not None

        # AND
        valid = lib.FilterTagItems(
            tag_list, tag_array, FilterTagItemsFlag.TAGFILTER_AND
        )
        assert valid == 1
        assert tag_list.to_list() == [(MyTag.BAR_TAG, 4)]

        # restore list
        tag_list.get_first_tag().set_tag(MyTag.FOO_TAG)

        # NOT
        valid = lib.FilterTagItems(
            tag_list, tag_array, FilterTagItemsFlag.TAGFILTER_NOT
        )
        assert valid == 1
        assert tag_list.to_list() == [(MyTag.FOO_TAG, 2)]

        tag_array.free()
        tag_list.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_apply_tag_changes_test(vamos_task):
    def func(ctx, lib):
        tag_list = TagList.alloc(ctx.alloc, (MyTag.FOO_TAG, 2), (MyTag.BAR_TAG, 4))
        assert tag_list is not None
        change_list = TagList.alloc(ctx.alloc, (MyTag.BAR_TAG, MyTag.BAZ_TAG))
        assert change_list is not None

        lib.ApplyTagChanges(tag_list, change_list)

        assert tag_list.to_list() == [(MyTag.FOO_TAG, 2), (MyTag.BAZ_TAG, 4)]

        change_list.free()
        tag_list.free()

    run_util_func(vamos_task, func)


def build_pack_table(ctx, pack_table):
    size = len(pack_table) * 4
    mem = ctx.alloc.alloc_memory(size)
    addr = mem.addr
    ptr = addr
    for entry in pack_table:
        ctx.mem.w32(ptr, entry & 0xFFFFFFFF)
        ptr += 4
    return mem, addr


def pytask_util_tag_pack_structure_tags_test(vamos_task):
    def func(ctx, lib):
        tag_list = TagList.alloc(
            ctx.alloc,
            (MyTag.FOO_TAG, 0xDEADBEEF),
            (MyTag.BAR_TAG, 0xBABE),
            (MyTag.BAZ_TAG, 0xFE),
        )
        assert tag_list is not None

        pack_table = [
            MyTag.FOO_TAG,  # tag offset
            PackStructureTagsFlag.PKCTRL_ULONG,  # tag offset=0, data offset=0
            PackStructureTagsFlag.PKCTRL_UWORD
            | (1 << 16)
            | 4,  # tag_offset=1, data_offset=4
            PackStructureTagsFlag.PKCTRL_UBYTE
            | (2 << 16)
            | 6,  # tag_offset=1, data_offset=6
            0,  # end of table
        ]
        mem_obj, addr = build_pack_table(ctx, pack_table)

        pack = 0x100

        num = lib.PackStructureTags(pack, addr, tag_list)
        assert num == 3

        assert ctx.mem.r32(pack) == 0xDEADBEEF
        assert ctx.mem.r16(pack + 4) == 0xBABE
        assert ctx.mem.r8(pack + 6) == 0xFE

        ctx.alloc.free_memory(mem_obj)
        tag_list.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_pack_structure_tags_signed_test(vamos_task):
    def func(ctx, lib):
        tag_list = TagList.alloc(
            ctx.alloc,
            (MyTag.FOO_TAG, -3),
            (MyTag.BAR_TAG, -2),
            (MyTag.BAZ_TAG, -1),
        )
        assert tag_list is not None

        pack_table = [
            MyTag.FOO_TAG,  # tag offset
            PackStructureTagsFlag.PKCTRL_LONG,  # tag offset=0, data offset=0
            PackStructureTagsFlag.PKCTRL_WORD
            | (1 << 16)
            | 4,  # tag_offset=1, data_offset=4
            PackStructureTagsFlag.PKCTRL_BYTE
            | (2 << 16)
            | 6,  # tag_offset=1, data_offset=6
            0,  # end of table
        ]
        mem_obj, addr = build_pack_table(ctx, pack_table)

        pack = 0x100

        num = lib.PackStructureTags(pack, addr, tag_list)
        assert num == 3

        assert ctx.mem.r32s(pack) == -3
        assert ctx.mem.r16s(pack + 4) == -2
        assert ctx.mem.r8s(pack + 6) == -1

        ctx.alloc.free_memory(mem_obj)
        tag_list.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_unpack_structure_tags_test(vamos_task):
    def func(ctx, lib):
        tag_list = TagList.alloc(
            ctx.alloc,
            (MyTag.FOO_TAG, 0),
            (MyTag.BAR_TAG, 0),
            (MyTag.BAZ_TAG, 0),
        )
        assert tag_list is not None

        pack_table = [
            MyTag.FOO_TAG,  # tag offset
            PackStructureTagsFlag.PKCTRL_ULONG,  # tag offset=0, data offset=0
            PackStructureTagsFlag.PKCTRL_UWORD
            | (1 << 16)
            | 4,  # tag_offset=1, data_offset=4
            PackStructureTagsFlag.PKCTRL_UBYTE
            | (2 << 16)
            | 6,  # tag_offset=1, data_offset=6
            0,  # end of table
        ]
        mem_obj, addr = build_pack_table(ctx, pack_table)

        pack = 0x100
        ctx.mem.w32(pack, 0xDEADBEEF)
        ctx.mem.w16(pack + 4, 0xBABE)
        ctx.mem.w8(pack + 6, 0xFE)

        num = lib.UnpackStructureTags(pack, addr, tag_list)
        assert num == 3

        assert tag_list.to_list() == [
            (MyTag.FOO_TAG, 0xDEADBEEF),
            (MyTag.BAR_TAG, 0xBABE),
            (MyTag.BAZ_TAG, 0xFE),
        ]

        ctx.alloc.free_memory(mem_obj)
        tag_list.free()

    run_util_func(vamos_task, func)


def pytask_util_tag_unpack_structure_tags_signed_test(vamos_task):
    def func(ctx, lib):
        tag_list = TagList.alloc(
            ctx.alloc,
            (MyTag.FOO_TAG, 0),
            (MyTag.BAR_TAG, 0),
            (MyTag.BAZ_TAG, 0),
        )
        assert tag_list is not None

        pack_table = [
            MyTag.FOO_TAG,  # tag offset
            PackStructureTagsFlag.PKCTRL_LONG,  # tag offset=0, data offset=0
            PackStructureTagsFlag.PKCTRL_WORD
            | (1 << 16)
            | 4,  # tag_offset=1, data_offset=4
            PackStructureTagsFlag.PKCTRL_BYTE
            | (2 << 16)
            | 6,  # tag_offset=1, data_offset=6
            0,  # end of table
        ]
        mem_obj, addr = build_pack_table(ctx, pack_table)

        pack = 0x100
        ctx.mem.w32s(pack, -1)
        ctx.mem.w16s(pack + 4, -2)
        ctx.mem.w8s(pack + 6, -3)

        num = lib.UnpackStructureTags(pack, addr, tag_list)
        assert num == 3

        assert tag_list.to_list() == [
            (MyTag.FOO_TAG, -1 & 0xFFFFFFFF),
            (MyTag.BAR_TAG, -2 & 0xFFFFFFFF),
            (MyTag.BAZ_TAG, -3 & 0xFFFFFFFF),
        ]

        ctx.alloc.free_memory(mem_obj)
        tag_list.free()

    run_util_func(vamos_task, func)
