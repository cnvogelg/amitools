class MockTraps(object):
    """mock for the traps API"""

    def __init__(self, max_traps=4096):
        self.max_traps = max_traps
        self.traps = {}
        self.tids = []

    def setup(self, py_func, auto_rts=False, one_shot=False):
        """setup trap and return trap id"""
        # too many traps
        if len(self.traps) == self.max_traps:
            return -1
        # find new tid
        tid = 0
        while tid in self.tids:
            tid += 1
        self.tids.append(tid)
        self.traps[tid] = (py_func, auto_rts, one_shot)
        return tid

    def free(self, tid):
        """free an allocated trap"""
        if tid not in self.tids:
            raise ValueError("invalid tid to free!")
        self.tids.remove(tid)
        del self.traps[tid]

    # mock API

    def get_num_traps(self):
        return len(self.tids)

    def get_func(self, tid):
        return self.traps[tid][0]

    def is_auto_rts(self, tid):
        return self.traps[tid][1]

    def is_one_shot(self, tid):
        return self.traps[tid][2]

    def trigger(self, tid, pc=0):
        # mask opcode
        tid = tid & 0xFFF
        t = self.traps[tid]
        # call py function with (op, pc)
        op = 0xA000 | tid
        func = t[0]
        func(op, pc)
        # is one shot?
        one_shot = t[2]
        if one_shot:
            self.free(tid)
