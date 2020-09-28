from .romaccess import RomAccess


RTC_MATCHWORD = 0x4AFC

RTF_AUTOINIT = 1 << 7
RTF_AFTERDOS = 1 << 2
RTF_SINGLETASK = 1 << 1
RTF_COLDSTART = 1 << 0

flag_names = {
    RTF_AUTOINIT: "RTF_AUTOINIT",
    RTF_AFTERDOS: "RTF_AFTERDOS",
    RTF_SINGLETASK: "RTF_SINGLETASK",
    RTF_COLDSTART: "RTF_COLDSTART",
}

NT_UNKNOWN = 0
NT_TASK = 1
NT_DEVICE = 3
NT_RESOURCE = 8
NT_LIBRARY = 9

nt_names = {
    NT_UNKNOWN: "NT_UNKNOWN",
    NT_TASK: "NT_TASK",
    NT_DEVICE: "NT_DEVICE",
    NT_RESOURCE: "NT_RESOURCE",
    NT_LIBRARY: "NT_LIBRARY",
}


class Resident:
    def __init__(
        self, off, flags, version, node_type, pri, name, id_string, init_off, skip_off
    ):
        self.off = off
        self.flags = flags
        self.version = version
        self.node_type = node_type
        self.pri = pri
        self.name = name
        self.id_string = id_string
        self.init_off = init_off
        self.skip_off = skip_off

    def __repr__(self):
        return (
            "Resident(@off=%08x,flags=%02x,version=%d,node_type=%d,"
            "pri=%d,name=%s,id_string=%s,init_off=%08x,skip_off=%08x)"
            % (
                self.off,
                self.flags,
                self.version,
                self.node_type,
                self.pri,
                self.name,
                self.id_string,
                self.init_off,
                self.skip_off,
            )
        )

    def get_flags_strings(self):
        f = self.flags
        res = []
        for fn in flag_names:
            if f & fn == fn:
                res.append(flag_names[fn])
        return res

    def get_node_type_str(self):
        nt = self.node_type
        if nt in nt_names:
            return nt_names[nt]
        else:
            return str(nt)

    @classmethod
    def parse(cls, access, off, base_addr):
        # +0 RT_MATCHWORD
        mw = access.read_word(off)
        if mw != RTC_MATCHWORD:
            raise ValueError("No RTC_MATCHWORD at resident offset!")
        # +2 RT_MATCHTAG
        tag_ptr = access.read_long(off + 2)
        if tag_ptr != base_addr + off:
            raise ValueError("Wrong MatchTag pointer in resident!")
        # +6 RT_ENDSKIP
        end_skip_ptr = access.read_long(off + 6)
        end_skip_off = end_skip_ptr - base_addr
        # +10..13 RT_FLAGS, RT_VERSION, RT_TYPE, RT_PRI
        flags = access.read_byte(off + 10)
        version = access.read_byte(off + 11)
        rtype = access.read_byte(off + 12)
        pri = access.read_sbyte(off + 13)
        # +14: RT_NAME
        name = cls._parse_cstr(access, off + 14, base_addr)
        # +18: RT_IDSTRING
        id_string = cls._parse_cstr(access, off + 18, base_addr)
        # +22: RT_INIT
        init_ptr = access.read_long(off + 22)
        init_off = init_ptr - base_addr
        return Resident(
            off, flags, version, rtype, pri, name, id_string, init_off, end_skip_off
        )

    @classmethod
    def _parse_cstr(cls, access, off, base_addr):
        str_ptr = access.read_long(off)
        if str_ptr == 0:
            return None
        str_off = str_ptr - base_addr
        res = []
        rom = access.rom_data
        while True:
            c = rom[str_off]
            if c == 0:
                break
            res.append(c)
            str_off += 1
        return bytes(res).decode("latin-1")


class ResidentScan:
    def __init__(self, rom_data, base_addr=0):
        self.access = RomAccess(rom_data)
        self.base_addr = base_addr

    def get_all_matchwords(self):
        """scan memory for all occurrences of matchwords"""
        mw = b"\x4a\xfc"
        res = []
        off = 0
        num = self.access.size
        rom = self.access.rom_data
        while off < num:
            pos = rom.find(mw, off)
            if pos == -1:
                break
            res.append(pos)
            off = pos + 2
        return res

    def guess_base_addr(self):
        offs = self.get_all_matchwords()
        if not offs:
            return None
        base_map = {}
        for off in offs:
            tag_ptr = self.access.read_long(off + 2)
            tag_off = tag_ptr & 0xFFFF
            if tag_off == off:
                base_addr = tag_ptr & ~0xFFFF
                if base_addr not in base_map:
                    base_map[base_addr] = 1
                else:
                    base_map[base_addr] += 1
        # one match
        if not base_map:
            return None
        elif len(base_map) == 1:
            addr = list(base_map.keys())[0]
            return addr
        else:
            return sorted(list(base_map.keys()), key=lambda x: base_map[x])

    def get_all_resident_pos(self):
        offs = self.get_all_matchwords()
        res = []
        for off in offs:
            # check tag ptr
            tag_ptr = self.access.read_long(off + 2)
            if tag_ptr == self.base_addr + off:
                res.append(off)
        return res

    def is_resident_at(self, off):
        mw = self.access.read_word(off)
        if mw != RTC_MATCHWORD:
            return False
        tag_ptr = self.access.read_long(off + 2)
        return tag_ptr == self.base_addr + off

    def get_resident(self, off):
        return Resident.parse(self.access, off, self.base_addr)
