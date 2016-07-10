from UtilStruct import *

TAG_DONE = 0
TAG_IGNORE = 1
TAG_MORE = 2
TAG_SKIP = 3

TAG_USER = 1<<31

class Tag:
  def __init__(self,tag,data,tag_info):
    self.user = (tag & TAG_USER == TAG_USER)
    self.tag = tag & ~TAG_USER
    self.data = data
    if tag_info != None and tag_info.has_key(self.tag):
      self.name = tag_info[self.tag]
    else:
      self.name = None
    
  def __str__(self):
    if self.user:
      return "(U:%s/%08x->%08x)" % (self.name, self.tag, self.data)
    else:
      return "(S:%s/%08x->%08x)" % (self.name, self.tag, self.data)

class TagList:
  def __init__(self, tag_info):
    self.tags = []
    self.tag_info = tag_info
    
  def add(self, tag, data):
    self.tags.append(Tag(tag,data, self.tag_info))

  def find_tag(self, tagname):
    for tag in self.tags:
      if tag.name == tagname:
        return tag
    return None
  
  def __str__(self):
    return "[%s]" % ",".join(map(str, self.tags))

def taglist_parse_tagitem_ptr(mem, addr, tag_info=None):
  result = TagList(tag_info)
  while True:
    tag = mem.access.r32(addr)
    data = mem.access.r32(addr+4)
    if tag == TAG_DONE:
      break
    elif tag == TAG_IGNORE:
      addr += 8
    elif tag == TAG_SKIP:
      addr += 8
    elif tag == TAG_MORE:
      addr = data
    else:
      result.add(tag,data)
      addr += 8
  return result
