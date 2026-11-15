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
