from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.lib.util.TagList import *
from amitools.vamos.lib.util.AmiDate import *
from amitools.vamos.log import *

from math import trunc

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
    def NextTagItem(self, ctx):
        ti_ptr_addr = ctx.cpu.r_reg(REG_A0)
        ti_addr = ctx.mem.r32(ti_ptr_addr)
        ti_addr = next_tag_item(ctx, ti_addr)
        if ti_addr is None:
            next_addr = 0
        else:
            next_addr = ti_addr + 8
        ctx.mem.w32(ti_ptr_addr, next_addr)
        return ti_addr

    def FindTagItem(self, ctx):
        tagValue = ctx.cpu.r_reg(REG_D0)
        ti_addr = ctx.cpu.r_reg(REG_A0)
        if ti_addr == 0:
            return 0
        while True:
            ti_addr = next_tag_item(ctx, ti_addr)
            if ti_addr is None:
                return 0
            tag, _ = get_tag(ctx, ti_addr)
            if tag == tagValue:
                return ti_addr
            ti_addr += 8

    def GetTagData(self, ctx):
        defaultValue = ctx.cpu.r_reg(REG_D1)
        ti_addr = self.FindTagItem(ctx)
        if ti_addr != 0:
            return get_tag(ctx, ti_addr)[1]
        else:
            return defaultValue

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


    def PackBoolTags(self, ctx):
        initialFlags = ctx.cpu.r_reg(REG_D0)
        tagList_addr = ctx.cpu.r_reg(REG_A0)
        boolMap_addr = ctx.cpu.r_reg(REG_A1)

        boolflags = pack_bool_tags(ctx, initialFlags, tagList_addr, boolMap_addr)
        log_utility.info(
            "PackBoolTags(initialFlags=%08x, tagList=%08x, boolMap=%08x) => %08x",
            initialFlags,
            tagList_addr,
            boolMap_addr,
            boolflags,
        )
        return boolflags
    

def read_tag_list(ctx, tagList_addr):
    """
    Reads a tag list from the given address.
    Returns a list of (tag, value) tuples.
    """
    tagList = []
    ti_addr = tagList_addr
    while True:
        ti = next_tag_item(ctx, ti_addr)
        if ti is None:
            break
        tag, value = get_tag(ctx, ti)
        tagList.append((tag, value))
        ti_addr += 8  # Assuming each TagItem is 8 bytes
    return tagList

def pack_bool_tags(ctx, initialFlags, tagList_addr, boolMap_addr):
    """
    Packs boolean tags from a tag list into a bit-flag representation.
    """
    boolflags = initialFlags
    tagList = read_tag_list(ctx, tagList_addr)  # List of (tag, value)
    boolMap = read_tag_list(ctx, boolMap_addr)  # List of (tag, flag)

    # Convert boolMap to a dictionary for fast lookup
    boolMapDict = {tag: flag for tag, flag in boolMap}

    for tag, value in tagList:
        if tag in boolMapDict:
            flag_value = boolMapDict[tag]
            if value:
                boolflags |= flag_value
            else:
                boolflags &= ~flag_value

    return boolflags

"""
NAME
    PackBoolTags --  Builds a "Flag" word from a TagList. (V36)

SYNOPSIS
    boolflags = PackBoolTags( initialFlags, tagList, boolMap )
    D0                        D0            A0       A1

    ULONG PackBoolTags( ULONG initialFlags, struct TagItem *tagList,
                        struct TagItem *boolMap );

FUNCTION
    Picks out the Boolean TagItems in a TagItem list and converts
    them into bit-flag representations according to a correspondence
    defined by the TagItem list 'BoolMap.'

    A Boolean TagItem is one where only the logical value of
    the ti_Data is relevant.  If this field is 0, the value is
    FALSE, otherwise TRUE.


INPUTS
    initialFlags    - a starting set of bit-flags which will be changed
                      by the processing of TRUE and FALSE Boolean tags
                      in tagList.
    tagList         - a TagItem list which may contain several TagItems
                      defined to be "Boolean" by their presence in
                      boolMap.  The logical value of ti_Data determines
                      whether a TagItem causes the bit-flag value related
                      by boolMap to set or cleared in the returned flag
                      longword.
    boolMap         - a TagItem list defining the Boolean Tags to be
                      recognized, and the bit (or bits) in the returned
                      longword that are to be set or cleared when a
                      Boolean Tag is found to be TRUE or FALSE in
                      tagList.

RESULT
    boolflags       - the accumulated longword of bit-flags, starting
                      with InitialFlags and modified by each Boolean
                      TagItem encountered.

EXAMPLE

    /* define some nice user tag values ... */
    enum mytags { tag1 = TAG_USER+1, tag2, tag3, tag4, tag5 };

    /* this TagItem list defines the correspondence between Boolean tags
     * and bit-flag values.
     */
    struct TagItem       boolmap[] = {
        { tag1,  0x0001 },
        { tag2,  0x0002 },
        { tag3,  0x0004 },
        { tag4,  0x0008 },
        { TAG_DONE }
    };

    /* You are probably passed these by some client, and you want
     * to "collapse" the Boolean content into a single longword.
     */

    struct TagItem       boolexample[] = {
        { tag1,  TRUE },
        { tag2,  FALSE },
        { tag5, Irrelevant },
        { tag3,  TRUE },
        { TAG_DONE }
    };

    /* Perhaps 'boolflags' already has a current value of 0x800002. */
    boolflags = PackBoolTags( boolflags, boolexample, boolmap );

    /* The resulting new value of 'boolflags' will be 0x80005. /*

BUGS
    There are some undefined cases if there is duplication of
    a given Tag in either list.  It is probably safe to say that
    the *last* of identical Tags in TagList will hold sway.

SEE ALSO
    utility/tagitem.h, GetTagData(), FindTagItem(), NextTagItem()
"""