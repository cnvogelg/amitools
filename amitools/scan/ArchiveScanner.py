import zipfile
import io

# optional lhafile
try:
    import lhafile
except ImportError:
    lhafile = None


class ArchiveScanner:
    """Scan archives and visit all files"""

    exts = []  # valid file extensions

    def _create_archive_obj(self, fobj, scanner):
        pass

    def _create_entry_scan_file(self, arc, info, sf):
        pass

    def can_handle(self, scan_file):
        base_name = scan_file.get_basename().lower()
        for ext in self.exts:
            if base_name.endswith(ext):
                return True
        return False

    def handle(self, scan_file, scanner):
        """scan a given archive file"""
        # ensure a seekable fobj
        if not scan_file.is_seekable():
            sf = scanner.promote_scan_file(scan_file, seekable=True)
        else:
            sf = scan_file
        # create archive obj
        arc = self._create_archive_obj(sf, scanner)
        if arc is None:
            return True  # simply ignore
        # get infos
        infos = arc.infolist()
        for info in infos:
            if info.file_size > 0:
                sf = self._create_entry_scan_file(arc, info, scan_file)
                ok = scanner.scan_obj(sf)
                sf.close()
                if not ok:
                    return False
        return True


class ZipScanner(ArchiveScanner):
    """Scan .zip Archives"""

    exts = [".zip"]

    def _create_archive_obj(self, sf, scanner):
        try:
            fobj = sf.get_fobj()
            return zipfile.ZipFile(fobj, "r")
        except Exception as e:
            scanner.warning(sf, "error reading archive: %s" % e)

    def _create_entry_scan_file(self, arc, info, scan_file):
        name = info.filename
        fobj = arc.open(info)
        size = info.file_size
        # its a non-seekable file
        return scan_file.create_sub_path(name, fobj, size, False, False)


class LhaScanner(ArchiveScanner):
    """Scan .lha/.lzh Archives"""

    exts = [".lha", ".lzh"]

    def _create_archive_obj(self, sf, scanner):
        if lhafile:
            try:
                fobj = sf.get_fobj()
                return lhafile.LhaFile(fobj, "r")
            except Exception as e:
                scanner.warning(sf, "error reading archive: %s" % e)
        else:
            scanner.warning(sf, "can't handle archive. missing 'lhafile' module.")

    def _create_entry_scan_file(self, arc, info, scan_file):
        data = arc.read(info.filename)
        fobj = io.StringIO(data)
        size = info.file_size
        name = info.filename
        return scan_file.create_sub_path(name, fobj, size, True, False)


# mini test
if __name__ == "__main__":
    import sys
    from .FileScanner import FileScanner

    ifs = ["*.txt"]

    def handler(scan_file):
        print(scan_file)
        return True

    def skip_handler(scan_file):
        print("SKIP:", scan_file)
        return True

    def error_handler(scan_file, error):
        print("FAILED:", scan_file, error)
        raise error

    scanners = [LhaScanner(), ZipScanner()]
    fs = FileScanner(
        handler,
        ignore_filters=ifs,
        error_handler=error_handler,
        scanners=scanners,
        skip_handler=skip_handler,
    )
    for a in sys.argv[1:]:
        fs.scan(a)
