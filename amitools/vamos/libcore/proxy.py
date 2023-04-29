from amitools.vamos.machine.regs import REG_D0, REG_D1


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
            # ensure that all positional args are given
            assert len(args) == len(arg_regs)

            # fill registers with arg values
            for reg, val in zip(arg_regs, args):
                self.ctx.cpu.w_reg(reg, val)

            # shall we return d1 as well?
            ret_d1 = kwargs.pop("ret_d1", False)

            # perform call at stub
            stub_method(**kwargs)

            # prepare return value
            d0 = self.ctx.cpu.r_reg(REG_D0)
            if ret_d1:
                d1 = self.ctx.cpu.r_reg(REG_D1)
                return (d0, d1)
            else:
                return d0

        return stub_call

    def _gen_lib_call(self, arg_regs, bias, name=None):
        def lib_call(self, *args, **kwargs):
            # ensure that all positional args are given
            assert len(args) == len(arg_regs)

            reg_map = {}
            for reg, val in zip(arg_regs, args):
                reg_map[reg] = val

            ret_regs = [REG_D0]
            # shall we return d1 as well?
            ret_d1 = kwargs.pop("ret_d1", False)
            if ret_d1:
                ret_regs.append(REG_D1)

            jump_addr = self.base_addr - bias

            # perform native run
            res = self.ctx.machine.run(
                jump_addr,
                sp=self.run_sp,
                set_regs=reg_map,
                get_regs=ret_regs,
                name=name,
            )

            if ret_d1:
                return res.regs[REG_D0], res.regs[REG_D1]
            else:
                return res.regs[REG_D0]

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
