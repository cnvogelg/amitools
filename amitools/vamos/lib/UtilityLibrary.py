from math import trunc
from amitools.vamos.machine.regs import REG_D0, REG_D1, REG_A0, REG_A1
from amitools.vamos.astructs import APTR
from amitools.vamos.libcore import LibImpl
from amitools.vamos.libtypes import TagList, TagItem, CommonTag, TagArray, Tag
from amitools.vamos.lib.util.AmiDate import *
from amitools.vamos.lib.util.flags import MapTagsFlag, FilterTagItemsFlag
from amitools.vamos.lib.lexec.flags import MemFlag
from amitools.vamos.log import *


class UtilityLibrary(LibImpl):
    def UDivMod32(self, ctx):
        dividend = ctx.cpu.r_reg(REG_D0)
        divisor = ctx.cpu.r_reg(REG_D1)
        quot = dividend // divisor
        rem = dividend % divisor
        log_utility.info(
            "UDivMod32(dividend=%u, divisor=%u) => (quotient=%u, remainder=%u)"
            % (dividend, divisor, quot, rem)
        )
        return [quot, rem]

    def SDivMod32(self, ctx):
        dividend = ctx.cpu.r_reg(REG_D0)
        if dividend >= 0x80000000:
            dividend = dividend - 0x100000000
        divisor = ctx.cpu.r_reg(REG_D1)
        if divisor >= 0x80000000:
            divisor = divisor - 0x100000000

        # python modulos differs from c modulo
        quot = trunc(float(dividend) / divisor)
        rem = dividend - divisor * quot

        if quot < 0:
            quot = quot + 0x100000000
        if rem < 0:
            rem = rem + 0x100000000
        log_utility.info(
            "SDivMod32(dividend=%u, divisor=%u) => (quotient=%u, remainder=%u)"
            % (dividend, divisor, quot, rem)
        )
        return [quot, rem]

    def UMult32(self, ctx):
        a = ctx.cpu.r_reg(REG_D0)
        b = ctx.cpu.r_reg(REG_D1)
        c = (a * b) & 0xFFFFFFFF
        log_utility.info("UMult32(a=%u, b=%u) => %u", a, b, c)
        return c

    def SMult32(self, ctx):
        # Z_{2^32} is a ring. It does not matter whether we multiply signed or unsigned
        a = ctx.cpu.r_reg(REG_D0)
        b = ctx.cpu.r_reg(REG_D1)
        c = (a * b) & 0xFFFFFFFF
        log_utility.info("SMult32(a=%d, b=%d) => %d", a, b, c)
        return c

    def ToUpper(self, ctx):
        a = ctx.cpu.r_reg(REG_D0) & 0xFF
        return ord(chr(a).upper())

    def Stricmp(self, ctx):
        str1_addr = ctx.cpu.r_reg(REG_A0)
        str2_addr = ctx.cpu.r_reg(REG_A1)
        str1 = ctx.mem.r_cstr(str1_addr)
        str2 = ctx.mem.r_cstr(str2_addr)
        log_utility.info(
            'Stricmp(%08x="%s",%08x="%s")' % (str1_addr, str1, str2_addr, str2)
        )
        if str1.lower() < str2.lower():
            return -1
        elif str1.lower() > str2.lower():
            return +1
        else:
            return 0

    def Strnicmp(self, ctx):
        str1_addr = ctx.cpu.r_reg(REG_A0)
        str2_addr = ctx.cpu.r_reg(REG_A1)
        length = ctx.cpu.r_reg(REG_D0)
        str1 = ctx.mem.r_cstr(str1_addr)[:length]
        str2 = ctx.mem.r_cstr(str2_addr)[:length]
        log_utility.info(
            'Strnicmp(%08x="%s",%08x="%s")' % (str1_addr, str1, str2_addr, str2)
        )
        if str1.lower() < str2.lower():
            return -1
        elif str1.lower() > str2.lower():
            return +1
        else:
            return 0

    # Tags

    def FindTagItem(self, ctx, tag_val, tag_list: TagList) -> TagItem:
        if not tag_list:
            return None
        log_utility.info("FindTagItem(tag=%08x, list=%s)", tag_val, tag_list)
        tag = tag_list.find_tag(tag_val)
        if tag:
            log_utility.info("found tag: %r", tag)
            return tag
        else:
            log_utility.info("no tag!")
            return None

    def GetTagData(self, ctx, tag_val, default_val, tag_list_addr):
        if tag_list_addr == 0:
            return default_val
        log_utility.info(
            "GetTagData(tag=%08x, def=%08x, list=%08x)",
            tag_val,
            default_val,
            tag_list_addr,
        )
        tl = TagList(ctx.mem, tag_list_addr)
        data = tl.get_tag_data(tag_val, default_val)
        log_utility.info("result data=%08x", data)
        return data

    def PackBoolTags(self, ctx, init_flags, tag_list_addr, bool_map_addr):
        if tag_list_addr == 0 or bool_map_addr == 0:
            return 0
        log_utility.info(
            "PackBoolTags(flags=%08x, list=%08x, map=%08x)",
            init_flags,
            tag_list_addr,
            bool_map_addr,
        )
        tag_list = TagList(ctx.mem, tag_list_addr)
        bool_map = TagList(ctx.mem, bool_map_addr)
        result = init_flags
        for tag in tag_list:
            on_flag = tag.get_data()
            bool_tag = bool_map.find_tag(tag)
            if bool_tag:
                mask_val = bool_tag.get_data()
                if on_flag:
                    result |= mask_val
                else:
                    result &= ~mask_val
        log_utility.info("result mask=%08x", result)
        return result

    def NextTagItem(self, ctx, ti_ptr: APTR(APTR(TagItem))):
        if ti_ptr is None:
            return 0
        tag_ptr = ti_ptr.ref
        log_utility.info("NextTagItem(ti_ptr=%s) -> tag=%s", ti_ptr, tag_ptr)
        if tag_ptr is None:
            return 0
        tag = tag_ptr.ref
        real_tag = tag.next_real_tag()
        if real_tag is None:
            log_utility.info("no real tag!")
            tag_ptr.ref = None
            return 0
        else:
            succ_tag = tag.succ_tag()
            log_utility.info("real tag=%r, succ_tag=%r", tag, succ_tag)
            tag_ptr.ref = succ_tag
            return tag.get_addr()

    def FilterTagChanges(self, ctx, change_list: TagList, orig_list: TagList, apply):
        if change_list is None or orig_list is None:
            return 0
        log_utility.info(
            "FilterTagChanges(change=%s, orig=%s, apply=%s)",
            change_list,
            orig_list,
            apply,
        )
        for tag in change_list:
            orig_tag = orig_list.find_tag(tag)
            if orig_tag:
                tag_data = tag.get_data()
                if tag_data == orig_tag.get_data():
                    tag.remove()
                elif apply:
                    orig_tag.set_data(tag_data)

    def MapTags(self, ctx, tag_list: TagList, map_list: TagList, map_type):
        if tag_list is None or map_list is None:
            return
        log_utility.info(
            "MapTags(tag_list=%s, map_list=%s, map_type=%s)",
            tag_list,
            map_list,
            map_type,
        )
        for tag in tag_list:
            map_tag = map_list.find_tag(tag)
            if map_tag:
                log_utility.debug("map tag %s -> %s", tag, map_tag)
                tag.set_tag(map_tag.get_data())
            elif map_type == MapTagsFlag.MAP_REMOVE_NOT_FOUND:
                log_utility.debug("remove tag %s", tag)
                tag.remove()

    def AllocateTagItems(self, ctx, num_tags) -> TagList:
        log_utility.info("AllocateTagItems(num_tags=%s)", num_tags)
        exec_lib = ctx.proxies.get_exec_lib_proxy()
        size = num_tags * 8
        addr = exec_lib.AllocVec(size, MemFlag.MEMF_CLEAR | MemFlag.MEMF_PUBLIC)
        log_utility.info("addr=%08x", addr)
        return TagList(ctx.mem, addr)

    def CloneTagItems(self, ctx, tag_list: TagList) -> TagList:
        log_utility.info("CloneTagItems(tag_list=%s)", tag_list)
        num_items = len(tag_list)
        log_utility.debug("num_items=%d", num_items)
        new_tag_list = self.AllocateTagItems(ctx, num_items)
        if new_tag_list is None:
            return None
        log_utility.debug("new_list=%s", new_tag_list)
        tag_list.clone_to(new_tag_list)
        return new_tag_list

    def FreeTagItems(self, ctx, tag_list):
        log_utility.info("FreeTagItems(addr=%08x)", tag_list)
        exec_lib = ctx.proxies.get_exec_lib_proxy()
        exec_lib.FreeVec(tag_list)

    def RefreshTagItemClones(self, ctx, clone_list: TagList, orig_list: TagList):
        log_utility.info(
            "RefreshTagItemClones(clone=%s, orig=%s)", clone_list, orig_list
        )
        if clone_list is None:
            return
        if orig_list is None:
            # if orig list is not available then clear clone
            clone_list.get_first_tag().remove()
            return
        orig_list.clone_to(clone_list)

    def TagInArray(self, ctx, tag_value, tag_array: TagArray):
        log_utility.info("TagInArray(val=%08x, array=%s)", tag_value, tag_array)
        return tag_array.find_tag(tag_value)

    def FilterTagItems(self, ctx, tag_list: TagList, filter_array: TagArray, logic):
        log_utility.info(
            "FilterTagItems(tag_list=%s, filter_array=%s, logic=%s)",
            tag_list,
            filter_array,
            logic,
        )
        valid = 0
        for tag in tag_list:
            found = filter_array.find_tag(tag)
            if logic == FilterTagItemsFlag.TAGFILTER_AND:
                if found:
                    valid += 1
                else:
                    tag.remove()
            elif logic == FilterTagItemsFlag.TAGFILTER_NOT:
                if found:
                    tag.remove()
                else:
                    valid += 1
        return valid

    # ---- Date -----

    def Amiga2Date(self, ctx):
        seconds = ctx.cpu.r_reg(REG_D0)
        date_ptr = ctx.cpu.r_reg(REG_A0)

        t = date_at(seconds)
        log_utility.info("Amiga2Date: seconds=%d -> time=%s", seconds, t)
        write_clock_data(t, ctx.mem, date_ptr)

    def Date2Amiga(self, ctx):
        date_ptr = ctx.cpu.r_reg(REG_A0)

        t = read_clock_data(ctx.mem, date_ptr)
        if t is None:
            log_utility.warning("Date2Amiga: invalid date! @%08x", date_ptr)
            return 0
        seconds = seconds_since(t)
        log_utility.info("Date2Amige: time=%s -> seconds=%u", t, seconds)
        return seconds

    def CheckDate(self, ctx):
        date_ptr = ctx.cpu.r_reg(REG_A0)

        t = read_clock_data(ctx.mem, date_ptr)
        if t is None:
            log_utility.info("CheckDate: invalid date! @%08x", date_ptr)
            return 0
        seconds = seconds_since(t)
        log_utility.info("CheckDate: time=%s -> seconds=%u", t, seconds)
        return seconds
