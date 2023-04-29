import logging
from .romaccess import RomAccess


class RomPatch:
    def __init__(self, name, desc, args_desc=None):
        self.name = name
        self.desc = desc
        self.args_desc = args_desc

    def apply_patch(self, access, args=None):
        return False

    def _ensure_arg(self, args, arg_name):
        if arg_name not in args:
            logging.error("%s: '%s' argument missing!", self.name, arg_name)
            return False
        return True


class OneMegRomPatch(RomPatch):
    def __init__(self):
        RomPatch.__init__(
            self, "1mb_rom", "Patch Kickstart to support ext ROM with 512 KiB"
        )

    def apply_patch(self, access, args=None):
        off = 8
        while off < 0x430:
            v = access.read_long(off)
            if v == 0xF80000:
                v4 = access.read_long(off + 4)
                v8 = access.read_long(off + 8)
                vc = access.read_long(off + 0xC)
                v10 = access.read_long(off + 0x10)
                if (
                    v4 == 0x1000000
                    and v8 == 0xF00000
                    and vc == 0xF80000
                    and v10 == 0xFFFFFFFF
                ):
                    vp8 = access.read_long(off - 8)
                    if vp8 == 0xF80000:
                        access.write_long(off - 4, 0x1000000)
                        access.write_long(off, 0xE00000)
                        access.write_long(off + 4, 0xE80000)
                        logging.info("@%08x Variant A", off)
                        return True
                    else:
                        access.write_long(off, 0xF00000)
                        access.write_long(off + 8, 0xE00000)
                        access.write_long(off + 0xC, 0xE80000)
                        logging.info("@%08x Variant B", off)
                        return True
            off += 2
        logging.error("Exec Table not found!")
        return False


class FourMegRomPatch(RomPatch):
    def __init__(self):
        RomPatch.__init__(
            self, "4mb_rom", "Patch Kickstart to support ext ROM with 3584 KiB"
        )

    def apply_patch(self, access, args=None):
        off = 8
        while off < 0x430:
            v = access.read_long(off)
            if v == 0xF80000:
                v4 = access.read_long(off + 4)
                v8 = access.read_long(off + 8)
                vc = access.read_long(off + 0xC)
                v10 = access.read_long(off + 0x10)
                if (
                    v4 == 0x1000000
                    and v8 == 0xF00000
                    and vc == 0xF80000
                    and v10 == 0xFFFFFFFF
                ):
                    vp8 = access.read_long(off - 8)
                    if vp8 == 0xF80000:
                        access.write_long(off - 4, 0x1000000)
                        access.write_long(off, 0x1000000)
                        access.write_long(off + 4, 0x1400000)
                        logging.info("@%08x Variant A", off)
                        return True
                    else:
                        access.write_long(off, 0xF00000)
                        access.write_long(off + 8, 0x1000000)
                        access.write_long(off + 0xC, 0x1400000)
                        logging.info("@%08x Variant B", off)
                        return True
            off += 2
        logging.error("Exec Table not found!")
        return False


class BootConRomPatch(RomPatch):
    def __init__(self):
        RomPatch.__init__(
            self,
            "boot_con",
            "Set the boot console",
            {"name": "name of the new console," " e.g. 'CON:MyConsole'"},
        )

    def apply_patch(self, access, args):
        # search CON:
        data = access.get_data()
        off = data.find(b"CON:")
        if off == -1:
            logging.error("console not found!")
            return False
        # find terminator
        pos = data.find(b"\0", off)
        if pos == -1:
            logging.error("no console end found!")
            return False
        # build old string
        con_old_len = pos - off
        con_old = data[off:pos]
        logging.info("@%08x: +%08x  old='%s'" % (off, con_old_len, con_old))
        # check new string
        if "name" in args:
            con_new = args["name"].encode("latin-1")
            con_new_len = len(con_new)
            if con_new_len > con_old_len:
                logging.error("new console name is too long (>%d)!", con_old_len)
                return False
            # pad and write to rom
            pad_len = con_old_len - con_new_len + 1
            con_new += b"\0" * pad_len
            data[off : pos + 1] = con_new
            logging.info("new='%s'" % (con_new_len))
        return True


class RomPatcher:

    # list of all available patch classes
    patches = [OneMegRomPatch(), FourMegRomPatch(), BootConRomPatch()]

    def __init__(self, rom):
        self.access = RomAccess(rom)
        self.access.make_writable()

    def get_all_patch_names(self):
        res = []
        for p in self.patches:
            res.append(p.name)
        return res

    def find_patch(self, name):
        for p in self.patches:
            if p.name == name:
                return p

    def apply_patch(self, patch, args=None):
        return patch.apply_patch(self.access, args)

    def get_patched_rom(self):
        return self.access.get_data()
