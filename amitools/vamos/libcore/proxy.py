from typing import get_type_hints

from amitools.vamos.machine import Code, REG_D0, REG_D1
from amitools.vamos.libtypes import TagList


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
    def __init__(self, ctx, args, arg_regs, kwargs, stub_method=None):
        assert len(args) == len(arg_regs)
        self.ctx = ctx
        self.args = args
        self.arg_regs = arg_regs
        self.stub_method = stub_method
        # shall we return d1 as well?
        self.ret_d1 = kwargs.pop("ret_d1", False)
        # shall we wrap the return value into a type
        self.wrap_res = kwargs.pop("wrap_res", None)
        self.kw_args = kwargs
        # auto strings
        self.auto_strings = []
        self.auto_tag_lists = []

    def input_reg_map(self):
        reg_map = {}
        for reg, val in zip(self.arg_regs, self.args):
            reg_map[reg] = self._map_value(val)
        return reg_map

    def _map_value(self, val):
        if val is None:
            val = 0
        elif isinstance(val, int):
            # auto convert to unsigend
            if val < 0:
                val &= 0xFFFFFFFF
        # auto convert strings
        elif isinstance(val, str):
            str_mem = self.ctx.alloc.alloc_cstr(val, label="reg_auto_str")
            val = str_mem.addr
            self.auto_strings.append(str_mem)
        # auto convert tag list: [(tag, data), (tag2, data2), ...]
        elif isinstance(val, list):
            map_list = self._map_tag_list(val)
            tag_list = TagList.alloc(self.ctx.alloc, *map_list)
            self.auto_tag_lists.append(tag_list)
            val = tag_list.get_addr()
        # complex object? try to get its in memory address via "get_addr"
        else:
            # has 'addr'?
            get_addr = getattr(val, "get_addr", None)
            if get_addr is not None:
                val = get_addr()
            else:
                raise ValueError(f"Invalid argument for proxy call reg={reg} val={val}")
        return val

    def _map_tag_list(self, tag_list):
        result = []
        for tag, data in tag_list:
            val = self._map_value(data)
            result.append((tag, val))
        return result

    def output_reg_list(self):
        regs = [REG_D0]
        if self.ret_d1:
            regs.append(REG_D1)
        return regs

    def return_d1(self):
        return self.ret_d1

    def wrap_result(self):
        # either use forced type in proxy call argument
        result_type = self.wrap_res
        # or use from type hint of stub method (if any)
        if not result_type and self.stub_method:
            hints = get_type_hints(self.stub_method)
            if hints and "return" in hints:
                result_type = hints["return"]
        return result_type

    def cleanup(self):
        for mem in self.auto_strings:
            self.ctx.alloc.free_cstr(mem)
        for tag_list in self.auto_tag_lists:
            tag_list.free()


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
            regs = LibProxyRegs(self.ctx, args, arg_regs, kwargs, stub_method)

            # fill registers with arg values
            # (lib call may depend on it)
            reg_map = regs.input_reg_map()
            for reg, val in reg_map.items():
                self.ctx.cpu.w_reg(reg, val)

            # perform call at stub
            res = stub_method(**kwargs)

            # clean up auto strings
            regs.cleanup()

            # if we have to wrap the result we could actually directly use
            # the returned value from the stub call.
            # just make sure its the same type
            result_type = regs.wrap_result()
            if result_type:
                assert res is None or type(res) is result_type
                return res
            else:
                # classic return value from d0/d1
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

            # warp result into type?
            d0 = rs.regs[REG_D0]
            result_type = regs.wrap_result()
            if result_type:
                # wrap into given type located at address d0
                return result_type(mem=self.ctx.mem, addr=d0)
            elif regs.return_d1():
                return d0, rs.regs[REG_D1]
            else:
                return d0

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
