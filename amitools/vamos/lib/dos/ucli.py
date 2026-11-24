"""Minimal ("micro") CLI construction for a DOS process.

A single binary only reads a handful of ``CLIStruct`` fields, but ``pr_CLI``
is a ``BPTR(CLIStruct)`` so the full layout is kept.  ``MicroCLI`` fills just
the fields a program actually needs: the standard streams, the
prompt/set-name/command-name string buffers and the command path chain.

Shell-only state is deliberately left out: ``ShellProcess`` builds on the same
allocator and adds the ``S:Vamos-Startup`` redirect of ``cli_CurrentInput``
on top.
"""

from amitools.vamos.libstructs.dos import CLIStruct, PathStruct
from amitools.vamos.log import log_proc


class MicroCLI:
    """a minimally initialised ``CLIStruct`` plus its string buffers.

    Exposes ``addr`` (the BPTR target of ``pr_CLI``) and ``free()``; the raw
    struct is available as ``cli`` for subclasses that need to tweak a field.
    """

    def __init__(self, ctx, input_fh, output_fh, bin_name, stack_size):
        self.ctx = ctx
        self.paths = []
        cli = ctx.alloc.alloc_astruct(CLIStruct, label=bin_name + "_CLI")
        self.cli = cli
        cli.cli_DefaultStack.val = stack_size // 4  # in longs
        cli.cli_FailLevel.val = 10
        # set input/output
        cli.cli_StandardInput.aptr = input_fh.b_addr << 2
        cli.cli_CurrentInput.aptr = input_fh.b_addr << 2
        cli.cli_StandardOutput.aptr = output_fh.b_addr << 2
        cli.cli_CurrentOutput.aptr = output_fh.b_addr << 2
        # alloc prompt/cmdname/cmdfile/setname
        self.prompt = ctx.alloc.alloc_memory(60, label="cli_Prompt")
        self.cmdname = ctx.alloc.alloc_memory(104, label="cli_CommandName")
        self.cmdfile = ctx.alloc.alloc_memory(40, label="cli_CommandFile")
        self.setname = ctx.alloc.alloc_memory(80, label="cli_SetName")
        cli.cli_Prompt.aptr = self.prompt.addr
        cli.cli_CommandName.aptr = self.cmdname.addr
        cli.cli_CommandFile.aptr = self.cmdfile.addr
        cli.cli_SetName.aptr = self.setname.addr
        # set default prompt
        ctx.mem.w_bstr(self.prompt.addr, "%N.%S> ")
        ctx.mem.w_bstr(self.setname.addr, "SYS:")
        ctx.mem.w_bstr(self.cmdname.addr, bin_name)
        log_proc.info(cli)
        # Create the path
        cmd_dir_addr = cli.cli_CommandDir.aptr
        for p in ctx.path_mgr.get_cmd_paths():
            if p != "C:" and p != "c:":
                lock = ctx.dos_lib.lock_mgr.create_lock(None, p, False)
                if lock != None:
                    path = ctx.alloc.alloc_astruct(PathStruct, label="Path(%s)" % p)
                    path.path_Lock.aptr = lock.mem.addr
                    path.path_Next.aptr = cmd_dir_addr
                    cmd_dir_addr = path.addr
                    cli.cli_CommandDir.aptr = cmd_dir_addr
                    self.paths.append((path, lock))
                else:
                    log_proc.warning("Path %s does not exist, expect problems!", p)

    @property
    def addr(self):
        return self.cli.addr

    def free(self):
        ctx = self.ctx
        ctx.alloc.free_memory(self.prompt)
        ctx.alloc.free_memory(self.cmdname)
        ctx.alloc.free_memory(self.setname)
        ctx.alloc.free_memory(self.cmdfile)
        self.cli.free()
        # free path
        for path, lock in self.paths:
            path.free()
            ctx.dos_lib.lock_mgr.release_lock(lock)
