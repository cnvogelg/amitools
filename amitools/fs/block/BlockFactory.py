from .Block import Block
from .RootBlock import RootBlock
from .UserDirBlock import UserDirBlock
from .FileHeaderBlock import FileHeaderBlock
from .FileListBlock import FileListBlock
from .FileDataBlock import FileDataBlock
from .CommentBlock import CommentBlock
from .DirCacheBlock import DirCacheBlock


class BlockFactory:
    @classmethod
    def create_block(cls, blkdev, blk_num, type, sub_type):
        if type == Block.T_SHORT:
            if sub_type == Block.ST_ROOT:
                return RootBlock(blkdev, blk_num)
            elif sub_type == Block.ST_USERDIR:
                return UserDirBlock(blkdev, blk_num)
            elif sub_type == Block.ST_FILE:
                return FileHeaderBlock(blkdev, blk_num)
        elif type == Block.T_LIST:
            if sub_type == Block.ST_FILE:
                return FileListBlock(blkdev, blk_num)
        elif type == Block.T_DATA:
            return FileDataBlock(blkdev, blk_num)
        elif type == Block.T_COMMENT:
            return CommentBlock(blkdev, blk_num)
        elif type == Block.T_DIR_CACHE:
            return DirCacheBlock(blkdev, blk_num)

    @classmethod
    def create_specific_block(cls, block):
        return cls.create_block(block.blkdev, block.blk_num, block.type, block.sub_type)
