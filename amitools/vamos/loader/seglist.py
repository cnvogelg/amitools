from amitools.vamos.label import LabelRange, LabelSegment


class Segment:
    def __init__(self, seg_list):
        self.seg_list = seg_list
        self.addr = seg_list.addr + 4
        self.size = seg_list.get_size() - 8

    def __repr__(self):
        return "[Segment:addr=%06x,size=%06x]" % (self.addr, self.size)

    def get_addr(self):
        return self.addr

    def get_size(self):
        return self.size

    def get_end(self):
        return self.addr + self.size

    def get_next(self):
        baddr = self.seg_list.get_next_baddr()
        if baddr != 0:
            seg_list = SegList(self.seg_list.alloc, baddr)
            return Segment(seg_list)


class SegmentIter:
    def __init__(self, seg):
        self.seg = seg

    def __iter__(self):
        return self

    def __next__(self):
        seg = self.seg
        if seg is None:
            raise StopIteration
        self.seg = self.seg.get_next()
        return seg


class SegList:
    def __init__(self, alloc, baddr):
        self.alloc = alloc
        self.mem = alloc.get_mem()
        self.baddr = baddr
        self.addr = baddr << 2

    def __repr__(self):
        return "[SegList:baddr=%06x,addr=%06x,size=%06x]" % (
            self.baddr,
            self.addr,
            self.get_size(),
        )

    def __iter__(self):
        return SegmentIter(self.get_segment())

    def get_baddr(self):
        return self.baddr

    def get_size(self):
        return self.mem.r32(self.addr - 4)

    def get_next_baddr(self):
        return self.mem.r32(self.addr)

    def get_segment(self):
        return Segment(self)

    def get_all_segments(self):
        res = []
        seg = self.get_segment()
        while seg:
            res.append(seg)
            seg = seg.get_next()
        return res

    def get_all_addrs(self):
        res = []
        seg = self.get_segment()
        while seg:
            res.append(seg.get_addr())
            seg = seg.get_next()
        return res

    def get_all_sizes(self):
        res = []
        seg = self.get_segment()
        while seg:
            res.append(seg.get_size())
            seg = seg.get_next()
        return res

    @staticmethod
    def alloc(alloc, sizes, labels=None, bin_img_segs=None):
        mem = alloc.get_mem()
        last_addr = 0
        first_addr = 0
        for i in range(len(sizes)):
            size = sizes[i]
            size = (size + 3) & ~3
            seg_size = size + 8  # add next segment pointer and size field

            # alloc mem
            seg_mem = alloc.alloc_memory(seg_size)
            seg_addr = seg_mem.addr

            # create label
            if alloc.label_mgr and labels:
                name = labels[i]
                # add a segment label if bin img segment available
                if bin_img_segs:
                    bin_img_seg = bin_img_segs[i]
                    label = LabelSegment(name, seg_addr, seg_size, bin_img_seg)
                else:
                    label = LabelRange(name, seg_addr, seg_size)
                seg_mem.label = label
                alloc.label_mgr.add_label(label)

            # store size
            mem.w32(seg_addr, seg_size)
            # link last to me
            if last_addr != 0:
                mem.w32(last_addr + 4, (seg_addr + 4) >> 2)
            last_addr = seg_addr
            if i == 0:
                first_addr = seg_addr

        # terminate link
        mem.w32(seg_addr + 4, 0)

        # seglist start baddr
        baddr = (first_addr + 4) >> 2
        return SegList(alloc, baddr)

    def free(self):
        addr = self.addr
        while addr != 0:
            next_baddr = self.mem.r32(addr)
            mem_addr = addr - 4
            mem_obj = self.alloc.get_memory(mem_addr)
            assert mem_obj
            self.alloc.free_memory(mem_obj)
            addr = next_baddr << 2
