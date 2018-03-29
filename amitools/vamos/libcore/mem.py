import datetime
from amitools.vamos.astructs import AccessStruct, LibraryDef
from amitools.vamos.label import LabelLib
from .info import LibInfo


class LibMem(object):
  """manage the in-memory representation of a library"""

  NT_LIBRARY = 9

  # flags
  LIBF_SUMMING = 1
  LIBF_CHANGED = 2
  LIBF_SUMUSED = 4
  LIBF_DELEXP = 8

  def __init__(self, mem, addr, struct=None):
    self.mem = mem
    self.addr = addr
    if struct is None:
      struct = LibraryDef
    self.struct = struct
    self.access = AccessStruct(mem, struct, addr)
    self.label = None

  def __str__(self):
    return "@%08x" % self.addr

  def get_addr(self):
    return self.addr

  def init_base(self, pri=0):
    self.access.w_s("lib_Node.ln_Succ", 0)
    self.access.w_s("lib_Node.ln_Pred", 0)
    self.access.w_s("lib_Node.ln_Type", self.NT_LIBRARY)
    self.access.w_s("lib_Node.ln_Pri", pri)
    self.access.w_s("lib_Flags", 0)
    self.access.w_s("lib_Sum", 0)
    self.access.w_s("lib_OpenCnt", 0)

  def write_info(self, info, name_str_addr, id_str_addr):
    self.access.w_s("lib_Node.ln_Name", name_str_addr)
    self.access.w_s("lib_NegSize", info.get_neg_size())
    self.access.w_s("lib_PosSize", info.get_pos_size())
    self.access.w_s("lib_Version", info.get_version())
    self.access.w_s("lib_Revision", info.get_revision())
    self.access.w_s("lib_IdString", id_str_addr)
    self.mem.w_cstr(name_str_addr, info.get_name())
    self.mem.w_cstr(id_str_addr, info.get_id_string())

  def read_info(self):
    name_addr = self.access.r_s("lib_Node.ln_Name")
    name = self.mem.r_cstr(name_addr)
    neg_size = self.access.r_s("lib_NegSize")
    pos_size = self.access.r_s("lib_PosSize")
    version = self.access.r_s("lib_Version")
    revision = self.access.r_s("lib_Revision")
    id_str_addr = self.access.r_s("lib_IdString")
    id_str = self.mem.r_cstr(id_str_addr)
    date = LibInfo.extract_date(id_str)
    if date is None:
      # fake date
      date = datetime.date(2007, 7, 7)
    return LibInfo(name, version, revision, date, pos_size, neg_size)

  def write_flags(self, flags):
    self.access.w_s("lib_Flags", flags)

  def read_flags(self):
    return self.access.r_s("lib_Flags")

  def write_open_cnt(self, cnt):
    self.access.w_s("lib_OpenCnt", cnt)

  def read_open_cnt(self):
    return self.access.r_s("lib_OpenCnt")

  def inc_open_cnt(self):
    cnt = self.access.r_s("lib_OpenCnt")
    cnt = cnt + 1
    self.access.w_s("lib_OpenCnt", cnt)
    return cnt

  def dec_open_cnt(self):
    cnt = self.access.r_s("lib_OpenCnt")
    cnt = cnt - 1
    self.access.w_s("lib_OpenCnt", cnt)
    return cnt

  def read_sum(self):
    return self.access.r_s("lib_Sum")

  def write_sum(self, val):
    self.access.w_s("lib_Sum", val)

  def calc_sum(self):
    neg_size = self.access.r_s("lib_NegSize")
    addr = self.addr - neg_size
    lib_sum = 0
    while addr < self.addr:
      val = self.mem.r32(addr)
      lib_sum += val
      addr += 4
    lib_sum &= 0xffffffff
    return lib_sum

  def update_sum(self):
    lib_sum = self.calc_sum()
    self.write_sum(lib_sum)

  def check_sum(self):
    lib_sum = self.calc_sum()
    got_sum = self.read_sum()
    return lib_sum == got_sum

  def set_label(self, label_mgr):
    name_addr = self.access.r_s("lib_Node.ln_Name")
    name = self.mem.r_cstr(name_addr)
    neg_size = self.access.r_s("lib_NegSize")
    pos_size = self.access.r_s("lib_PosSize")
    addr_begin = self.addr - neg_size
    size = neg_size + pos_size
    # TODO: re-enable label
    #self.label = LabelLib(self)
    #label_mgr.add_label(self.label)
    return self.label

  def remove_label(self, label_mgr):
    #label_mgr.remove_label(self.label)
    self.label = None
