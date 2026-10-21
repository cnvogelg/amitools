import pytest

from amitools.fs.FSString import FSString


@pytest.mark.parametrize("value", range(256))
def fs_string_latin1_roundtrip_test(value):
    data = bytes([value])
    assert FSString(data).get_ami_str() == data
    assert FSString(data.decode("latin-1")).get_ami_str() == data


def fs_string_decomposed_unicode_test():
    assert FSString("Ha\u0308llo").get_ami_str() == b"H\xe4llo"
    assert FSString("Ha\u0308llo".encode("utf-8"), "utf-8").get_ami_str() == b"H\xe4llo"


def fs_string_unrepresentable_unicode_test():
    with pytest.raises(UnicodeEncodeError):
        FSString("\u2044").get_ami_str()
