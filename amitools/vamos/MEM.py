class MEM:
  def __init__(self, name):
    self.name = name
  def init(self,ram_size_kib):
    pass
  def free(self):
    pass
  def read_mem(self,width, addr):
    return 0
  def write_mem(self,width, addr, val):
    pass
  def reserve_special_range(num_pages):
    return 0
  def set_special_range_read_func(page_addr, width, func):
    pass
  def set_special_range_write_func(page_addr, width, func):
    pass