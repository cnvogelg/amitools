from ADFSDir import ADFSDir
from MetaInfo import MetaInfo

class ADFSVolDir(ADFSDir):
  def __init__(self, volume, root_block):
    ADFSDir.__init__(self, volume, None)
    self.set_block(root_block)
    self._init_name_hash()
  
  def __repr__(self):
    return "[VolDir(%d)'%s':%s]" % (self.block.blk_num, self.block.name, self.entries)
  
  def draw_on_bitmap(self, bm, show_all=False):
    blk_num = self.block.blk_num
    bm[blk_num] = 'V'
    if show_all:
      for e in self.entries:
        e.draw_on_bitmap(bm, True)

  def get_size_str(self):
    return "VOLUME"

  def create_meta_info(self):
    self.meta_info = MetaInfo(mod_ts=self.block.mod_ts)
  
  def can_delete(self):
    return False

