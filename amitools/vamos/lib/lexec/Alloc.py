# helper for Allocate()/Deallocate()

from amitools.vamos.log import log_exec
from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import MemHeaderStruct, MemChunkStruct


class MemChunk:
    def __init__(self, mc_next=None, mc_bytes=None, addr=None):
        self.addr = addr
        self.next = mc_next
        self.bytes = mc_bytes

    def __str__(self):
        return "[MC(%06x+%06x=%06x):next=%06x]" % (
            self.addr,
            self.bytes,
            self.addr + self.bytes,
            self.next,
        )

    def read(self, ctx, mc_addr):
        self.addr = mc_addr
        mc = AccessStruct(ctx.mem, MemChunkStruct, mc_addr)
        self.next = mc.r_s("mc_Next")
        self.bytes = mc.r_s("mc_Bytes")

    def write(self, ctx):
        mc = AccessStruct(ctx.mem, MemChunkStruct, self.addr)
        mc.w_s("mc_Next", self.next)
        mc.w_s("mc_Bytes", self.bytes)

    def read_next(self, ctx):
        if self.next == 0:
            return None
        else:
            mc = MemChunk()
            mc.read(ctx, self.next)
            return mc


class MemHdr:
    def __init__(self):
        self.addr = None
        self.first = None
        self.lower = None
        self.upper = None
        self.free = None
        self.total = None  # total bytes managed by header

    def __str__(self):
        return "[MH@%06x:(%06x+%06x=%06x):free=%06x,MC=%06x]" % (
            self.addr,
            self.lower,
            self.total,
            self.upper,
            self.free,
            self.first,
        )

    def read(self, ctx, mh_addr):
        self.addr = mh_addr
        mh = AccessStruct(ctx.mem, MemHeaderStruct, mh_addr)
        self.first = mh.r_s("mh_First")
        self.lower = mh.r_s("mh_Lower")
        self.upper = mh.r_s("mh_Upper")
        self.free = mh.r_s("mh_Free")
        self.total = self.upper - self.lower

    def write(self, ctx):
        mh = AccessStruct(ctx.mem, MemHeaderStruct, self.addr)
        # only update first/free
        mh.w_s("mh_First", self.first)
        mh.w_s("mh_Free", self.free)

    def read_first(self, ctx):
        if self.first == 0:
            return None
        else:
            mc = MemChunk()
            mc.read(ctx, self.first)
            return mc


def validate(ctx, mh):
    log_exec.debug("Header: %s", mh)
    sum_free = 0
    mc = mh.read_first(ctx)
    num = 0
    while mc:
        log_exec.debug("#%d: chunk: %s", num, mc)
        sum_free += mc.bytes
        mc = mc.read_next(ctx)
        num += 1
    # check if free size in header matches sum of chunks
    if sum_free != mh.free:
        log_exec.error("sum_free=%d != mh.free=%d", sum_free, mh.free)
        raise RuntimeError("MH Validation!")


def allocate(ctx, mh_addr, num_bytes, check=False):
    # nothing to allocate
    if num_bytes == 0:
        return 0

    # round size to nearest 8 byte
    ex = num_bytes & 7
    if ex != 0:
        num_bytes += 8 - ex

    log_exec.debug("ALLOC: mh_addr=%06x, num_bytes=%d", mh_addr, num_bytes)

    # read mem header
    mh = MemHdr()
    mh.read(ctx, mh_addr)
    log_exec.debug("read: %s", mh)

    # enough total free?
    if mh.free < num_bytes:
        return 0
    if mh.first == 0:
        return 0

    if check:
        validate(ctx, mh)

    # find chunk with enough free bytes
    mc_last = None
    mc = mh.read_first(ctx)
    log_exec.debug("read: %s", mc)
    while mc.bytes < num_bytes:
        mc_next = mc.read_next(ctx)
        log_exec.debug("read: %s", mc_next)
        if mc_next is None:
            # no memory found. chunks are too fragmented
            return 0
        mc_last = mc
        mc = mc_next

    # what's left in chunk?
    rem = mc.bytes - num_bytes
    if rem > 0:
        # some bytes left in chunk -> adjust size and keep it
        mc.bytes = rem
        mc.write(ctx)
        # allocate at end of chunk
        res_addr = mc.addr + rem
        log_exec.debug("shrink: %s", mc)
    else:
        # remove whole chunk
        if mc_last is None:
            # set new first
            mh.first = mc.next
            # mh will be written below
        else:
            mc_last.next = mc.next
            mc_last.write(ctx)
        # result is whole chunk
        res_addr = mc.addr
        log_exec.debug("remove: %s", mc)

    # update header
    mh.free -= num_bytes
    mh.write(ctx)
    log_exec.debug("done: %s", mh)

    return res_addr


