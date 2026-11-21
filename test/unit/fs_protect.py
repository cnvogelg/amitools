"""ADFS protection mask tests.

``fib_Protection`` is a full 32-bit long: the owner bits are active low and
spelled ``HSPArwed``, while the group (bits 8-11), other (bits 12-15) and
SUID (bit 31) bits are active high and have no letter. ``ProtectFlags`` keeps
the 8-char owner string for the plain listing and exposes the high bits as a
hex mask that a detailed listing shows only when they are set.
"""

import pytest

from amitools.fs import DosType
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.ProtectFlags import ProtectFlags
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice


def make_volume(tmp_path, name="work", dos_type=DosType.DOS5):
    blkdev = ADFBlockDevice(str(tmp_path / "v.adf"))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString(name), dos_type=dos_type)
    return volume, blkdev


def reopen(blkdev):
    volume = ADFSVolume(blkdev)
    volume.open()
    return volume


def fs_protect_flags_owner_str_test():
    # the owner form stays 8 chars, whatever high bits are set
    assert str(ProtectFlags(0)) == "----rwed"
    assert str(ProtectFlags(0xFFFF_FFFF)) == "hspa----"
    # a high bit outside the owner byte does not change the owner form
    assert str(ProtectFlags(0x8000_8000)) == "----rwed"
    assert ProtectFlags(0).short_str() == "rwed"
    assert ProtectFlags.empty_string == "--------"


def fs_protect_flags_extra_test():
    # a mask without group/other/SUID bits has nothing extra to show
    assert not ProtectFlags(0).has_extra()
    assert not ProtectFlags(0x0000_00FF).has_extra()
    # group, other and SUID bits all count as extra
    assert ProtectFlags(ProtectFlags.FIBF_GRP_READ).has_extra()
    assert ProtectFlags(ProtectFlags.FIBF_OTR_WRITE).has_extra()
    assert ProtectFlags(ProtectFlags.FIBF_SUID).has_extra()
    assert ProtectFlags(0x8000_8000).extra_str() == "0x80008000"
    assert ProtectFlags(0x0000_0800).extra_str() == "0x00000800"


def fs_protect_flags_bin_str_test():
    # the binary form covers the whole 32-bit mask
    assert len(ProtectFlags(0).bin_str()) == 32
    assert ProtectFlags(0).bin_str() == "0" * 32
    assert ProtectFlags(1).bin_str() == "0" * 31 + "1"
    assert ProtectFlags(ProtectFlags.FIBF_SUID).bin_str() == "1" + "0" * 31


def fs_protect_flags_parse_full_test():
    # the owner form round-trips; group/other bits are left untouched
    p = ProtectFlags()
    p.parse_full("hsparwed")
    assert str(p) == "hsparwed"
    p.parse_full("----rwed")
    assert p.get_mask() == 0
    assert str(p) == "----rwed"


@pytest.mark.parametrize("dos_type", [DosType.DOS0, DosType.DOS5])
def fs_protect_volume_roundtrip_test(tmp_path, dos_type):
    volume, blkdev = make_volume(tmp_path, dos_type=dos_type)
    volume.write_file(b"x", FSString("f"))
    node = volume.get_path_name(FSString("f"))
    node.change_protect(0x0000_800F)
    check = reopen(blkdev)
    assert check.get_path_name(FSString("f")).meta_info.get_protect() == 0x0000_800F


def fs_protect_listing_test(tmp_path):
    volume, _ = make_volume(tmp_path)
    volume.write_file(b"x", FSString("f"))
    node = volume.get_path_name(FSString("f"))
    # a plain owner mask adds no hex to either listing
    assert "0x" not in node.get_list_str()
    assert "0x" not in node.get_list_str(detail=True)
    # a mask with high bits shows the hex mask in both listings
    node.change_protect(0x0000_800F)
    assert "0x0000800f" in node.get_list_str()
    assert "0x0000800f" in node.get_list_str(detail=True)
