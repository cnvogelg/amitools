"""Volume discovery failures must not hide failures locking the target."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.util.Win32Disk import _Disk


@pytest.mark.parametrize("failure", ["open", "extents"])
@pytest.mark.parametrize("code", [1, 2, 3, 5, 21, 50])
def unqueryable_volume_test(failure, code):
    error = OSError("unqueryable volume")
    error.winerror = code
    disk = _Disk.__new__(_Disk)
    disk.volume_handles = []
    api = disk.api = SimpleNamespace(
        volumes=lambda: ["unknown", "target"],
        GENERIC_READ=1, GENERIC_WRITE=2, LOCK_VOLUME=3, DISMOUNT_VOLUME=4,
        open=Mock(side_effect=[error if failure == "open" else 10, 20, 21]),
        volume_disks=Mock(side_effect=[error, {2}] if failure == "extents" else [{2}]),
        close=Mock(), ioctl=Mock(),
    )
    disk._lock_volumes(2)
    assert disk.volume_handles == [21]
    assert [c.args for c in api.ioctl.call_args_list] == [(21, 3), (21, 4)]
    assert [c.args for c in api.close.call_args_list] == (
        [(10,), (20,)] if failure == "extents" else [(20,)])


@pytest.mark.parametrize("failure", ["open", "lock", "dismount"])
def target_volume_failure_test(failure):
    error = OSError("target volume busy")
    disk = _Disk.__new__(_Disk)
    disk.volume_handles = []
    disk.api = SimpleNamespace(
        volumes=lambda: ["target"],
        GENERIC_READ=1, GENERIC_WRITE=2, LOCK_VOLUME=3, DISMOUNT_VOLUME=4,
        open=Mock(side_effect=[20, error if failure == "open" else 21]),
        volume_disks=lambda h: {2}, close=Mock(),
        ioctl=Mock(side_effect=[None, error] if failure == "dismount" else error),
    )
    with pytest.raises(OSError, match="target"):
        disk._lock_volumes(2)
