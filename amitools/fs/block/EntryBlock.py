from .Block import Block
from .CommentBlock import CommentBlock
from ..FSString import FSString


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
            nac = self._get_bytes(-46, 112)
            name_len = nac[0]
            self.name = FSString(nac[1 : name_len + 1])
            comment_len = nac[name_len + 1]
            if comment_len > 0:
                self.comment = FSString(nac[name_len + 2 : name_len + 2 + comment_len])
            else:
                # Comment is located in an extra block
                self.comment_block_id = self._get_long(-18)
                self.comment = FSString()
            self.mod_ts = self._get_timestamp(-15)
        else:
            self.comment = self._get_bstr(-46, 79)
            self.name = self._get_bstr(-20, 30)
            self.mod_ts = self._get_timestamp(-23)

    def _write_nac_modts(self):
        """Writes the name, comment, and modifcation timestamp"""
        if self.is_longname:
            nac = bytearray()
            name = self.name.get_ami_str()
            name_len = len(name)
            nac.append(name_len)
            nac += name
            if self.comment_block_id != 0:
                nac.append(0)
            else:
                comment = self.name.get_ami_str()
                comment_len = len(comment)
                nac.append(comment_len)
                nac += comment
            self._put_bytes(-46, nac)
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
