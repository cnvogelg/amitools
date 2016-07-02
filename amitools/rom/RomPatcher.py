import logging
from RomAccess import RomAccess


class RomPatch:
  def __init__(self, name, desc):
    self.name = name
    self.desc = desc

  def apply_patch(self, access):
    return False


class OneMegRomPatch(RomPatch):
  def __init__(self):
    RomPatch.__init__(self, "1mb_rom", "Patch Kickstart to support ext ROM with 512 KiB")

  def apply_patch(self, access):
    off = 8
    while off < 0x400:
      v = access.read_long(off)
      if v == 0xf80000:
        v4 = access.read_long(off+4)
        v8 = access.read_long(off+8)
        vc = access.read_long(off+0xc)
        v10 = access.read_long(off+0x10)
        if v4 == 0x1000000 and v8 == 0xf00000 and \
           vc == 0xf80000 and v10 == 0xffffffff:
          vp8 = access.read_long(off-8)
          if vp8 == 0xf80000:
            access.write_long(off-4, 0x1000000)
            access.write_long(off, 0xe00000)
            access.write_long(off+4, 0xe80000)
            logging.info("@%08x Variant A", off)
            return True
          else:
            access.write_long(off, 0xf00000)
            access.write_long(off+8, 0xe00000)
            access.write_long(off+0xc, 0xe80000)
            logging.info("@%08x Variant B", off)
            return True
      off += 2
    logging.error("Exec Table not found!")
    return False


# list of all available patch classes
patches = [
  OneMegRomPatch()
]


class RomPatcher:
  def __init__(self, rom):
    self.access = RomAccess(rom)
    self.access.make_writable()

  def get_all_patch_names(self):
    res = []
    for p in self.patches:
      res.append(p.name)
    return res

  def find_patch(self, name):
    for p in patches:
      if p.name == name:
        return p

  def apply_patch(self, patch):
    return patch.apply_patch(self.access)

  def get_patched_rom(self):
    return self.access.get_data()
