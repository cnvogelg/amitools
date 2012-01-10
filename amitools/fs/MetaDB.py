from MetaInfo import MetaInfo
from ProtectFlags import ProtectFlags
from TimeStamp import TimeStamp

class MetaDB:
  def __init__(self):
    self.metas = {}
  
  def set_meta_info(self, path, meta_info):
    self.metas[path] = meta_info
  
  def get_meta_info(self, path):
    if self.metas.has_key(path):
      return self.metas[path]
    else:
      return None
    
  def load(self, file_path):
    self.metas = {}
    f = open(file_path, "r")
    for line in f:
      line = line.strip()
      # path
      pos = line.find(':')
      if pos == -1:
        raise IOError("Invalid xdfmeta file! (no colon in line)")
      path = line[:pos]
      # prot
      line = line[pos+1:]
      pos = line.find(',')
      if pos == -1:
        raise IOError("Invalid xdfmeta file! (no first comma)")
      prot_str = line[:pos]
      prot = ProtectFlags()
      prot.parse(prot_str)
      # time
      line = line[pos+1:]
      pos = line.find(',')
      if pos == -1:
        raise IOError("Invalid xdfmeta file! (no second comma)")
      time_str = line[:pos]
      time = TimeStamp()
      time.parse(time_str)
      # comment
      comment = line[pos+1:]
      # meta info
      mi = MetaInfo(protect_flags=prot, mod_ts=time, comment=comment)
      self.set_meta_info(path, mi)
    f.close()
    
  def save(self, file_path):
    f = open(file_path, "w")
    for path in sorted(self.metas):
      meta_info = self.metas[path]
      protect = meta_info.get_protect_short_str()
      mod_time = meta_info.get_time_str()
      comment = meta_info.get_comment_str()
      line = "%s:%s,%s,%s\n" % (path, protect, mod_time, comment)
      f.write(line)
    f.close()

