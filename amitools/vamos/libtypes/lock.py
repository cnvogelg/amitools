from amitools.vamos.libstructs import FileLockStruct, FileHandleStruct
from amitools.vamos.astructs import AmigaClassDef


@AmigaClassDef
class FileLock(FileLockStruct):
    pass


@AmigaClassDef
class FileHandle(FileHandleStruct):
    pass
