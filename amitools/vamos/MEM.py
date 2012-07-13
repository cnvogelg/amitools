class MEM:
  def __init__(self, name):
    self.name = name
  def init(self,ram_size_kib):
    pass
  def free(self):
    pass
  def read_ram(self,width, addr):
    return 0
  def write_ram(self,width, addr, val):
    pass
  def read_ram_block(self,addr,size,data):
    pass
  def write_ram_block(self,addr,size,data):
    pass
  def clear_ram_block(self,addr,size,value):
    pass
  def reserve_special_range(self,num_pages):
    return 0
  def set_special_range_read_func(self,page_addr, width, func):
    pass
  def set_special_range_write_func(self,page_addr, width, func):
    pass