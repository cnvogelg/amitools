from FileName import FileName
from MetaInfo import MetaInfo
from ProtectFlags import ProtectFlags
from TimeStamp import TimeStamp
from FSError import *

class ADFSNode:
  def __init__(self, volume, parent):
    self.volume = volume
    self.blkdev = volume.blkdev
    self.parent = parent
    self.block_bytes = self.blkdev.block_bytes
    self.block = None
    self.name = None
    self.valid = False
    self.meta_info = None
  
  def set_block(self, block):  
    self.block = block
    self.name = FileName(self.block.name)
    self.valid = True
    self.create_meta_info()
    
  def create_meta_info(self):
    self.meta_info = MetaInfo(self.block.protect, self.block.mod_ts, self.block.comment)

  def get_file_name_str(self):
    return self.name.name

  def delete(self, wipe=False, all=False):
    if all:
      self.delete_children(wipe, all)
    self.parent._delete(self, wipe=wipe)

  def delete_children(self, wipe, all):
    pass

  def get_meta_info(self):
    return self.meta_info

  def change_meta_info(self, meta_info):
    dirty = False

    # dircache?
    rebuild_dircache = False
    if self.volume.is_dircache and self.parent != None:
      record = self.parent.get_dircache_record(self.get_file_name_str())
      if record == None:
        raise FSError(INTERNAL_ERROR, node=self)

    # alter protect flags
    protect = meta_info.get_protect()
    if protect != None and hasattr(self.block, 'protect'):
      self.block.protect = protect
      self.meta_info.set_protect(protect)
      dirty = True
      if record != None:
        record.protect = protect

    # alter mod time
    mod_ts = meta_info.get_mod_ts()
    if mod_ts != None:
      self.block.mod_ts = mod_ts
      self.meta_info.set_mod_ts(mod_ts)
      dirty = True
      if record != None:
        record.mod_ts = mod_ts
    
    # alter comment
    comment = meta_info.get_comment()
    if comment != None and hasattr(self.block, "comment"):
      self.block.comment = comment
      self.meta_info.set_comment(comment)
      dirty = True
      if record != None:
        rebuild_dircache = len(record.comment) < comment 
        record.comment = comment
    
    # really need update?
    if dirty:
      self.block.write()
      # dirache update
      if record != None:
        self.parent.update_dircache_record(record, rebuild_dircache)        
      
  def change_comment(self, comment):
    self.change_meta_info(MetaInfo(comment=comment))
    
  def change_protect(self, protect):
    self.change_meta_info(MetaInfo(protect=protect))
    
  def change_protect_by_string(self, pr_str):
    p = ProtectFlags()
    p.parse(pr_str)
    self.change_protect(p.mask)
    
  def change_mod_ts(self, mod_ts):
    self.change_meta_info(MetaInfo(mod_ts=mod_ts))
    
  def change_mod_ts_by_string(self, tm_str):
    t = TimeStamp()
    t.parse(tm_str)
    self.change_meta_info(MetaInfo(mod_ts=t))

  def list(self, indent=0, all=False):
    istr = "  " * indent
    print "%-40s       %8s  %s" % (istr + self.block.name, self.get_size_str(), str(self.meta_info))

  def dump_blocks(self, with_data=False):
    blks = self.get_blocks(with_data)
    for b in blks:
      b.dump()

  def get_node_path(self, with_vol=False):
    if self.parent != None:
      if not with_vol and self.parent.parent == None:
        r = []
      else:
        r = self.parent.get_node_path()
    else:
      if not with_vol:
        return []
      r = []
    r.append(self.name.name)
    return r

  def get_node_path_name(self, with_vol=False):
    r = self.get_node_path()
    return "/".join(r)

      