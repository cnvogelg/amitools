INVALID_BOOT_BLOCK = 1
INVALID_ROOT_BLOCK = 2
INVALID_USER_DIR_BLOCK = 3
INVALID_FILE_HEADER_BLOCK = 4
INVALID_FILE_LIST_BLOCK = 5
INVALID_FILE_DATA_BLOCK = 6
NO_FREE_BLOCKS = 7
UNSUPPORTED_DIR_BLOCK = 8
INVALID_FILE_NAME = 9
NAME_ALREADY_EXISTS = 10
INVALID_SEQ_NUM = 11
FILE_LIST_BLOCK_COUNT_MISMATCH = 12
FILE_DATA_BLOCK_COUNT_MISMATCH = 13
INVALID_BITMAP_BLOCK = 14
BITMAP_BLOCK_COUNT_MISMATCH = 15
BITMAP_SIZE_MISMATCH = 16
DELETE_NOT_ALLOWED = 17
INTERNAL_ERROR = 18
INVALID_PROTECT_FORMAT = 19
INVALID_PARENT_DIRECTORY = 20
FILE_NOT_FOUND = 21
INVALID_VOLUME_NAME = 22

error_names = {
    INVALID_BOOT_BLOCK: "Invalid Boot Block",
    INVALID_ROOT_BLOCK: "Invalid Root Block",
    INVALID_USER_DIR_BLOCK: "Invalid UserDir Block",
    INVALID_FILE_HEADER_BLOCK: "Invalid FileHeader Block",
    INVALID_FILE_LIST_BLOCK: "Invalid FileList Block",
    INVALID_FILE_DATA_BLOCK: "Invalid FileData Block",
    NO_FREE_BLOCKS: "No Free Blocks",
    UNSUPPORTED_DIR_BLOCK: "Unsupported Dir Block",
    INVALID_FILE_NAME: "Invalid File Name",
    NAME_ALREADY_EXISTS: "Name already exists",
    INVALID_SEQ_NUM: "Invalid Sequence Number",
    FILE_LIST_BLOCK_COUNT_MISMATCH: "FileList Block Count Mismatch",
    FILE_DATA_BLOCK_COUNT_MISMATCH: "FileData Block Count Mismatch",
    INVALID_BITMAP_BLOCK: "Invalid Bitmap Block",
    BITMAP_BLOCK_COUNT_MISMATCH: "Bitmap Block Count Mismatch",
    BITMAP_SIZE_MISMATCH: "Bitmap Size Mismatch",
    DELETE_NOT_ALLOWED: "Delete Not Allowed",
    INTERNAL_ERROR: "Internal Error",
    INVALID_PROTECT_FORMAT: "Invalid Protect Format",
    INVALID_PARENT_DIRECTORY: "Invalid Parent Directory",
    FILE_NOT_FOUND: "File not found",
    INVALID_VOLUME_NAME: "Invalid volume name",
}


class FSError(Exception):
    def __init__(self, code, node=None, block=None, file_name=None, extra=None):
        self.code = code
        self.node = node
        self.block = block
        self.file_name = file_name
        self.extra = extra

    def __str__(self):
        if self.code in error_names:
            code_str = str(error_names[self.code])
        else:
            code_str = "?"
        srcs = []
        if self.node != None:
            srcs.append("node=" + str(self.node))
        if self.block != None:
            srcs.append("block=" + str(self.block))
        if self.file_name != None:
            srcs.append("file_name=" + self.file_name.get_unicode())
        if self.extra != None:
            srcs.append(str(self.extra))
        return "%s(%d):%s" % (code_str, self.code, ",".join(srcs))
