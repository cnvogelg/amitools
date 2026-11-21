"""Per-disk option syntax on ``--disk`` (HANDLER.md step 25a).

A ``--disk`` value is ``IMAGE[?key=val,key=val]``. The tests pin the path-only
case, the read/write override, the raw device name and type keys, comma
handling, and the rejection of unknown keys or a ``?`` inside the path.
"""

import pytest

from amitools.vamos.disk import DiskSpec


def disk_spec_path_only_test():
    spec = DiskSpec.parse("floppy.adf")
    assert spec.path == "floppy.adf"
    assert spec.options == {}
    assert spec.read_only is None


def disk_spec_read_write_test():
    assert DiskSpec.parse("work.hdf?rw").read_only is False
    assert DiskSpec.parse("work.hdf?ro").read_only is True
    # an explicit value converts like a volume spec
    assert DiskSpec.parse("work.hdf?rw=true").read_only is False
    assert DiskSpec.parse("work.hdf?rw=false").read_only is True
    assert DiskSpec.parse("work.hdf?ro=false").read_only is False
    with pytest.raises(ValueError, match="both rw and ro"):
        DiskSpec.parse("work.hdf?rw,ro")


def disk_spec_options_test():
    spec = DiskSpec.parse("work.hdf?name=DH9,type=hdf,bs=512,chs=(10,1,32),algo=2")
    assert spec.path == "work.hdf"
    assert spec.options == {
        "name": "DH9",
        "type": "hdf",
        "bs": "512",
        "chs": "10,1,32",
        "algo": "2",
    }


def disk_spec_keeps_commas_in_options_test():
    # a nested value keeps its commas: chs=(c,h,s)
    spec = DiskSpec.parse("disk.hdf?chs=(10,1,32)")
    assert spec.options == {"chs": "10,1,32"}


def disk_spec_part_option_test():
    # ``part`` selects an RDB partition and stays in the factory options
    spec = DiskSpec.parse("work.hdf?part=DH1,rw")
    assert spec.path == "work.hdf"
    assert spec.read_only is False
    assert spec.factory_options() == {"part": "DH1"}


def disk_spec_comma_in_path_test():
    # a comma before the '?' belongs to the path
    spec = DiskSpec.parse("/tmp/disk,with,commas.hdf?rw")
    assert spec.path == "/tmp/disk,with,commas.hdf"
    assert spec.read_only is False


def disk_spec_question_mark_in_path_test():
    # a '?' always starts the option list, so it cannot appear in a path
    with pytest.raises(ValueError, match="unknown disk option"):
        DiskSpec.parse("weird?name.hdf?rw")


def disk_spec_unknown_key_test():
    with pytest.raises(ValueError, match="unknown disk option"):
        DiskSpec.parse("work.hdf?size=10MiB")


def disk_spec_empty_path_test():
    with pytest.raises(ValueError, match="no image path"):
        DiskSpec.parse("?rw")


def disk_spec_factory_options_strips_mode_test():
    spec = DiskSpec.parse("work.hdf?rw,bs=1024")
    assert spec.factory_options() == {"bs": "1024"}
