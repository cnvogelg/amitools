from .range import LabelRange


class LabelSegment(LabelRange):
    def __init__(self, name, addr, size, segment):
        LabelRange.__init__(self, name, addr, size)
        self.segment = segment
