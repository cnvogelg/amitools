"""Image-backed volumes.

A volume whose source is a *file* (not a directory) is a file system inside an
image (ADF/HDF/RDB): it defaults to the ``adfs`` handler and is never mapped to
the host file system.
"""

from amitools.fs import DosType
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.vamos.path import VolumeManager


def make_image(path, name="work"):
    blkdev = ADFBlockDevice(str(path))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString(name), dos_type=DosType.DOS0)
    volume.close()
    blkdev.close()
    return str(path)


def path_volume_image_detect_test(tmp_path):
    image = make_image(tmp_path / "disk.adf")
    v = VolumeManager()
    assert v.setup()
    vol = v.add_volume("work:" + image)
    assert vol
    # an image file source is image-backed and defaults to the adfs handler
    assert vol.is_image is True
    assert vol.cfg["handler"] == "adfs"
    assert vol.get_path() == image
    # an image volume has no host directory to map to/from
    assert v.ami_to_sys_path("work:foo") is None
    assert v.sys_to_ami_path(image) is None
    assert vol.create_rel_sys_path("sub") is None
    # setup/shutdown stay no-ops for the image volume
    assert v.setup()
    v.shutdown()


def path_volume_image_dir_source_test(tmp_path):
    d = tmp_path / "hostdir"
    d.mkdir()
    v = VolumeManager()
    v.setup()
    vol = v.add_volume("work:" + str(d))
    # a directory source stays a plain host volume
    assert vol.is_image is False
    assert "handler" not in vol.cfg
    assert vol.create_rel_sys_path("sub") == str(d / "sub")
    v.shutdown()


def path_volume_image_explicit_handler_test(tmp_path):
    image = make_image(tmp_path / "disk.adf")
    v = VolumeManager()
    # an explicit non-adfs handler is not overridden
    vol = v.add_volume("work:" + image + "?handler=hostfs")
    assert vol is not None
    assert vol.is_image is False
    assert vol.cfg["handler"] == "hostfs"


def path_volume_image_options_test(tmp_path):
    image = make_image(tmp_path / "disk.adf")
    v = VolumeManager()
    v.setup()
    # ?img/?part reach the handler factory through the volume config
    vol = v.add_volume("work:" + image + "?img=adf_hd,part=1")
    assert vol.is_image is True
    assert vol.cfg["img"] == "adf_hd"
    assert vol.cfg["part"] == "1"
    v.shutdown()
