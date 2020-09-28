import os
import io


class ScanFile:
    """a file that is currently scanned"""

    def __init__(self, path, fobj, size, seekable=True, file_based=True):
        """create a scan file from a host file object"""
        if type(path) is list:
            self.paths = path
        else:
            self.paths = [path]
        self.fobj = fobj
        self.size = size
        self.seekable = seekable
        self.file_based = file_based

    def __str__(self):
        return "[%s:%d, seekable=%s, file_based=%s, fobj=%s]" % (
            self.get_path(),
            self.size,
            self.seekable,
            self.file_based,
            self.fobj.__class__.__name__,
        )

    def __repr__(self):
        return self.__str__()

    def is_seekable(self):
        return self.seekable

    def is_file_based(self):
        return self.file_based

    def get_path(self):
        return ";".join(self.paths)

    def get_local_path(self):
        return self.paths[-1]

    def get_basename(self):
        return os.path.basename(self.paths[-1])

    def get_fobj(self):
        return self.fobj

    def is_host_path(self):
        return len(self.paths) == 1

    def close(self):
        self.fobj.close()

    def create_sub_path(self, sub_path, fobj, size, seekable, file_based):
        paths = self.paths[:]
        paths.append(sub_path)
        return ScanFile(paths, fobj, size, seekable, file_based)

    def create_clone(self, seekable, file_based):
        src_fobj = self.fobj
        # create a temp file
        if file_based:
            fobj = tempfile.TemporaryFile()
            # copy original file
            blk_size = 4096
            while True:
                buf = src_fobj.read(blk_size)
                if len(buf) == 0:
                    break
                fobj.write(buf)
        # create a string buffer
        else:
            data = src_fobj.read()
            fobj = io.StringIO(data)
        # close old scan file
        src_fobj.close()
        # create promoted file
        return ScanFile(self.paths, fobj, self.size, seekable, file_based)
