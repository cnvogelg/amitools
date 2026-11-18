"""dos.library segment/resident calls (RKRM AmigaDOS 3, LoadSeg/UnLoadSeg
and resident segments).

``NewLoadSeg`` is the tag-list variant of ``LoadSeg`` (Vamos supports no
load tags, so only the file is used), ``InternalUnLoadSeg`` shares the
``UnLoadSeg`` bookkeeping and ``RemSegment`` unlinks a resident segment added
by ``AddSegment``.
"""

from amitools.vamos.libstructs import SegmentStruct
from amitools.vamos.log import log_dos

from .Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_OBJECT_WRONG_TYPE,
    ERROR_REQUIRED_ARG_MISSING,
)


def new_load_seg(dos, ctx, name, tag_list):
    if not name:
        return 0
    if tag_list is not None and len(tag_list) > 0:
        log_dos.warning("NewLoadSeg(%s): tags are not supported", name)
    lock = dos.get_current_dir(ctx)
    return dos._load_seg_list(ctx, name, lock)


def internal_unload_seg(dos, ctx, seg_list, free_func):
    if free_func:
        log_dos.info(
            "InternalUnLoadSeg(%06x): freefunc %06x is not called",
            seg_list,
            free_func,
        )
    else:
        log_dos.info("InternalUnLoadSeg(%06x)", seg_list)
    dos._unload_seg_list(ctx, seg_list)


def rem_segment(dos, ctx, seg):
    """remove a resident segment node from the DOS resident list"""
    if seg == 0:
        return DOSFALSE, ERROR_REQUIRED_ARG_MISSING
    head = dos.dos_info_struct.di_NetHand.aptr
    prev = 0
    cur = head
    node = None
    while cur != 0:
        node = SegmentStruct(ctx.mem, cur)
        if cur == seg:
            break
        prev = cur
        cur = node.seg_Next.aptr
    if cur != seg:
        return DOSFALSE, ERROR_OBJECT_NOT_FOUND
    next_addr = node.seg_Next.aptr
    if prev:
        SegmentStruct(ctx.mem, prev).seg_Next.aptr = next_addr
    else:
        dos.dos_info_struct.di_NetHand.aptr = next_addr
    if seg in dos.resident:
        dos.resident.remove(seg)
    log_dos.info("RemSegment(%06x)", seg)
    dos._free_mem(seg)
    return DOSTRUE, 0


# ----- fd functions -----


def load_seg(dos, ctx, name_ptr):
    name = ctx.mem.r_cstr(name_ptr)
    lock = dos.get_current_dir(ctx)
    return dos._load_seg_list(ctx, name, lock)


def unload_seg(dos, ctx, b_addr):
    dos._unload_seg_list(ctx, b_addr)


def internal_load_seg(dos, ctx, fh_baddr, table_ptr, func_ptr, stack_ptr):
    # FIXME: For now, just fail
    log_dos.warning(
        "InternalLoadSeg: fh=%06x table=%06x funcptr=%06x stack_ptr=%06x"
        " -> not implemented!",
        fh_baddr,
        table_ptr,
        func_ptr,
        stack_ptr,
    )
    dos.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
    return 0


def find_segment(dos, ctx, name_ptr, start, system):
    needle = ctx.mem.r_cstr(name_ptr)
    if start == 0:
        seg_addr = dos.dos_info_struct.di_NetHand.aptr
    else:
        seg_addr = SegmentStruct(ctx.mem, start).seg_Next.aptr
    log_dos.info("FindSegment(%s)", needle)
    while seg_addr != 0:
        segment = SegmentStruct(ctx.mem, seg_addr)
        name_addr = seg_addr + SegmentStruct.sdef.seg_Name.offset
        name = ctx.mem.r_bstr(name_addr)
        seg_uc = segment.seg_UC.val
        if name.lower() == needle.lower():
            if (system and seg_uc < 0) or (not system and seg_uc > 0):
                seg = segment.seg_Seg.aptr
                log_dos.info("FindSegment(%s) -> %s", name, seg)
                return seg_addr
        seg_addr = segment.seg_Next.aptr
    return 0


def add_segment(dos, ctx, name_ptr, seglist, system):
    seglist = seglist << 2
    name = ctx.mem.r_cstr(name_ptr)
    seg_addr = dos._alloc_mem("Segment", SegmentStruct.get_size() + len(name) + 1)
    name_addr = seg_addr + SegmentStruct.sdef.seg_Name.offset
    segment = SegmentStruct(ctx.mem, seg_addr)
    head_addr = dos.dos_info_struct.di_NetHand.aptr
    segment.seg_Next.aptr = head_addr
    segment.seg_UC.val = system
    segment.seg_Seg.aptr = seglist
    ctx.mem.w_bstr(name_addr, name)
    dos.dos_info_struct.di_NetHand.aptr = seg_addr
    log_dos.info("AddSegment(%s,%06x) -> %06x", name, seglist, seg_addr)
    dos.resident.append(seg_addr)
    # Adding a resident command to the registered seglists.
    b_addr = seglist >> 2
    if b_addr not in dos.seg_lists:
        dos.seg_lists[b_addr] = name
    return -1


def check_signal(dos, ctx, sigmask):
    # THOR: Fixme. We really need to get the signal
    # mask from the tty here.
    return 0
