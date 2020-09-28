import logging
from amitools.vamos.log import *


class LabelManager:
    def __init__(self):
        self.first = None
        self.last = None

    # This is now all done manually with doubly linked
    # lists. The reason for this is that the python built-in
    # lists are ill-performing as the list grows larger,
    # and this is a heavy-duty class.
    def add_label(self, range):
        assert range.next == None
        assert range.prev == None
        if self.last == None:
            assert self.first == None
            self.last = range
            self.first = range
        else:
            self.last.next = range
            range.prev = self.last
            self.last = range

    def remove_label(self, range):
        if range.prev != None:
            range.prev.next = range.next
        if range.next != None:
            range.next.prev = range.prev
        if self.last == range:
            self.last = range.prev
        if self.first == range:
            self.first = range.next
        range.next = None
        range.prev = None

    def delete_labels_within(self, addr, size):
        # try to find compatible: release all labels within the given range
        # this is necessary because the label could be part of a puddle
        # that is released in one go.
        r = self.first
        while r != None:
            if r.addr >= addr and r.addr + r.size <= addr + size:
                s = r.next
                self.remove_label(r)
                r = s
            else:
                r = r.next

    def get_all_labels(self):
        ranges = []
        r = self.first
        while r != None:
            ranges.append(r)
            r = r.next
        return ranges

    def dump(self):
        r = self.first
        while r != None:
            print(r)
            r = r.next

    # This is called quite often and hence
    # a bit speed critical. It finds the
    # range within which the given address
    # lies.
    def get_label(self, addr):
        r = self.first
        while r != None:
            if r.addr <= addr and addr < r.end:
                return r
            r = r.next
        return None

    def get_intersecting_labels(self, addr, size):
        result = []
        r = self.first
        while r != None:
            if r.does_intersect(addr, size):
                result.append(r)
            r = r.next
        return result

    def get_label_offset(self, addr):
        r = self.get_label(addr)
        if r == None:
            return (None, 0)
        else:
            off = addr - r.addr
            return (r, off)
