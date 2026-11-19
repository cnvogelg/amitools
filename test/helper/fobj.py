from amitools.vamos.loader import FileOpener, StreamFileObj


class HostFileOpener(FileOpener):
    """test opener mapping Amiga paths to host files"""

    def __init__(self, files=None):
        self.files = dict(files) if files else {}
        self.opened = []

    def add(self, ami_path, sys_path):
        self.files[str(ami_path)] = str(sys_path)

    def open(self, ami_path, lock=None):
        sys_path = self.files.get(str(ami_path), str(ami_path))
        try:
            stream = open(sys_path, "rb")
        except OSError:
            return None
        fobj = StreamFileObj(stream)
        self.opened.append(fobj)
        return fobj


def load_sys_lib(loader, segload, sys_bin_file, run_sp=None):
    """test helper: load a native lib from a host path"""
    try:
        stream = open(sys_bin_file, "rb")
    except OSError:
        return 0, 0
    fobj = StreamFileObj(stream)
    try:
        seglist_baddr = segload.load_seglist(fobj, name=str(sys_bin_file))
    finally:
        fobj.close()
    if seglist_baddr:
        return loader.init_lib(seglist_baddr, str(sys_bin_file), run_sp=run_sp)
    return 0, 0
