from .elf.BinFmtELF import BinFmtELF
from .hunk.BinFmtHunk import BinFmtHunk


class BinFmt:
    def __init__(self):
        self.formats = [BinFmtHunk(), BinFmtELF()]

    def get_format(self, path):
        """get instance of BinFmt loader or None"""
        with open(path, "rb") as f:
            return self.get_format_fobj(f)

    def get_format_fobj(self, fobj):
        """get instance of BinFmt loader or None"""
        for f in self.formats:
            if f.is_image_fobj(fobj):
                return f
        return None

    def is_image(self, path):
        """check if a given file is a supported binary file"""
        with open(path, "rb") as f:
            return self.is_image_fobj(f)

    def is_image_fobj(self, fobj):
        """check if a given file is a supported binary file"""
        f = self.get_format_fobj(fobj)
        return f is not None

    def load_image(self, path):
        """load a binary file and return a BinImage. unknown format returns None"""
        with open(path, "rb") as f:
            return self.load_image_fobj(f)

    def load_image_fobj(self, fobj):
        """load a binary file and return a BinImage. unknown format returns None"""
        f = self.get_format_fobj(fobj)
        if f is not None:
            return f.load_image_fobj(fobj)
        else:
            return None


# mini test
if __name__ == "__main__":
    import sys

    bf = BinFmt()
    for a in sys.argv[1:]:
        ok = bf.is_image(a)
        bi = bf.load_image(a)
        print(a, ok, str(bi))
