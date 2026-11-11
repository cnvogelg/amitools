import errno
import os

import pytest

from amitools.vamos.path.volume import Volume, VolumeManager


def path_volume_overlapping_temp_test(tmp_path):
    base = tmp_path / "ram"
    first = Volume("ram", str(base), {"temp": True})
    second = Volume("ram", str(base), {"temp": True})
    assert first.setup()
    assert second.setup()
    assert first.get_path() != second.get_path()
    survivor = os.path.join(second.get_path(), "data")
    with open(survivor, "wb") as stream:
        stream.write(b"keep me")
    first.shutdown()
    with open(survivor, "rb") as stream:
        assert stream.read() == b"keep me"
    second.shutdown()
    assert not base.exists()


def path_volume_temp_preserves_base_contents_test(tmp_path):
    base = tmp_path / "ram"
    base.mkdir()
    original = base / "original"
    original.write_bytes(b"existing data")
    volume = Volume("ram", str(base), {"temp": True})
    assert volume.setup()
    volume.shutdown()
    assert original.read_bytes() == b"existing data"
    assert list(base.iterdir()) == [original]


def path_volume_temp_base_is_file_test(tmp_path):
    base = tmp_path / "ram"
    base.write_bytes(b"existing data")
    volume = Volume("ram", str(base), {"temp": True})
    assert not volume.setup()
    assert base.read_bytes() == b"existing data"


def path_volume_temp_base_removed_during_setup_test(tmp_path, monkeypatch):
    import tempfile

    base = tmp_path / "ram"
    mkdtemp = tempfile.mkdtemp
    calls = 0

    def competing_cleanup(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            os.rmdir(kwargs["dir"])
            raise FileNotFoundError(errno.ENOENT, "base removed by another instance")
        return mkdtemp(*args, **kwargs)

    monkeypatch.setattr(tempfile, "mkdtemp", competing_cleanup)
    volume = Volume("ram", str(base), {"temp": True})
    assert volume.setup()
    assert calls == 2
    volume.shutdown()
    assert not base.exists()


@pytest.mark.parametrize("operation", ["base", "volume", "assign"])
def path_volume_shared_creation_race_test(tmp_path, monkeypatch, operation):
    path = str(tmp_path / operation)
    makedirs = os.makedirs
    raced = False

    def competing_creation(name, *args, **kwargs):
        nonlocal raced
        if name == path and not raced:
            raced = True
            makedirs(name)
        return makedirs(name, *args, **kwargs)

    monkeypatch.setattr(os, "makedirs", competing_creation)
    if operation == "base":
        manager = VolumeManager(path)
        assert manager._setup_base_dir() == path
    elif operation == "volume":
        volume = Volume("system", path, {"create": True})
        assert volume.setup()
    else:
        volume = Volume("system", str(tmp_path))
        assert volume.create_rel_sys_path(operation) == path
    assert raced
    assert os.path.isdir(path)