def deallocate(ctx, mh_addr, blk_addr, num_bytes, check=False):
    # nothing to allocate
    if num_bytes == 0 or blk_addr == 0:
        return 0
    # round size to nearest 8 byte
    ex = num_bytes & 7
    if ex != 0:
        num_bytes += 8 - ex

    log_exec.debug(
        "DEALLOC: mh_addr=%06x, blk_addr=%06x, num_bytes=%d",
        mh_addr,
        blk_addr,
        num_bytes,
    )

    # read mem header
    mh = MemHdr()
    mh.read(ctx, mh_addr)
    log_exec.debug("read: %s", mh)

    # sanity check
    if blk_addr < mh.lower or (blk_addr + num_bytes - 1) > mh.upper:
        log_exec.error("deallocate: block outside of mem header!")

    if check:
        validate(ctx, mh)

    # no mem chunks?
    if mh.first == 0:
        # sanity check
        if mh.free != 0:
            log_exec.error("deallocate: internal error: first=0 but free!=0!")

        # create new and only mem chunk in deallocated range
        mc = MemChunk(0, num_bytes, blk_addr)
        mc.write(ctx)
        log_exec.debug("single: %s", mc)
        mh.first = blk_addr
    else:
        # find chunk right before/after the returned block
        mc_last = None
        mc = mh.read_first(ctx)
        log_exec.debug("read first: %s", mc)
        while mc and mc.addr < blk_addr:
            mc_last = mc
            mc = mc.read_next(ctx)
            if mc is not None:
                log_exec.debug("read next: %s", mc)

        # now we have either a mc_last and/or mc chunk
        # check if we can merge with one or both
        end_addr = blk_addr + num_bytes
        mc_merge = True if mc is not None and end_addr == mc.addr else False
        mc_last_merge = (
            True
            if mc_last is not None and mc_last.addr + mc_last.bytes == blk_addr
            else False
        )
        log_exec.debug("merge: mc_last=%s, mc=%s", mc_last_merge, mc_merge)

        # we merge with both last and current one -> grow mc_last, remove mc
        if mc_merge and mc_last_merge:
            mc_last.bytes += num_bytes + mc.bytes
            mc_last.next = mc.next
            mc_last.write(ctx)
            log_exec.debug("both: %s", mc_last)
        # we merge with last only
        elif mc_last_merge:
            mc_last.bytes += num_bytes
            mc_last.write(ctx)
            log_exec.debug("grow last: %s", mc_last)
        # we merge with current only -> move chunk to begin of blk_addr
        elif mc_merge:
            mc.addr = blk_addr
            mc.bytes += num_bytes
            mc.write(ctx)
            if mc_last:
                mc_last.next = blk_addr
                mc_last.write(ctx)
            else:
                # update header
                mh.first = mc.addr
            log_exec.debug("grow cur: %s", mc)
        # no merging possible -> create a new chunk between last and cur
        else:
            next_addr = mc.addr if mc is not None else 0
            mc_new = MemChunk(next_addr, num_bytes, blk_addr)
            mc_new.write(ctx)
            if mc_last:
                mc_last.next = mc_new.addr
                mc_last.write(ctx)
                log_exec.debug("new after: %s", mc_new)
            else:
                mh.first = mc_new.addr
                # mh is written below
                log_exec.debug("new front: %s", mc_new)

    # update header
    mh.free += num_bytes
    mh.write(ctx)
    log_exec.debug("done: %s", mh)

    if check:
        validate(ctx, mh)
