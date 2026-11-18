"""dos.library segment/resident calls (RKRM AmigaDOS 3, LoadSeg/UnLoadSeg
and resident segments).

``NewLoadSeg`` is the tag-list variant of ``LoadSeg`` (Vamos supports no
load tags, so only the file is used), ``InternalUnLoadSeg`` shares the
``UnLoadSeg`` bookkeeping and ``RemSegment`` unlinks a resident segment added
by ``AddSegment``.
"""

from amitools.vamos.libstructs import SegmentStruct
from amitools.vamos.log import log_dos

from .Error import DOSFALSE, DOSTRUE, ERROR_OBJECT_NOT_FOUND, ERROR_REQUIRED_ARG_MISSING


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
