from amitools.vamos.libstructs import LibraryStruct, NodeType
from amitools.vamos.libtypes import Library
from amitools.fd import read_lib_fd, generate_fd
from .vlib import VLib
from .stub import LibStubGen
from .patch import LibPatcherMultiTrap
from .impl import LibImplScanner


class LibCreator(object):
    """create a vamos internal libs"""

    def __init__(
        self,
        alloc,
        traps,
        fd_dir=None,
        log_missing=None,
        log_valid=None,
        lib_profiler=None,
    ):
        self.alloc = alloc
        self.traps = traps
        # options
        self.fd_dir = fd_dir
        self.profiler = lib_profiler
        self.stub_gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)

    def _create_library(self, info, is_dev, fd):
        if is_dev:
            ltype = NodeType.NT_DEVICE
        else:
            ltype = NodeType.NT_LIBRARY
        name = info.get_name()
        id_str = info.get_id_string()
        neg_size = info.get_neg_size()
        pos_size = info.get_pos_size()
        library = Library.alloc(
            self.alloc,
            name=name,
            id_string=id_str,
            neg_size=neg_size,
            pos_size=pos_size,
            fd=fd,
        )
        version = info.get_version()
        revision = info.get_revision()
        library.new_lib(version=version, revision=revision, type=ltype)
        return library

    def _generate_fake_fd(self, name, lib_cfg):
        if lib_cfg:
            num_calls = lib_cfg.num_fake_funcs
        else:
            num_calls = 0
        return generate_fd(name, num_calls)

    def get_profiler(self):
        return self.profiler

    def create_lib(self, info, ctx, impl=None, lib_cfg=None, check=False):
        name = info.get_name()
        if name.endswith(".device"):
            is_dev = True
        elif name.endswith(".library"):
            is_dev = False
        else:
            raise ValueError("create_lib: %s is neither lib nor dev!" % name)
        # get fd: either read from fd or fake one
        fd = read_lib_fd(name, self.fd_dir)
        if fd is None:
            fd = self._generate_fake_fd(name, lib_cfg)
        # if impl is available scan it
        scan = None
        if impl:
            scanner = LibImplScanner()
            if check:
                scan = scanner.scan_checked(name, impl, fd, True)
            else:
                scan = scanner.scan(name, impl, fd, True)
        # add profile?
        if self.profiler:
            # get some impl information
            if scan:
                impl_funcs = scan.get_all_funcs()
            else:
                impl_funcs = None
            profile = self.profiler.create_profile(name, fd, impl_funcs)
        else:
            profile = None
        # create stub
        if scan is None:
            stub = self.stub_gen.gen_fake_stub(name, fd, ctx, profile)
            struct = LibraryStruct
        else:
            stub = self.stub_gen.gen_stub(scan, ctx, profile)
            struct = impl.get_struct_def()
        # adjust info pos/neg size
        if info.pos_size == 0:
            info.pos_size = struct.get_size()
        if info.neg_size == 0:
            info.neg_size = fd.get_neg_size()
        # allocate and init lib
        library = self._create_library(info, is_dev, fd)
        addr = library.get_addr()
        # patcher
        patcher = LibPatcherMultiTrap(self.alloc, self.traps, stub)
        patcher.patch_jump_table(addr)
        # fix lib sum
        library.update_sum()
        # create vamos lib and combine all pieces
        vlib = VLib(
            library, info, struct, fd, impl, stub, ctx, patcher, profile, is_dev
        )
        return vlib
