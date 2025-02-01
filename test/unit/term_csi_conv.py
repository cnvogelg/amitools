from amitools.vamos.lib.dos.terminal import (
    CsiEscConverter,
    EscCsiConverter,
    ESC,
    CSI,
    CSI_ESC_SEQ,
)
from io import BytesIO


def term_csi_conv_csi_to_esc_test():
    conv = CsiEscConverter()
    # no conversion
    txt = b"hello, world!"
    assert conv.convert(txt) == txt
    # only esc
    txt = ESC
    assert conv.convert(txt) == txt
    # CSI to ESC
    txt = CSI
    assert conv.convert(txt) == CSI_ESC_SEQ
    # misc text
    txt = b"hello" + CSI + b"world!"
    out = b"hello" + CSI_ESC_SEQ + b"world!"
    assert conv.convert(txt) == out


def setup(data):
    reader = BytesIO(data)
    conv = EscCsiConverter(reader)
    return conv


def term_csi_conv_esc_to_csi_test():
    # no conversion
    txt = b"hello, world!"
    conv = setup(txt)
    assert conv.read(100) == txt
    # esc no conversion
    txt = b"hello" + ESC + b"world!"
    conv = setup(txt)
    assert conv.read(100) == txt
    # esc -> CSI
    txt = CSI_ESC_SEQ
    conv = setup(txt)
    assert conv.read(100) == CSI
    # esc inside
    txt = b"hello" + CSI_ESC_SEQ + b"world!"
    out = b"hello" + CSI + b"world!"
    conv = setup(txt)
    assert conv.read(100) == out
    # esc -> CSI at the border
    txt = b"hello" + CSI_ESC_SEQ + b"world!"
    out = b"hello" + CSI
    conv = setup(txt)
    assert conv.read(6) == out
    assert conv.read(100) == b"world!"
    # esc no CSI at the border
    txt = b"hello" + ESC + b"world!"
    out = b"hello" + ESC
    conv = setup(txt)
    assert conv.read(6) == out
    assert conv.read(100) == b"world!"
    # esc at end
    txt = b"hello" + ESC
    conv = setup(txt)
    assert conv.read(6) == txt
    assert conv.read(100) == b""
