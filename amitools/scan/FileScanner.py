# scan a set of file


import os
import fnmatch
import tempfile

from .ScanFile import ScanFile


class FileScanner:
    def __init__(
        self,
        handler=None,
        ignore_filters=None,
        scanners=None,
        error_handler=None,
        ram_bytes=10 * 1024 * 1024,
        skip_handler=None,
        warning_handler=None,
    ):
        """the handler will be called with all the scanned files.
        the optional ignore_filters contains a list of glob pattern to
        ignore file names"""
        self.handler = handler
        self.error_handler = error_handler
        self.warning_handler = warning_handler
        self.skip_handler = skip_handler
        self.ignore_filters = ignore_filters
        self.scanners = scanners
        self.ram_bytes = ram_bytes

    def scan(self, path):
        """start scanning a path. either a file or directory"""
        if os.path.isdir(path):
            return self._scan_dir(path)
        elif os.path.isfile(path):
            return self._scan_file(path)
        else:
            return True

    def scan_obj(self, scan_file, check_ignore=True):
        """pass a ScanFile to check"""
        if check_ignore and self._is_ignored(scan_file.get_local_path()):
            return False
        # does a scanner match?
        sf = scan_file
        sc = self.scanners
        if sc is not None:
            for s in sc:
                if s.can_handle(sf):
                    ok = s.handle(sf, self)
                    sf.close()
                    return ok
        # no match call user's handler
        ok = self._call_handler(sf)
        sf.close()
        return ok

    def _scan_dir(self, path):
        if self._is_ignored(path):
            return True
        for root, dirs, files in os.walk(path):
            for name in files:
                if not self._scan_file(os.path.join(root, name)):
                    return False
            for name in dirs:
                if not self._scan_dir(os.path.join(root, name)):
                    return False
        return True

    def _scan_file(self, path):
        if self._is_ignored(path):
            return True
        # build a scan file
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as fobj:
                sf = ScanFile(path, fobj, size, True, True)
                return self.scan_obj(sf, False)
        except IOError as e:
            eh = self.error_handler
            if eh is not None:
                sf = ScanFile(path, None, 0)
                return eh(sf, e)
            else:
                # ignore error
                return True

    def _is_ignored(self, path):
        if self.ignore_filters is not None:
            base = os.path.basename(path)
            for f in self.ignore_filters:
                if fnmatch.fnmatch(base, f):
                    return True
        return False

    def _call_handler(self, scan_file):
        if self.handler is not None:
            return self.handler(scan_file)
        else:
            return True

    def _call_skip_handler(self, scan_file):
        if self.skip_handler is not None:
            return self.skip_handler(scan_file)
        else:
            return True

    def promote_scan_file(self, scan_file, seekable=False, file_based=False):
        if not seekable and not file_base:
            return scan_file
        fb = file_based
        if not fb and seekable and scan_file.size > self.ram_bytes:
            fb = True
        sf = scan_file.create_clone(seekable, fb)
        scan_file.close()
        return sf

    def warn(self, scan_file, msg):
        wh = self.warning_handler
        if wh is not None:
            wh(scan_file, msg)


# mini test
if __name__ == "__main__":
    import sys

    ifs = ["*.txt"]

    def handler(scan_file):
        print(scan_file)
        return True

    def error_handler(scan_file, error):
        print("FAILED:", scan_file, error)
        raise error

    fs = FileScanner(handler, ignore_filters=ifs, error_handler=error_handler)
    for a in sys.argv[1:]:
        fs.scan(a)
