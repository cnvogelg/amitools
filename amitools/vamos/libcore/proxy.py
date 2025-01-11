from amitools.vamos.machine import Code, REG_D0, REG_D1


class LibProxy:
    """A lib proxy offers the functions of a library as descibed in
       a fd file.

    With a proxy you can call library functions directly via Python.
    A native library is called via CPU emulation while a Python library
    is called directly.
    """

    def __init__(self, ctx, base_addr=None, run_sp=None):
        self.ctx = ctx
        self.base_addr = base_addr
        self.run_sp = run_sp


class LibProxyRegs:
    def __init__(self, ctx, args, arg_regs, kwargs):
        assert len(args) == len(arg_regs)
        self.ctx = ctx
        self.args = args
        self.arg_regs = arg_regs
        # shall we return d1 as well?
        self.ret_d1 = kwargs.pop("ret_d1", False)
        self.kw_args = kwargs
        # auto strings
        self.auto_strings = []

    def input_reg_map(self):
        reg_map = {}
        for reg, val in zip(self.arg_regs, self.args):
            # auto convert strings
            if val is None:
                val = 0
            elif isinstance(val, int):
                pass
            elif isinstance(val, str):
                str_mem = self.ctx.alloc.alloc_cstr(val, label="reg_auto_str")
                val = str_mem.addr
                self.auto_strings.append(str_mem)
            # complex object? try to get its in memory address via "get_addr"
            else:
                # has 'addr'?
                get_addr = getattr(val, "get_addr", None)
                if get_addr is not None:
                    val = get_addr()
                else:
                    raise ValueError(
                        f"Invalid argument for proxy call reg={reg} val={val}"
                    )

            reg_map[reg] = val
        return reg_map

    def output_reg_list(self):
        regs = [REG_D0]
        if self.ret_d1:
            regs.append(REG_D1)
        return regs

    def return_d1(self):
        return self.ret_d1

    def cleanup(self):
        for mem in self.auto_strings:
            self.ctx.alloc.free_cstr(mem)


class LibProxyGen:
    """Generate a new type derived from LibProxy holding all functions"""

    def _gen_arg_regs(self, func_def):
        arg_regs = []
        fd_args = func_def.get_args()
        if fd_args:
            for arg_name, arg_reg in fd_args:
                reg_num = int(arg_reg[1])
                if arg_reg[0] == "a":
                    reg_num += 8
                arg_regs.append(reg_num)
        return arg_regs

    def _gen_stub_call(self, arg_regs, stub_method):
        def stub_call(self, *args, **kwargs):
            """proxy function to call lib stub directly"""
            regs = LibProxyRegs(self.ctx, args, arg_regs, kwargs)

            # fill registers with arg values
            reg_map = regs.input_reg_map()
            for reg, val in reg_map.items():
                self.ctx.cpu.w_reg(reg, val)

            # perform call at stub
            stub_method(**kwargs)

            # clean up auto strings
            regs.cleanup()

            # prepare return value
            d0 = self.ctx.cpu.r_reg(REG_D0)
            if regs.return_d1():
                d1 = self.ctx.cpu.r_reg(REG_D1)
                return (d0, d1)
            else:
                return d0

        return stub_call

    def _gen_lib_call(self, arg_regs, bias, name=None):
        def lib_call(self, *args, **kwargs):
            # ensure that all positional args are given
            regs = LibProxyRegs(self.ctx, args, arg_regs, kwargs)

            # get input/output reg map/list
            reg_map = regs.input_reg_map()
            ret_regs = regs.output_reg_list()

            jump_addr = self.base_addr - bias

            # perform native run
            code = Code(jump_addr, self.run_sp, reg_map, ret_regs)
            rs = self.ctx.runner(code, name=name)

            # cleanup regs
            regs.cleanup()

            if regs.return_d1():
                return rs.regs[REG_D0], rs.regs[REG_D1]
            else:
                return rs.regs[REG_D0]

        return lib_call

    def gen_proxy_for_stub(self, proxy_name, lib_fd, stub):
        method_dict = {}
        for func_def in lib_fd.get_funcs():
            # prepare reg arg list
            arg_regs = self._gen_arg_regs(func_def)
            func_name = func_def.get_name()

            # lookup func in stub
            stub_method = getattr(stub, func_name, None)
            if stub_method:
                proxy_call = self._gen_stub_call(arg_regs, stub_method)
                method_dict[func_name] = proxy_call

        # create new type
        return type(proxy_name, (LibProxy,), method_dict)

    def gen_proxy_for_libcall(self, proxy_name, lib_fd):
        method_dict = {}
        for func_def in lib_fd.get_funcs():
            # prepare reg arg list
            arg_regs = self._gen_arg_regs(func_def)
            func_name = func_def.get_name()
            func_bias = func_def.get_bias()

            # lookup func in stub
            lib_call = self._gen_lib_call(arg_regs, func_bias, name=func_name)
            method_dict[func_name] = lib_call

        # create new type
        return type(proxy_name, (LibProxy,), method_dict)
