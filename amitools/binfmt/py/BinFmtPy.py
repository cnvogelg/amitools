from ..BinImage import BIN_IMAGE_TYPE_PY, BinImage

#: how many bytes to look at when sniffing the shebang line
MAX_SHEBANG_LEN = 256


def read_shebang(fobj):
    """return the first line of ``fobj`` (without the newline) or b"".

    The file position is restored. At most :data:`MAX_SHEBANG_LEN` bytes are
    read so that sniffing a large binary is cheap.
    """
    pos = fobj.tell()
    try:
        data = fobj.read(MAX_SHEBANG_LEN)
    finally:
        fobj.seek(pos, 0)
    if not data:
        return b""
    nl = data.find(b"\n")
    if nl != -1:
        data = data[:nl]
    return data


def is_python_shebang(line):
    """check whether ``line`` is a ``#!`` shebang running a Python interpreter.

    Recognizes the direct form (``#!/usr/bin/python3``) as well as the ``env``
    form (``#!/usr/bin/env python3``), including options such as
    ``env -S python3 -u``. The match is case-insensitive and only accepts a
    token whose file name starts with ``python``.
    """
    if not line.startswith(b"#!"):
        return False
    try:
        text = line[2:].decode("latin-1").strip()
    except ValueError:
        return False
    for token in text.split():
        base = token.rsplit("/", 1)[-1].lower()
        if base == "python" or base.startswith("python"):
            return True
    return False


class BinFmtPy:
    """Detect and load Amiga Python commands.

    A command is a Python script whose first line is a Python shebang. This
    format is detection-only: it produces a :class:`BinImage` without segments
    and keeps the script source in ``file_data``. The stub that makes the
    script runnable is synthesized later by ``vamos.cmdcore``.
    """

    def is_image(self, path):
        """check if a given file is a Python command"""
        with open(path, "rb") as f:
            return self.is_image_fobj(f)

    def is_image_fobj(self, fobj):
        """check if a given fobj is a Python command"""
        return is_python_shebang(read_shebang(fobj))

    def load_image(self, path):
        """load a BinImage from a Python file given via path"""
        with open(path, "rb") as f:
            return self.load_image_fobj(f)

    def load_image_fobj(self, fobj):
        """load a BinImage from a Python file given via file object"""
        pos = fobj.tell()
        try:
            source = fobj.read()
        finally:
            fobj.seek(pos, 0)
        bi = BinImage(BIN_IMAGE_TYPE_PY)
        bi.set_file_data(source)
        return bi


# mini test
if __name__ == "__main__":
    import sys

    bf = BinFmtPy()
    for a in sys.argv[1:]:
        if bf.is_image(a):
            print("loading", a)
            bi = bf.load_image(a)
            print(bi, len(bi.get_file_data()), "bytes")
        else:
            print("NO PY:", a)
