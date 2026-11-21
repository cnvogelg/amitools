import argparse

from amitools.vamos.cfg import DiskParser, VamosMainParser


def cfg_disk_default_test():
    dp = DiskParser()
    assert dp.get_cfg_dict() == {"disks": None}


def cfg_disk_dict_test():
    dp = DiskParser()
    dp.parse_config({"disks": ["disk0.hdf", "disk1.hdf"]}, "dict")
    assert dp.get_cfg_dict() == {"disks": ["disk0.hdf", "disk1.hdf"]}


def cfg_disk_args_test():
    dp = DiskParser()
    ap = argparse.ArgumentParser()
    dp.setup_args(ap)
    args = ap.parse_args(
        [
            "--disk",
            "disk0.hdf",
            "--disk",
            "/tmp/disk,with,commas.hdf",
        ]
    )
    dp.parse_args(args)
    assert dp.get_cfg_dict() == {"disks": ["disk0.hdf", "/tmp/disk,with,commas.hdf"]}


def cfg_disk_keeps_options_comma_safe_test():
    # a comma inside the per-disk option list must not split into two disks
    dp = DiskParser()
    ap = argparse.ArgumentParser()
    dp.setup_args(ap)
    args = ap.parse_args(
        [
            "--disk",
            "floppy.adf?name=DF0",
            "--disk",
            "work.hdf?rw,bs=512",
        ]
    )
    dp.parse_args(args)
    assert dp.get_cfg_dict() == {"disks": ["floppy.adf?name=DF0", "work.hdf?rw,bs=512"]}


def cfg_disk_dict_args_test():
    dp = DiskParser()
    dp.parse_config({"disks": ["disk0.hdf"]}, "dict")
    ap = argparse.ArgumentParser()
    dp.setup_args(ap)
    args = ap.parse_args(["--disk", "disk1.hdf"])
    dp.parse_args(args)
    assert dp.get_cfg_dict() == {"disks": ["disk0.hdf", "disk1.hdf"]}


def cfg_vamos_disk_args_test():
    vmp = VamosMainParser()
    assert vmp.parse(args=["--disk", "disk0.hdf", "bin"])
    assert vmp.get_disk_dict() == {"disks": ["disk0.hdf"]}


def cfg_disk_short_args_test():
    # -D is a shortcut for --disk and appends in order
    dp = DiskParser()
    ap = argparse.ArgumentParser()
    dp.setup_args(ap)
    args = ap.parse_args(["-D", "disk0.hdf", "--disk", "disk1.hdf"])
    dp.parse_args(args)
    assert dp.get_cfg_dict() == {"disks": ["disk0.hdf", "disk1.hdf"]}


def cfg_vamos_disk_short_args_test():
    vmp = VamosMainParser()
    assert vmp.parse(args=["-D", "disk0.hdf", "bin"])
    assert vmp.get_disk_dict() == {"disks": ["disk0.hdf"]}
