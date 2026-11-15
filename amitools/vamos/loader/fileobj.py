class FileObj(object):
    """binary file object as expected by the segment loader

    The interface follows a regular, seekable Python binary stream. The
    segment loader only relies on these calls, so it does not need to know
    whether the file lives on the host or is handled by AmigaDOS.
    """

    def read(self, size=-1):
        """read up to size bytes or all remaining bytes if size is negative"""
        raise NotImplementedError

    def seek(self, offset, whence=0):
        """seek to a new position and return it"""
        raise NotImplementedError

    def tell(self):
        """return the current file position"""
        raise NotImplementedError

    def close(self):
        """close the file"""
        raise NotImplementedError

    def get_b_addr(self):
        """return the AmigaDOS BPTR of the file handle or 0 if unknown"""
        return 0


class FileOpener(object):
    """open a file object at an Amiga path"""

    def open(self, ami_path, lock=None):
        """open ami_path read-only and return a FileObj or None on error"""
        raise NotImplementedError


class StreamFileObj(FileObj):
    """wrap a Python binary stream as FileObj"""

    def __init__(self, stream):
        self.stream = stream

    def read(self, size=-1):
        return self.stream.read(size)

    def seek(self, offset, whence=0):
        return self.stream.seek(offset, whence)

    def tell(self):
        return self.stream.tell()

    def close(self):
        self.stream.close()
