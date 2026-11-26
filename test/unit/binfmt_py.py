import io

from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.BinImage import BIN_IMAGE_TYPE_PY
from amitools.binfmt.py import BinFmtPy, is_python_shebang, read_shebang


# ----- is_python_shebang -----


def binfmt_py_shebang_yes_test():
    yes = [
        b"#!/usr/bin/env python3",
        b"#!/usr/bin/python",
        b"#!/usr/bin/python3.11",
        b"#!/usr/bin/env -S python3 -u",
        b"#!python",
        b"#!/usr/bin/PYTHON3",
        b"#!/usr/bin/env python\n",
        b"#!/usr/bin/python3\r\n",
    ]
    for line in yes:
        assert is_python_shebang(line), line


def binfmt_py_shebang_no_test():
    no = [
        b"",
        b"#python",
        b"import os",
        b"#!/bin/sh",
        b"#!/usr/bin/perl",
        b"#!/usr/bin/env ruby",
        b"#!/usr/bin/notpython",
        b"#!/usr/bin/env",
        b"\x7fELF\x02\x01\x01\x00",
    ]
    for line in no:
        assert not is_python_shebang(line), line


def binfmt_py_shebang_notpython_test():
    # "notpython" contains "python" but is not a python interpreter
    assert not is_python_shebang(b"#!/usr/bin/notpython")
    # a path token is compared by its file name only
    assert is_python_shebang(b"#!/opt/py/python3")


# ----- read_shebang -----


def binfmt_py_read_shebang_test():
    fobj = io.BytesIO(b"#!/bin/sh\necho hi\n")
    assert read_shebang(fobj) == b"#!/bin/sh"
    # position restored
    assert fobj.tell() == 0


def binfmt_py_read_shebang_no_newline_test():
    fobj = io.BytesIO(b"#!python")
    assert read_shebang(fobj) == b"#!python"


def binfmt_py_read_shebang_empty_test():
    fobj = io.BytesIO(b"")
    assert read_shebang(fobj) == b""


def binfmt_py_read_shebang_max_test():
    line = b"#!" + b"a" * 1000
    fobj = io.BytesIO(line)
    got = read_shebang(fobj)
    assert len(got) == 256
    assert got == line[:256]


# ----- BinFmtPy file API -----


def binfmt_py_is_image_test(tmp_path):
    p = tmp_path / "hello.py"
    p.write_bytes(b"#!/usr/bin/env python3\ndef main(ctx, a, n):\n    return 0\n")
    bf = BinFmtPy()
    assert bf.is_image(str(p))
    # position is restored after sniffing
    with open(p, "rb") as f:
        assert bf.is_image_fobj(f)
        assert f.tell() == 0


def binfmt_py_is_image_no_test(tmp_path):
    p = tmp_path / "plain.py"
    p.write_bytes(b"import os\ndef main(ctx, a, n):\n    return 0\n")
    bf = BinFmtPy()
    assert not bf.is_image(str(p))


def binfmt_py_load_image_test(tmp_path):
    source = b"#!/usr/bin/python3\ndef main(ctx, a, n):\n    return 7\n"
    p = tmp_path / "cmd.py"
    p.write_bytes(source)
    bi = BinFmtPy().load_image(str(p))
    assert bi.file_type == BIN_IMAGE_TYPE_PY
    assert bi.get_segments() == []
    assert bi.get_file_data() == source


def binfmt_py_load_image_restore_test(tmp_path):
    source = b"#!/usr/bin/python3\n"
    p = tmp_path / "cmd.py"
    p.write_bytes(source)
    with open(p, "rb") as f:
        bi = BinFmtPy().load_image_fobj(f)
        # the position is restored
        assert f.tell() == 0
    assert bi.get_file_data() == source


# ----- BinFmt integration -----


def binfmt_py_binfmt_detect_test(tmp_path):
    p = tmp_path / "cmd.py"
    p.write_bytes(b"#!/usr/bin/env python3\ndef main(ctx, a, n):\n    return 0\n")
    bf = BinFmt()
    assert bf.is_image(str(p))
    fmt = bf.get_format(str(p))
    assert isinstance(fmt, BinFmtPy)


def binfmt_py_binfmt_load_test(tmp_path):
    source = b"#!/usr/bin/python\ndef main(ctx, a, n):\n    return 0\n"
    p = tmp_path / "cmd.py"
    p.write_bytes(source)
    bf = BinFmt()
    bi = bf.load_image(str(p))
    assert bi is not None
    assert bi.file_type == BIN_IMAGE_TYPE_PY
    assert bi.get_file_data() == source


def binfmt_py_binfmt_no_test(tmp_path):
    p = tmp_path / "plain.py"
    p.write_bytes(b"def main(ctx, a, n):\n    return 0\n")
    bf = BinFmt()
    assert not bf.is_image(str(p))
    assert bf.load_image(str(p)) is None
