from types import MethodType
from typing import get_type_hints
import time
import traceback

from amitools.vamos.astructs import ScalarType, PointerType
from amitools.vamos.machine.regs import REG_D0, REG_D1, REG_A7


class LibStub(object):
    """a lib stub is a frontend object instance that wraps all calls into
    a library implementation.

    It is suitable for binding these functions to traps of the machine
    emulation.

    A wrapped call return value processing or optional profiling features.
    """

    def __init__(self, name, fd, impl=None, profile=None):
        """create a stub for a given implementation and
        associated fd description"""
        self.name = name
        self.impl = impl
        self.fd = fd
        # a table with all methods mapped via index
        self.func_tab = [None] * fd.get_num_indices()
        # (optional) attach profile object
        self.profile = profile
        self.log_exc = None

    def get_func_tab(self):
        return self.func_tab

    def _get_callee_pc(self, ctx):
        """a call stub log helper to extract the callee's pc"""
        sp = ctx.cpu.r_reg(REG_A7)
        return ctx.mem.r32(sp)

    def _gen_arg_dump(self, args, ctx):
        """a call stub helper to dump the registers of a call"""
        if args == None or len(args) == 0:
            return ""
        result = []
        for a in args:
            name = a[0]
            reg = a[1]
            reg_num = int(reg[1])
            if reg[0] == "a":
                reg_num += 8
            val = ctx.cpu.r_reg(reg_num)
            result.append("%s[%s]=%08x" % (name, reg, val))
        return ", ".join(result)

    def _handle_exc(self):
        """default exception handler"""
        traceback.print_exc()
        raise


