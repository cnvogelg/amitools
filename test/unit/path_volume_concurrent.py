import os

import pytest

from amitools.vamos.path.volume import Volume, VolumeManager


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
