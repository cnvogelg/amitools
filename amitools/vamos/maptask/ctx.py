class TaskCtx:
    """the default environment a task will receive"""

    def __init__(self, machine, alloc, proxy_mgr=None):
        self.machine = machine
        self.alloc = alloc
        self.proxy_mgr = proxy_mgr

    def __repr__(self):
        return "[TaskCtx:machine=%s,alloc=%s]" % (self.machine, self.alloc)
