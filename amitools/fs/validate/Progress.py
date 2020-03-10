import sys


class Progress:
    def __init__(self):
        self.num = 0
        self.msg = None

    def begin(self, msg):
        self.num = 0
        self.msg = msg

    def end(self):
        pass

    def add(self):
        self.num += 1
