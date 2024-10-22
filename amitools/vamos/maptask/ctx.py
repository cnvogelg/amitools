class TaskCtx:
    """the default environment a task will receive"""

    def __init__(self, machine, alloc):
        self.machine = machine
        self.alloc = alloc

    def __repr__(self):
        return "[TaskCtx:machine=%s,alloc=%s]" % (self.machine, self.alloc)
