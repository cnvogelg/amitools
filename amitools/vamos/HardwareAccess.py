from Log import log_hw

class HardwareAccess:
  """As an OS-level emulator vamos usually does not need to emulate
     any custom chips. Unfortunately, some libs (e.g. xvs.library)
     need custom chip access to work correctly. We emulate a minimal
     sub set to make those broken (i.e. non OS-compliant) libs work.
  """

  MODE_IGNORE = 0
  MODE_EMU = 1
  MODE_ABORT = 2
  MODE_DISABLE = 3

  def __init__(self, raw_mem):
    # setup $BFxxxx CIA range
    raw_mem.set_special_range_read_funcs(0xbf0000, 1, self.cia_r8, None, None)
    raw_mem.set_special_range_write_funcs(0xbf0000, 1, self.cia_w8, None, None)
    # setup $DFxxxx Custom Chip range
    raw_mem.set_special_range_read_funcs(0xdf0000, 1, None, self.cc_r16, None)
    raw_mem.set_special_range_write_funcs(0xdf0000, 1, None, self.cc_w16, None)
    # set mode
    self.mode = self.MODE_IGNORE
    self.raw_mem = raw_mem

  def set_mode(self, mode):
    self.mode = mode

  def cia_r8(self, addr):
    log_hw.warn("CIA read byte @%06x",addr)
    if self.mode == self.MODE_ABORT:
      self.raw_mem.set_all_to_end()
    return 0

  def cia_w8(self, addr, val):
    log_hw.warn("CIA write byte @%06x: %02x",addr,val)
    if self.mode == self.MODE_ABORT:
      self.raw_mem.set_all_to_end()

  def cc_r16(self, addr):
    log_hw.warn("Custom Chip read word @%06x",addr)
    if self.mode == self.MODE_ABORT:
      self.raw_mem.set_all_to_end()
    return 0

  def cc_w16(self, addr, val):
    log_hw.warn("Custom Chip write word @%06x: %04x",addr,val)
    if self.mode == self.MODE_ABORT:
      self.raw_mem.set_all_to_end()
