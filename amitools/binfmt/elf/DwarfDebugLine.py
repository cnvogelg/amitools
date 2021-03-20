import io
import struct


class LineState:
    def __init__(self, is_stmt=False):
        self.address = 0
        self.file = 1
        self.line = 1
        self.column = 0
        self.is_stmt = is_stmt
        self.basic_block = False
        self.end_sequence = False
        self.section = None

    def clone(self):
        state = LineState()
        state.address = self.address
        state.file = self.file
        state.line = self.line
        state.column = self.column
        state.is_stmt = self.is_stmt
        state.basic_block = self.basic_block
        state.end_sequence = self.end_sequence
        state.section = self.section
        return state

    def __str__(self):
        return "[address=%08x file=%d line=%d column=%d is_stmt=%s basic_block=%s end_sequence=%d]" % (
            self.address,
            self.file,
            self.line,
            self.column,
            self.is_stmt,
            self.basic_block,
            self.end_sequence,
        )


class DwarfDebugLine:
    """decode .debug_line Dwarf line debug sections"""

    def __init__(self, verbose=False):
        self.input = None
        self.error = None
        self.verbose = verbose
        self.matrix = None

    def _log(self, *args):
        if self.verbose:
            print(*args)

    def decode(self, elf_file):
        # get section with debug info
        debug_line = elf_file.get_section_by_name(".debug_line")
        if debug_line is None:
            self.error = "No .debug_line section found! No debug info?"
            return False
        # get (optional) relocations
        rela = elf_file.get_section_by_name(".rela.debug_line")
        # start parsing
        self.input = io.StringIO(debug_line.data)
        # decode header
        if not self.decode_header():
            return False
        if self.verbose:
            self.dump_header()
        # decode line program
        matrix = []
        state = LineState(self.default_is_stmt)
        log = self._log
        while True:
            # read opcode
            opc_ch = self.input.read(1)
            if len(opc_ch) == 0:
                break
            opc = ord(opc_ch)
            log("opcode=", opc)
            # 0 = extended opcode
            if opc == 0:
                opc_size = self.read_leb128()
                sub_opc = ord(self.input.read(1))
                log("  sub_opcode=", sub_opc)
                # 1: DW_LNE_end_sequence
                if sub_opc == 1:
                    state.end_sequence = True
                    line = state.clone()
                    matrix.append(line)
                    state.__init__()
                    log("DW_LNE_end_sequence:", line)
                # 2: DW_LNE_set_address
                elif sub_opc == 2:
                    pos = self.input.tell()
                    addr = self.read_long()
                    addend, sect = self.find_rela(rela, pos)
                    state.address = addr + addend
                    state.section = sect
                    log("DW_LNE_set_address: %08x  sect=%s" % (state.address, sect))
                # 3: DW_LNE_set_file
                elif sub_opc == 3:
                    tup = self.decode_file()
                    self.files.append(tup)
                    log("DW_LNE_set_file", tup)
                # other (unknown) ext opc
                else:
                    log("unknown sub opcode!")
                    self.input.seek(opc_size - 1, 1)
            # standard opcodes
            elif opc < self.opc_base:
                # 1: DW_LNS_copy
                if opc == 1:
                    line = state.clone()
                    matrix.append(line)
                    log("DW_LNS_copy:", line)
                    state.basic_block = False
                # 2: DW_LNS_advance_pc
                elif opc == 2:
                    offset = self.read_leb128() * self.min_instr_len
                    state.address += offset
                    log("DW_LNS_advance_pc: +%d -> %08x" % (offset, state.address))
                # 3: DW_LNS_advance_line
                elif opc == 3:
                    offset = self.read_sleb128()
                    state.line += offset
                    log("DW_LNS_advance_line: +%d -> %d" % (offset, state.line))
                # 4: DW_LNS_set_file
                elif opc == 4:
                    state.file = self.read_leb128()
                    log("DW_LNS_set_file", state.file)
                # 5: DW_LNS_set_column
                elif opc == 5:
                    state.column = self.read_leb128()
                    log("DW_LNS_set_column", state.column)
                # 6: DW_LNS_negate_stmt
                elif opc == 6:
                    state.is_stmt = not state.is_stmt
                    log("DW_LNS_negate_stmt", state.is_stmt)
                # 7: DW_LNS_set_basic_block
                elif opc == 7:
                    state.basic_block = True
                    log("DW_LNS_set_basic_block")
                # 8: DW_LNS_const_add_pc
                elif opc == 8:
                    (addr_addend, _) = self.decode_special_opcode(255)
                    state.address += addr_addend
                    log(
                        "DW_LNS_const_add_pc: +%d -> %08x"
                        % (addr_addend, state.address)
                    )
                # 9: DW_LNS_fixed_advance_pc
                elif opc == 9:
                    offset = self.read_word()
                    state.address += offset
                    log("DW_LNS_fixed_advance_pc: %+08x" % offset)
                # other (unknown) opc
                else:
                    num_args = self.std_opc_lens[opc]
                    log("skip unknown: num_args=", num_args)
                    for i in range(num_args):
                        self.read_leb128()
            # special opcodes:
            else:
                (addr_addend, line_addend) = self.decode_special_opcode(opc)
                state.address += addr_addend
                state.line += line_addend
                state.basic_block = False
                line = state.clone()
                matrix.append(line)
                log("special", (opc - self.opc_base), line)
        # done
        self.matrix = matrix
        return True

    def get_matrix(self):
        return self.matrix

    def get_file_dir(self, idx):
        f = self.files[idx - 1]
        dir_idx = f[1]
        if dir_idx > 0:
            dir_name = self.inc_dirs[dir_idx - 1]
        else:
            dir_name = ""
        return dir_name

    def get_file_name(self, idx):
        return self.files[idx - 1][0]

    def find_rela(self, rela_section, pos):
        if rela_section is not None:
            for rela in rela_section.rela:
                if rela.offset == pos:
                    return rela.addend, rela.section
        return 0, None

    def decode_special_opcode(self, opc):
        adj_opc = opc - self.opc_base
        addr_addend = (adj_opc // self.line_range) * self.min_instr_len
        line_addend = self.line_base + (adj_opc % self.line_range)
        return (addr_addend, line_addend)

    def decode_header(self):
        # header
        self.unit_length = self.read_long()
        self.version = self.read_word()
        if self.version != 2:
            self.error = "Can only decode DWARF 2 debug info"
            return False
        self.header_length = self.read_long()
        self.min_instr_len = self.read_byte()
        self.default_is_stmt = self.read_byte()
        self.line_base = self.read_sbyte()
        self.line_range = self.read_byte()
        self.opc_base = self.read_byte()
        # 9 standard opcode lengths
        self.std_opc_lens = []
        n = self.opc_base
        if n > 0:
            for i in range(n - 1):
                l = self.read_byte()
                self.std_opc_lens.append(l)
        # 10 include dirs
        self.inc_dirs = []
        while True:
            inc_dir = self.read_string()
            if inc_dir == "":
                break
            self.inc_dirs.append(inc_dir)
        # 11 file names
        self.files = []
        while True:
            tup = self.decode_file()
            if tup is None:
                break
            self.files.append(tup)
        # end header: check header size
        pos = self.input.tell()
        hdr_len = pos - 10
        if hdr_len != self.header_length:
            self.error = "Error size mismatch: %d != %d" % (hdr_len, self.header_length)
            return False
        return True

    def decode_file(self):
        file_name = self.read_string()
        if file_name == "":
            return None
        dir_idx = self.read_leb128()
        last_mod = self.read_leb128()
        file_size = self.read_leb128()
        return (file_name, dir_idx, last_mod, file_size)

    def dump_header(self):
        print(
            "unit_length=%x version=%d header_length=%x max_instr_len=%d "
            "default_is_stmt=%d line_base=%d line_range=%d opc_base=%d"
            % (
                self.unit_length,
                self.version,
                self.header_length,
                self.min_instr_len,
                self.default_is_stmt,
                self.line_base,
                self.line_range,
                self.opc_base,
            )
        )
        print("std_opc_lens:", ",".join(map(str, self.std_opc_lens)))
        print("inc_dirs")
        for d in self.inc_dirs:
            print(d)
        print("files")
        for f in self.files:
            print(f)

    def read_string(self):
        result = []
        while True:
            ch = self.input.read(1)
            if ord(ch) == 0:
                break
            result.append(ch)
        return "".join(result)

    def read_leb128(self):
        result = 0
        shift = 0
        while True:
            byte = self.read_byte()
            result |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                break
            shift += 7
        return result

    def read_sleb128(self):
        result = 0
        shift = 0
        while True:
            byte = self.read_byte()
            result |= (byte & 0x7F) << shift
            shift += 7
            if byte & 0x80 == 0:
                break
        # negative?
        if byte & 0x40 == 0x40:
            mask = 1 << shift
            result |= -mask
        return result

    def read_long(self):
        data = self.input.read(4)
        return struct.unpack(">I", data)[0]

    def read_word(self):
        data = self.input.read(2)
        return struct.unpack(">H", data)[0]

    def read_byte(self):
        data = self.input.read(1)
        return struct.unpack(">B", data)[0]

    def read_sbyte(self):
        data = self.input.read(1)
        return struct.unpack(">b", data)[0]


# mini test
if __name__ == "__main__":
    import sys
    from .ELFReader import ELFReader

    reader = ELFReader()
    for a in sys.argv[1:]:
        f = open(a, "rb")
        ef = reader.load(f)
        ddl = DwarfDebugLine(verbose=True)
        ok = ddl.decode(ef)
        if ok:
            print("--- line matrix ---")
            for row in ddl.get_matrix():
                name = ddl.get_file_name(row.file)
                fdir = ddl.get_file_dir(row.file)
                sect_name = row.section.name_str
                print(
                    "%08x: %s [%s] %s:%d"
                    % (row.address, sect_name, fdir, name, row.line)
                )
