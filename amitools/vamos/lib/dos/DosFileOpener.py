from amitools.vamos.loader import FileObj, FileOpener


class DosFileObj(FileObj):
    """FileObj backed by an AmigaDOS file handle"""

    def __init__(self, file_mgr, fh):
        self.file_mgr = file_mgr
        self.fh = fh

    def read(self, size=-1):
        if size is None:
            size = -1
        data = self.fh.read(size)
        if data == -1:
            raise IOError("read failed on AmigaDOS file handle")
        return data

    def seek(self, offset, whence=0):
        pos = self.fh.seek(offset, whence)
        if pos < 0:
            raise IOError("seek failed on AmigaDOS file handle")
        return pos

    def tell(self):
        pos = self.fh.tell()
        if pos < 0:
            raise IOError("tell failed on AmigaDOS file handle")
        return pos

    def close(self):
        if self.fh is not None:
            fh = self.fh
            self.fh = None
            self.file_mgr.close(fh)

    def get_b_addr(self):
        if self.fh is None:
            return 0
        return self.fh.b_addr


class DosFileOpener(FileOpener):
    """open files through the DOS file manager using Amiga paths"""

    def __init__(self, file_mgr):
        self.file_mgr = file_mgr

    def open(self, ami_path, lock=None):
        fh = self.file_mgr.open(lock, str(ami_path), "rb")
        if fh is None:
            return None
        return DosFileObj(self.file_mgr, fh)
