"""Scan an ADF image an visit all files"""

import io

from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.ADFSVolume import ADFSVolume


class ADFSScanner:
    def __init__(self):
        self.factory = BlkDevFactory()

    def can_handle(self, scan_file):
        base_name = scan_file.get_basename().lower()
        for ext in self.factory.EXT_MAP:
            if base_name.endswith(ext):
                return True
        return False

    def handle(self, scan_file, scanner):
        if scan_file.is_seekable():
            sf = scan_file
        else:
            sf = scanner.promote_scan_file(scan_file, seekable=True)
        # create blkdev
        blkdev = self.factory.open(sf.get_local_path(), fobj=sf.get_fobj())
        # create volume
        volume = ADFSVolume(blkdev)
        volume.open()
        # scan volume
        node = volume.get_root_dir()
        ok = self._scan_node(sf, scanner, node)
        # done
        volume.close()
        blkdev.close()
        return ok

    def _scan_node(self, scan_file, scanner, node):
        if node.is_dir():
            # recurse into dir
            entries = node.get_entries()
            for e in entries:
                ok = self._scan_node(scan_file, scanner, e)
                if not ok:
                    return False
            return True
        elif node.is_file():
            # read file in ram fobj
            data = node.get_file_data()
            node.flush()
            size = len(data)
            path = node.get_node_path_name().get_unicode()
            fobj = io.StringIO(data)
            sf = scan_file.create_sub_path(path, fobj, size, True, False)
            ok = scanner.scan_obj(sf)
            sf.close()
            return True


# mini test
if __name__ == "__main__":
    import sys
    from .FileScanner import FileScanner

    ifs = ["*.txt"]

    def handler(scan_file):
        print(scan_file)
        return True

    def skip_handler(scan_file):
        print(("SKIP:", scan_file))
        return True

    def error_handler(scan_file, error):
        print(("FAILED:", scan_file, error))
        raise error

    scanners = [ADFSScanner()]
    fs = FileScanner(
        handler,
        ignore_filters=ifs,
        error_handler=error_handler,
        scanners=scanners,
        skip_handler=skip_handler,
    )
    for a in sys.argv[1:]:
        fs.scan(a)
