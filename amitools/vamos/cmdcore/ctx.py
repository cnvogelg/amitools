import sys


class CommandStream:
    """A small write-only output stream for a command.

    Output is routed through an Amiga DOS file handle when one is available
    (so it shows up on the emulated console and is captured like any other
    program output). Otherwise it falls back to a host stream, which lets the
    same command code run inside a bare unit test machine.
    """

    def __init__(self, dos_lib=None, file_handle=None, alloc=None, host_stream=None):
        self.dos_lib = dos_lib
        self.file_handle = file_handle
        self.alloc = alloc
        self.host_stream = host_stream

    def _write_dos(self, data):
        # place the bytes in Amiga memory and hand the buffer to dos.Write()
        mem_obj = self.alloc.alloc_memory(len(data))
        try:
            self.alloc.get_mem().w_block(mem_obj.addr, data)
            return self.dos_lib.Write(self.file_handle, mem_obj.addr, len(data))
        finally:
            self.alloc.free_memory(mem_obj)

    def write(self, text):
        if not isinstance(text, str):
            text = str(text)
        data = text.encode("latin-1", "replace")
        if self.dos_lib is not None and self.file_handle and self.alloc is not None:
            self._write_dos(data)
        else:
            stream = self.host_stream if self.host_stream is not None else sys.stdout
            stream.write(text)
        return len(data)

    def writeln(self, text=""):
        return self.write(text + "\n")

    def flush(self):
        if self.dos_lib is None:
            stream = self.host_stream if self.host_stream is not None else sys.stdout
            stream.flush()


class CommandContext:
    """The object passed to a command's ``main`` function.

    It exposes the ``exec`` and ``dos`` library proxies plus the low level
    machine handles and the ``stdout``/``stderr`` streams. The proxies are
    optional so a command can also run in a bare machine (unit tests).
    """

    def __init__(
        self,
        machine,
        alloc,
        runner,
        cmd=None,
        exec_lib=None,
        dos_lib=None,
        out_fh=None,
        err_fh=None,
    ):
        self.machine = machine
        self.mem = machine.get_mem() if machine is not None else None
        self.alloc = alloc
        self.runner = runner
        self.exec = exec_lib
        self.dos = dos_lib
        self.name = cmd.name if cmd is not None else None
        self.stdout = CommandStream(dos_lib, out_fh, alloc, sys.stdout)
        # stderr falls back to the output handle when no separate error
        # handle exists (AmigaDOS normally has a single console)
        self.stderr = CommandStream(dos_lib, err_fh or out_fh, alloc, sys.stderr)

    def print(self, *args):
        self.stdout.writeln(" ".join(str(a) for a in args))
