"""Native handler block-device resolution (HANDLER.md step 24b).

A ``?handler=native`` volume references a ``--disk`` RDB partition through the
``DiskSession``: ``device`` names the DOS device node (``DH0``) that
``install_dos`` created, ``part`` the RDB partition directly. With neither set
the mount name is tried and the first partition is the fallback. The block
device the handler opens is always ``scsi.device``.
"""

from types import SimpleNamespace

from amitools.fs.FSString import FSString
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.disk import DiskSession
from amitools.vamos.handler.native import NativeConfig
from amitools.vamos.handler.native.blkdev import (
    DEFAULT_DEVICE,
    BlkDevGeometry,
    resolve_blkdev,
)


def _partition(name, index, env=None):
    return SimpleNamespace(name=name, index=index, dos_env=env or object())


def _session(*backends):
    """a minimal stand-in for DiskSession (unit -> backend)"""
    units = dict(enumerate(backends))
    return SimpleNamespace(
        get_units=lambda: tuple(sorted(units)),
        get_backend=lambda unit: units.get(unit),
    )


def _make_rdb(path):
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(320)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 32), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), (1, 9))
    raw.flush()
    rdisk.close()
    raw.close()


def handler_native_blkdev_device_name_test():
    env = object()
    session = _session(SimpleNamespace(partitions=[_partition("DH0", 0, env)]))
    # ``device`` names the DOS device node of a partition; the handler opens
    # scsi.device, not the DOS node
    spec = resolve_blkdev(session, NativeConfig({"device": "DH0"}), "WORK")
    assert spec.device == DEFAULT_DEVICE
    assert spec.unit == 0
    assert spec.geometry is env


def handler_native_blkdev_part_selector_test():
    env = object()
    session = _session(
        SimpleNamespace(partitions=[_partition("DH0", 0), _partition("DH1", 1, env)])
    )
    # ``part`` selects the RDB partition by index ...
    spec = resolve_blkdev(session, NativeConfig({"part": "1"}), "WORK")
    assert spec.unit == 0
    assert spec.geometry is env
    # ... or by name (``partition`` is an alias)
    spec = resolve_blkdev(session, NativeConfig({"partition": "DH0"}), "WORK")
    assert spec.geometry is not env


def handler_native_blkdev_mount_name_default_test():
    env = object()
    session = _session(SimpleNamespace(partitions=[_partition("DH0", 0, env)]))
    # the mount name is used when it matches a disk device
    spec = resolve_blkdev(session, NativeConfig({}), "DH0")
    assert spec.geometry is env


def handler_native_blkdev_first_partition_fallback_test():
    env = object()
    session = _session(
        SimpleNamespace(partitions=[]),
        SimpleNamespace(partitions=[_partition("DH1", 0, env)]),
    )
    # neither the mount name nor a selector matches: the first partition wins
    spec = resolve_blkdev(session, NativeConfig({}), "WORK")
    assert spec.unit == 1
    assert spec.geometry is env


def handler_native_blkdev_unit_override_test():
    env = object()
    session = _session(SimpleNamespace(partitions=[_partition("DH0", 0, env)]))
    # an explicit unit wins over the partition's unit
    spec = resolve_blkdev(session, NativeConfig({"device": "DH0", "unit": "3"}), "WORK")
    assert spec.unit == 3
    assert spec.geometry is env


def handler_native_blkdev_synthetic_fallback_test():
    # no disk session at all: a synthetic geometry keeps the handler starting
    spec = resolve_blkdev(None, NativeConfig({}), "WORK")
    assert spec.device == DEFAULT_DEVICE
    assert spec.unit == 0
    assert isinstance(spec.geometry, BlkDevGeometry)


def handler_native_blkdev_empty_session_test():
    session = _session(SimpleNamespace(partitions=[]))
    spec = resolve_blkdev(session, NativeConfig({}), "WORK")
    assert isinstance(spec.geometry, BlkDevGeometry)


def handler_native_blkdev_real_rdb_test(tmp_path):
    image = tmp_path / "disk.hdf"
    _make_rdb(image)
    session = DiskSession([image]).open()
    try:
        spec = resolve_blkdev(session, NativeConfig({"device": "DH0"}), "WORK")
        assert spec.unit == 0
        assert spec.geometry.low_cyl == 1
        assert spec.geometry.high_cyl == 9
    finally:
        session.close()
