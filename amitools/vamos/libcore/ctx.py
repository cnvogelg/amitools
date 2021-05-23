class LibCtx(object):
    """the default context a library receives"""

    def __init__(self, machine):
        self.machine = machine
        self.cpu = machine.get_cpu()
        self.mem = machine.get_mem()
        # will be set on creation
        self.vlib = None

    def __str__(self):
        return "[LibCtx:cpu=%s,mem=%s]" % (self.cpu, self.mem)
