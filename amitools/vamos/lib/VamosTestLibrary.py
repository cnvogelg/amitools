import code
import importlib

from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.error import *
from amitools.vamos.astructs import CSTR


class VamosTestLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        self.cnt = 0

    def finish_lib(self, ctx):
        self.cnt = None

    def open_lib(self, ctx, open_cnt):
        self.cnt = open_cnt

    def close_lib(self, ctx, open_cnt):
        self.cnt = open_cnt

    def get_version(self):
        return 23

    def get_cnt(self):
        return self.cnt

    def ignore_func(self):
        """a lower-case function that is ignored"""
        pass

    def InvalidFunc(self, ctx):
        """a test function that does not exist in the .fd file"""
        pass

    def PrintHello(self, ctx):
        print("VamosTest: PrintHello()")
        return 0

    def PrintString(self, ctx, txt: CSTR):
        print("VamosTest: PrintString('%s')" % txt.str)
        return 0

    def Add(self, ctx, a, b):
        """define input values directly as function arguments"""
        return a + b

    def Swap(self, ctx, a, b):
        """define input values directly as function arguments"""
        return b, a

    def RaiseError(self, ctx, txt_ptr: CSTR):
        txt = txt_ptr.str
        if txt == "RuntimeError":
            e = RuntimeError("VamosTest")
        elif txt == "VamosInternalError":
            e = VamosInternalError("VamosTest")
        elif txt == "InvalidMemoryAccessError":
            e = InvalidMemoryAccessError("R", 2, 0x200)
        else:
            print("VamosTest: Invalid Error:", txt)
            return
        print("VamosTest: raise", e.__class__.__name__)
        raise e

    def _ExecutePyUsage(self):
        print(
            """ExecutePy Usage:
-e '<eval_string>'      # return value in d0
-x '<exec_string>'      # return value in 'rc' var
-f '<exec_host_file>'   # return value in 'rc' var
-c '<exec_host_file>' '<func>  # call function 'func(ctx)' and return value
-i '<module>' '<func>'  # call function in module
"""
        )

    def ExecutePy(self, ctx, argc, argv):
        """execute python code in the current context"""
        # read args
        args = []
        for i in range(argc):
            ptr = ctx.mem.r32(argv)
            txt = ctx.mem.r_cstr(ptr)
            args.append(txt)
            argv += 4
        # local and global variables
        loc = {"rc": 0, "ctx": ctx}
        glob = globals()
        # mode of operation
        if argc == 0:
            # nor args - run interactive
            code.interact(banner="vamos REPL", exitmsg="back to vamos", local=loc)
            rc = loc["rc"]
        elif argc < 2:
            # invalid usage
            self._ExecutePyUsage()
            rc = 2
        else:
            op = args[0]
            val = args[1]
            if op == "-e":
                # eval string
                rc = eval(val, glob, loc)
            elif op == "-x":
                # exec string
                exec(val, glob, loc)
                rc = loc["rc"]
            elif op == "-f":
                # exec script file
                with open(val) as fh:
                    exec(fh.read(), glob, loc)
                rc = loc["rc"]
            elif op == "-c" and argc > 2:
                # exec function(ctx) in file
                func_name = args[2]
                with open(val) as fh:
                    exec(fh.read(), glob, loc)
                func = loc[func_name]
                rc = func(ctx)
            elif op == "-i" and argc > 2:
                func_name = args[2]
                mod = importlib.import_module(val)
                func = getattr(mod, func_name)
                rc = func(ctx)
            else:
                self._ExecutePyUsage()
                rc = 2
        # check return value
        if rc is None:
            rc = 0
        elif type(rc) is not int:
            print("ExecutePy: invalid return value:", rc)
            rc = 3
        # fetch return code
        return rc
