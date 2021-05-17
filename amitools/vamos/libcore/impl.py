import inspect
import collections
from amitools.vamos.libstructs import LibraryStruct
from amitools.vamos.error import VamosInternalError
from amitools.vamos.machine import str_to_reg_map


class LibImpl(object):
    """base class for all Python-based library implementations"""

    def get_struct_def(self):
        """return the structure of your library pos_size"""
        return LibraryStruct

    def get_version(self):
        return 40

    def setup_lib(self, ctx, base_addr):
        pass

    def finish_lib(self, ctx):
        pass

    def open_lib(self, ctx, open_cnt):
        pass

    def close_lib(self, ctx, open_cnt):
        pass


LibImplFunc = collections.namedtuple(
    "LibImplFunc",
    ("name", "fd_func", "tag", "method", "extra_args"),
)


LibImplFuncArg = collections.namedtuple("LibImplFuncArg", ("name", "reg", "type"))


class LibImplScan(object):
    """scan result of a vamos library implementation

    it contains extracted function lists"""

    TAG_VALID = "valid"
    TAG_ERROR = "error"
    TAG_INVALID = "invalid"
    TAG_MISSING = "missing"

    def __init__(self, name, impl, fd):
        self.name = name
        self.impl = impl
        self.fd = fd
        self.all_funcs = {}
        self.valid_funcs = {}
        self.missing_funcs = {}
        self.invalid_funcs = {}
        self.error_funcs = {}

    def get_name(self):
        return self.name

    def get_impl(self):
        return self.impl

    def get_fd(self):
        return self.fd

    def get_valid_funcs(self):
        """return map: name -> LibImplFunc"""
        return self.valid_funcs

    def get_missing_funcs(self):
        """return map: name -> LibImplFunc"""
        return self.missing_funcs

    def get_invalid_funcs(self):
        """return map: name -> LibImplFunc"""
        return self.invalid_funcs

    def get_error_funcs(self):
        """return map: name -> LibImplFunc"""
        return self.error_funcs

    def get_all_funcs(self):
        """return map: name -> LibImplFunc"""
        return self.all_funcs

    def get_valid_func_names(self):
        return sorted(self.valid_funcs.keys())

    def get_missing_func_names(self):
        return sorted(self.missing_funcs.keys())

    def get_invalid_func_names(self):
        return sorted(self.invalid_funcs.keys())

    def get_error_func_names(self):
        return sorted(self.error_funcs.keys())

    def get_num_valid_funcs(self):
        return len(self.valid_funcs)

    def get_num_missing_funcs(self):
        return len(self.missing_funcs)

    def get_num_invalid_funcs(self):
        return len(self.invalid_funcs)

    def get_num_error_funcs(self):
        return len(self.error_funcs)

    def get_func_by_name(self, name):
        return self.all_funcs[name]


class LibImplScanner(object):
    """scan an implementation of a library for functions"""

    def scan(self, lib_name, impl, fd_lib, inc_std_funcs=False):
        """scan a library implementation and check if functions match the FD"""
        res = LibImplScan(lib_name, impl, fd_lib)
        found_names = []
        # scan methods of the impl class
        members = inspect.getmembers(impl, predicate=inspect.ismethod)
        for name, method in members:
            tag = None
            # is a func in the fd?
            if fd_lib.has_func(name):
                fd_func = fd_lib.get_func_by_name(name)
                impl_func = self._gen_impl_func(fd_func, method)
                res.all_funcs[name] = impl_func
                found_names.append(name)
                if impl_func.tag == LibImplScan.TAG_VALID:
                    res.valid_funcs[name] = impl_func
                else:
                    res.error_funcs[name] = impl_func
            # not a func name
            else:
                # if name is camel case then it is invalid
                if name[0].isupper():
                    impl_func = LibImplFunc(
                        name,
                        None,
                        LibImplScan.TAG_INVALID,
                        method,
                        None,
                    )
                    res.invalid_funcs[name] = impl_func
                    res.all_funcs[name] = impl_func
        # now check for missing functions
        funcs = fd_lib.get_funcs()
        if len(funcs) != len(found_names):
            for fd_func in funcs:
                # skip std functions
                if inc_std_funcs or not fd_func.is_std():
                    name = fd_func.get_name()
                    if name not in found_names:
                        impl_func = LibImplFunc(
                            name, fd_func, LibImplScan.TAG_MISSING, None, None
                        )
                        res.missing_funcs[name] = impl_func
                        res.all_funcs[name] = impl_func

        # return scan result
        return res

    def scan_checked(self, name, impl, fd, inc_std_funcs=False, ignore_invalid=False):
        res = self.scan(name, impl, fd, inc_std_funcs)
        # raise an error if impl is not valid
        num_invalid = res.get_num_invalid_funcs()
        num_error = res.get_num_error_funcs()
        if num_invalid > 0 and not ignore_invalid:
            names = res.get_invalid_func_names()
            txt = ",".join(names)
            raise VamosInternalError(
                "'%s' impl has %d invalid funcs: %s" % (name, num_invalid, txt)
            )
        if num_error > 0:
            names = res.get_error_func_names()
            txt = ",".join(names)
            raise VamosInternalError(
                "'%s' impl has %d error funcs: %s" % (name, num_error, txt)
            )

    def _gen_extra_args(self, more_args, fd_func, anno):
        """extract more args of func that are suitable to be mapped to regs"""
        extra_args = []
        fd_args = fd_func.get_args()
        num_fd_args = len(fd_args)
        if len(more_args) != num_fd_args:
            return None
        # make sure arg names match
        for i in range(num_fd_args):
            fd_arg_name = fd_args[i][0]
            impl_arg_name = more_args[i]
            # impl arg must have the fd arg as a prefix
            # if not impl_arg_name.startswith(fd_arg_name):
            #    return None
            # find CPU register
            reg_str = "REG_" + fd_args[i][1].upper()
            reg = str_to_reg_map[reg_str]
            # find type
            py_type = int
            if impl_arg_name in anno:
                py_type = anno[impl_arg_name]
            arg = LibImplFuncArg(fd_arg_name, reg, py_type)
            extra_args.append(arg)
        return extra_args

    def _gen_impl_func(self, fd_func, method):
        """describe the impl func"""
        # prepare impl_func
        func_name = fd_func.get_name()
        tag = LibImplScan.TAG_ERROR
        impl_func = LibImplFunc(func_name, fd_func, tag, method, None)
        # inspect method
        fas = inspect.getfullargspec(method)
        if fas.varargs is not None:
            return impl_func
        if fas.varkw is not None:
            return impl_func
        if fas.defaults is not None:
            return impl_func
        # args must begin with "self" and "ctx"
        num_args = len(fas.args)
        if num_args < 2:
            return impl_func
        if fas.args[:2] != ["self", "ctx"]:
            return impl_func
        # extra args? must be function arguments
        if num_args > 2:
            anno = fas.annotations
            extra_args = self._gen_extra_args(fas.args[2:], fd_func, anno)
            if not extra_args:
                return impl_func
        else:
            extra_args = None
        # impl_func is valid
        return LibImplFunc(
            func_name, fd_func, LibImplScan.TAG_VALID, method, extra_args
        )
