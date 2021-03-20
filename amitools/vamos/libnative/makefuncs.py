from amitools.vamos.machine.opcodes import op_jmp


class MakeFuncs(object):
    def __init__(self, mem):
        self.mem = mem

    def make_functions(self, lib_base_ptr, func_array_ptr, disp_base_ptr=0):
        """Exec's MakeFunctions() call

        returns table size in bytes
        """
        size = 0
        src_ptr = func_array_ptr
        dst_ptr = lib_base_ptr - 6
        if disp_base_ptr != 0:
            # word offset table
            while True:
                offset = self.mem.r16s(src_ptr)
                if offset == -1:
                    break
                addr = disp_base_ptr + offset
                self.mem.w16(dst_ptr, op_jmp)
                self.mem.w32(dst_ptr + 2, addr)
                size += 6
                src_ptr += 2
                dst_ptr -= 6
        else:
            # pointer table
            while True:
                addr = self.mem.r32(src_ptr)
                if addr == 0xFFFFFFFF:
                    break
                self.mem.w16(dst_ptr, op_jmp)
                self.mem.w32(dst_ptr + 2, addr)
                size += 6
                src_ptr += 4
                dst_ptr -= 6
        return size