class LibStubGen(object):
    """the lib stub generator scans a lib impl and creates stubs for all
    methods found there"""

    def __init__(self, log_missing=None, log_valid=None, ignore_invalid=True):
        self.log_missing = log_missing
        self.log_valid = log_valid
        self.ignore_invalid = ignore_invalid

    def gen_fake_stub(self, name, fd, ctx, profile=None):
        """a fake stub exists without an implementation and only contains
        "missing" functions
        """
        # create stub object
        stub = LibStub(name, fd, profile=profile)

        # iterate all functions in fd
        for fd_func in fd.get_funcs():
            stub_func = self._wrap_missing_func(stub, fd_func, ctx, profile)
            self._set_method(fd_func, stub, stub_func)

        # fill holes in func table
        self._fill_hole_funcs(stub, ctx)

        return stub

    def gen_stub(self, impl_scan, ctx, profile=None):
        # create stub object
        name = impl_scan.get_name()
        fd = impl_scan.get_fd()
        impl = impl_scan.get_impl()
        stub = LibStub(name, fd, impl, profile)

        # generate valid funcs
        valid_funcs = list(impl_scan.get_valid_funcs().values())
        for impl_func in valid_funcs:
            fd_func = impl_func.fd_func
            stub_func = self._wrap_func(stub, impl_func, ctx, profile)
            self._set_method(fd_func, stub, stub_func)

        # generate missing funcs
        missing_funcs = list(impl_scan.get_missing_funcs().values())
        for impl_func in missing_funcs:
            fd_func = impl_func.fd_func
            stub_func = self._wrap_missing_func(stub, fd_func, ctx, profile)
            self._set_method(fd_func, stub, stub_func)

        # fill holes in func table
        self._fill_hole_funcs(stub, ctx)

        # return final stub
        return stub

    def _set_method(self, fd_func, stub, stub_func):
        # bind method to stub instance
        stub_method = MethodType(stub_func, stub)
        # store in stub
        setattr(stub, fd_func.get_name(), stub_method)
        # add to func tab
        index = fd_func.get_index()
        stub.func_tab[index] = stub_method

    def _fill_hole_funcs(self, stub, ctx):
        """fill in entries in jump table that are skipped by fd file"""
        for idx, func in enumerate(stub.func_tab):
            if not func:
                func = self._gen_hole_func(stub, idx, ctx)
                name = "_hole_" + str(idx)
                stub_method = MethodType(func, stub)
                setattr(stub, name, stub_method)
                stub.func_tab[idx] = stub_method

    def _gen_hole_func(self, stub, idx, ctx):
        """create a stub func for an empty slot in the jump table"""
        bias = idx * 6 + 6
        log = self.log_missing
        if log is None:
            # without tracing
            def stub_func(this, *args, **kwargs):
                # return d0=0
                ctx.cpu.w_reg(REG_D0, 0)
                return 0

        else:
            # with tracing
            def stub_func(this, *args, **kwargs):
                callee_pc = this._get_callee_pc(ctx)
                call_info = "(%s) %4d UNKNOWN(#%d) from PC=%06x" % (
                    stub.name,
                    bias,
                    idx,
                    callee_pc,
                )
                log.warning("? CALL: %s -> d0=0 (default)", call_info)
                ctx.cpu.w_reg(REG_D0, 0)
                return 0

        return stub_func

    def _wrap_missing_func(self, stub, fd_func, ctx, profile):
        """create a stub func for a missing function in impl
        returns an unbound method for the stub instance
        """
        log = self.log_missing
        if log is None:
            # without tracing
            def stub_func(this, *args, **kwargs):
                # return d0=0
                ctx.cpu.w_reg(REG_D0, 0)
                return 0

        else:
            name = fd_func.get_name()
            func_args = fd_func.get_args()
            bias = fd_func.get_bias()
            # with tracing

            def stub_func(this, *args, **kwargs):
                callee_pc = this._get_callee_pc(ctx)
                call_info = "(%s) %4d %s( %s ) from PC=%06x" % (
                    stub.name,
                    bias,
                    name,
                    this._gen_arg_dump(func_args, ctx),
                    callee_pc,
                )
                log.warning("? CALL: %s -> d0=0 (default)", call_info)
                ctx.cpu.w_reg(REG_D0, 0)
                return 0

        func = stub_func

        # wrap profiling?
        if profile:
            index = fd_func.get_index()
            prof = profile.get_func_by_index(index)

            def profile_func(this, *args, **kwargs):
                res = stub_func(this, *args, **kwargs)
                prof.count(0.0)
                return res

            func = profile_func

        # return created func
        return func

    def _set_result(self, ctx, result_value, result_type):
        # if no result type is given then standard return rules apply
        # either single value for d0 or tuple/list with (d0, d1)
        if result_type is None or result_type is int:
            if result_value is None:
                # VOID functions return None
                # we do not alter any regs in this case
                pass
            elif type(result_value) in (list, tuple):
                ctx.cpu.w_reg(REG_D0, result_value[0] & 0xFFFFFFFF)
                ctx.cpu.w_reg(REG_D1, result_value[1] & 0xFFFFFFFF)
            elif type(result_value) in (int, bool):
                ctx.cpu.w_reg(REG_D0, int(result_value) & 0xFFFFFFFF)
            else:
                raise ValueError(
                    f"Unknown result value '{result_value}' for type {result_type}"
                )
        else:
            # if a return type is annotated then assume either
            # object with memory address or None
            if result_value is None:
                d0 = 0
            else:
                # make sure value and type match
                if not isinstance(result_value, result_type):
                    raise ValueError(
                        f"Invalid result value '{result_value}' for type {result_type}"
                    )
                # is type object? then use its addr
                get_addr = getattr(result_value, "get_addr", None)
                if get_addr:
                    d0 = get_addr()
                else:
                    raise ValueError(
                        f"Unknown result value '{result_value}' for type {result_type}"
                    )
            # write d0 of type
            ctx.cpu.w_reg(REG_D0, d0)

    def _get_result_str(self, res):
        """show result values"""
        if res is not None:
            if type(res) in (list, tuple):
                res_str = "d0=%08x, d1=%08x" % tuple(map(int, res))
            elif type(res) in (int, bool):
                res_str = "d0=%08x" % int(res)
            else:
                # is type object? then use its addr
                get_addr = getattr(res, "get_addr", None)
                if get_addr:
                    addr = get_addr()
                    res_str = "d0=%08x (%s)" % (addr, res)
                else:
                    raise ValueError(
                        f"Invalid result value '{result_value}' for {result_type}"
                    )
        else:
            res_str = "n/a"
        return res_str

    def _gen_extra_args(self, ctx, extra_args):
        """generate the extra arguments passed to a lib method"""
        args = []

        for arg in extra_args:
            arg_val = ctx.cpu.r_reg(arg.reg)
            arg_type = arg.type
            # int: keep value
            if issubclass(arg_type, int):
                pass
            # bool: convert to int
            elif issubclass(arg_type, bool):
                arg_val = int(arg_val)
            # scalar values and pointers are bound to the register
            elif issubclass(arg_type, ScalarType) or issubclass(arg_type, PointerType):
                arg_val = arg_type(cpu=ctx.cpu, reg=arg.reg, mem=ctx.mem)
            # all other types are bound to the address in memory
            # (implicit APTR conversion)
            else:
                if arg_val != 0:
                    arg_val = arg_type(mem=ctx.mem, addr=arg_val)
                else:
                    # NULL object is none
                    arg_val = None

            args.append(arg_val)

        return args

    def _gen_base_func(self, method, ctx, result_type):
        """generate a function that calls the method with the ctx."""

        def base_func(this, *args, **kwargs):
            """the base function to call the impl,
            set return vals, and catch exceptions"""
            result_value = method(ctx)
            self._set_result(ctx, result_value, result_type)
            return result_value

        return base_func

    def _gen_base_extra_args_func(self, method, ctx, extra_args, result_type):
        """generate a function that fills arguments from registers."""

        def base_func(this, *args, **kwargs):
            """the base function to call the impl,
            set return vals, and catch exceptions"""

            args = self._gen_extra_args(ctx, extra_args)
            # call function
            result_value = method(ctx, *args)
            self._set_result(ctx, result_value, result_type)
            return result_value

        return base_func

    def _gen_log_func(self, stub, fd_func, base_func, ctx, log):
        """wrap the base function with logging."""
        name = fd_func.get_name()
        func_args = fd_func.get_args()
        bias = fd_func.get_bias()

        def log_func(this, *args, **kwargs):
            callee_pc = this._get_callee_pc(ctx)
            call_info = "(%s) %4d %s( %s ) from PC=%06x" % (
                stub.name,
                bias,
                name,
                this._gen_arg_dump(func_args, ctx),
                callee_pc,
            )
            log.info("{ CALL: %s" % call_info)
            res = base_func(this, *args, **kwargs)
            res_str = self._get_result_str(res)
            log.info("} CALL: -> %s" % res_str)
            return res

        return log_func

    def _gen_profile_func(self, fd_func, profile, func):
        """wrap profiling around func"""
        index = fd_func.get_index()
        prof = profile.get_func_by_index(index)

        def profile_func(this, *args, **kwargs):
            start = time.perf_counter()
            res = func(this, *args, **kwargs)
            end = time.perf_counter()
            delta = end - start
            prof.count(delta)
            return res

        return profile_func

    def _copy_return_type_hint(self, in_func, out_func):
        # get type hint
        hints = get_type_hints(in_func)

        # is a return type defined
        if hints and "return" in hints:
            return_type = hints["return"]
            # attach new return annotation
            ann = out_func.__annotations__
            if ann is None:
                ann = out_func.__annotations__ = {}
            ann["return"] = return_type

    def _wrap_func(self, stub, impl_func, ctx, profile):
        """create a stub func for a valid impl func
        returns an unbound method for the stub instaance
        """
        fd_func = impl_func.fd_func
        method = impl_func.method

        # do we need to read some registers into extra args?
        extra_args = impl_func.extra_args

        # is a result type given?
        result = impl_func.result
        if result:
            result_type = result.type
        else:
            result_type = None

        if extra_args:
            func = self._gen_base_extra_args_func(method, ctx, extra_args, result_type)
        else:
            func = self._gen_base_func(method, ctx, result_type)

        # wrap around logging method?
        log = self.log_valid
        if log:
            func = self._gen_log_func(stub, fd_func, func, ctx, log)

        # wrap profiling?
        if profile:
            func = self._gen_profile_func(fd_func, profile, func)

        # copy return hint from method to wrap func for later use in proxy
        self._copy_return_type_hint(method, func)

        return func
