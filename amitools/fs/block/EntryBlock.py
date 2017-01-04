from __future__ import absolute_import
from __future__ import print_function

from .Block import Block
from .CommentBlock import CommentBlock

class EntryBlock(Block):
  """Base class for all block types that describe entries within a directory"""
  def __init__(self, blkdev, blk_num, is_type, is_sub_type, is_longname=False):
    Block.__init__(self, blkdev, blk_num, is_type, is_sub_type)
    self.is_longname = is_longname
    self.comment_block_id = 0

  def _read_nac_modts(self):
    """Reads the name, comment, and modifcation timestamp"""
    if self.is_longname:
      # In long filename mode, we have a combined field that contains
      # the filename and the comment as consequtive BSTR. If the comment does
      # not fit in, it is stored in an extra block
      nac = self._get_cstr(-46,112)
      name_len = ord(nac[0])
      self.name = nac[1:name_len+1]
      if len(nac) > name_len + 1:
        comment_len = ord(nac[name_len+1])
        self.comment = nac[name_len+2:name_len+2+comment_len]
      else:
        # Comment is located in an extra block
        self.comment_block_id = self._get_long(-18)
        self.comment = ""
      self.mod_ts = self._get_timestamp(-15)
    else:
      self.comment = self._get_bstr(-46, 79)
      self.name = self._get_bstr(-20, 30)
      self.mod_ts = self._get_timestamp(-23)

  def _write_nac_modts(self):
    """Writes the name, comment, and modifcation timestamp"""
    if self.is_longname:
      if self.comment_block_id != 0:
        nac = chr(len(self.name)) + self.name + chr(0)
      else:
        nac = chr(len(self.name)) + self.name + chr(len(self.comment)) + self.comment
      self._put_cstr(-46, 122, nac)
      self._put_long(-18, self.comment_block_id)
      self._put_timestamp(-15, self.mod_ts)
    else:
      self._put_bstr(-46, 79, self.comment)
      self._put_timestamp(-23, self.mod_ts)
      self._put_bstr(-20, 30, self.name)
  
  @staticmethod
  def needs_extra_comment_block(name, comment):
    """Returns whether the given name/comment pair requires an extra comment block"""
    return len(name) + len(comment) > 110
