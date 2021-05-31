from amitools.vamos.libtypes import Resident, Library
from amitools.vamos.libstructs import ResidentFlags, LibFlags, NodeType
from .makelib import MakeLib
from .libfuncs import LibFuncs


class InitRes(object):
    def __init__(self, machine, alloc):
        self.machine = machine
        self.alloc = alloc
        self.mem = machine.get_mem()

    def init_resident(
        self, resident_addr, seg_list_baddr, label_name=None, run_sp=None, exec_lib=None
    ):
        """Implement Exec's InitResident
        Returns lib_base, mem_obj or lib_base, 0 or 0, None
        """
        res = Resident(self.mem, resident_addr)
        if not res.is_valid():
            return 0, None

        if label_name is None:
            label_name = "%s_init" % res.name

        auto_init = res.flags.has_bits(ResidentFlags.RTF_AUTOINIT)
        if auto_init:
            ai = res.init.ref

            # create lib without calling init
            ml = MakeLib(self.machine, self.alloc)
            lib_base, mem_obj = ml.make_library(
                ai.functions.aptr,
                ai.init_struct.aptr,
                0,
                ai.pos_size.val,
                seg_list_baddr,
                label_name=label_name,
                run_sp=run_sp,
            )

            # fill lib
            lib = Library(self.mem, lib_base)
            flags = LibFlags.LIBF_CHANGED | LibFlags.LIBF_SUMUSED
            lib.new_lib(version=res.version, type=res.type.val, flags=flags)
            lib.name.aptr = res.name.aptr
            lib.id_string.aptr = res.id_string.aptr

            # now call init
            if ai.init_func.aptr != 0:
                run_name = "InitResident:%s" % res.name.str
                lib_base = ml.run_init(
                    ai.init_func.aptr, lib_base, seg_list_baddr, run_name, run_sp
                )

            if lib_base == 0:
                return 0, None

            # add lib to exec list
            rtype = res.type.val
            if rtype == NodeType.NT_LIBRARY:
                lf = LibFuncs(self.machine, self.alloc)
                lf.add_library(lib_base, exec_lib)
            elif rtype == NodeType.NT_DEVICE:
                # TODO
                raise NotImplementedError("InitResource(NT_DEVICE)")
            elif rtype == NodeType.NT_RESOURCE:
                # TODO
                raise NotImplementedError("InitResident(NT_RESOURCE)")
            else:
                raise ValueError("InitResident: invalid type!")

        else:
            # no auto init, lib_base, or mem_obj
            lib_base = 0
            mem_obj = None
            # call init func
            init_func = res.init.aptr
            if init_func != 0:
                ml = MakeLib(self.machine, self.alloc)
                lib_base = ml.run_init(
                    init_func, lib_base, seg_list_baddr, label_name, run_sp
                )

        return lib_base, mem_obj
