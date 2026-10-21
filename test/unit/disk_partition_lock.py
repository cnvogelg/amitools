"""Exercise native locks across handles, processes, and pathname aliases."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from amitools.vamos.disk import HostFileLock, PartitionFileLock


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "disk.hdf"
    path.write_bytes(bytes(4096))
    return path


def probe(image, *, offset=512, length=512, read_only=False, whole=False):
    script = """
import sys
from amitools.vamos.disk import HostFileLock, PartitionFileLock
path, offset, length, read_only, whole = sys.argv[1:]
lock = (HostFileLock if whole == 'True' else PartitionFileLock)(
    path, read_only=read_only == 'True')
try:
    lock.acquire()
    if whole != 'True':
        lock.lock_range(int(offset), int(length))
except OSError:
    sys.exit(23)
finally:
    lock.release()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    result = subprocess.run(
        [sys.executable, "-c", script, str(image), str(offset), str(length),
         str(read_only), str(whole)], env=env, capture_output=True,
        text=True, timeout=15)
    assert result.returncode in (0, 23), result.stderr
    return result.returncode == 0


@pytest.mark.parametrize("read_only", [True, False])
def partition_lock_conflicts_test(image, read_only):
    lock = PartitionFileLock(image, read_only=read_only)
    lock.acquire()
    try:
        lock.lock_range(512, 512)
        # Bootstrap opens and closes separate image handles. Their closure
        # must not drop our lock, as it would with POSIX process locks.
        with open(image, "rb") as stream:
            assert len(stream.read()) == 4096
        assert probe(image, offset=1024)
        assert probe(image, offset=0)
        assert not probe(image)
        assert not probe(image, offset=1023)
        assert probe(image, read_only=True) == read_only
        assert not probe(image, whole=True)
        alias = image.with_name("alias.hdf")
        os.link(image, alias)
        assert not probe(alias)
        other = PartitionFileLock(image, read_only=False)
        other.acquire()
        try:
            with pytest.raises(OSError):
                other.lock_range(512, 512)
        finally:
            other.release()
    finally:
        lock.release()
        lock.release()
    assert probe(image)
    assert probe(image, whole=True)


def whole_image_blocks_partition_guard_test(image):
    lock = HostFileLock(image)
    lock.acquire()
    try:
        assert not probe(image)
        other = PartitionFileLock(image)
        with pytest.raises(OSError):
            other.acquire()
        assert not other.is_locked
    finally:
        lock.release()
    assert probe(image)


def partition_guard_blocks_raw_before_range_test(image):
    lock = PartitionFileLock(image)
    lock.acquire()
    try:
        assert not probe(image, whole=True)
        for offset, length in [(-1, 1), (0, 0), (0, -1), (2**63, 1)]:
            with pytest.raises(ValueError):
                lock.lock_range(offset, length)
        lock.lock_range(4096, 512)  # Truncated images still get range locks.
        with pytest.raises(RuntimeError):
            lock.lock_range(512, 512)
    finally:
        lock.release()


def partition_process_exit_releases_locks_test(image):
    script = """
import os, sys
from amitools.vamos.disk import PartitionFileLock
lock = PartitionFileLock(sys.argv[1], read_only=False)
lock.acquire()
lock.lock_range(512, 512)
os._exit(0)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    subprocess.run([sys.executable, "-c", script, str(image)],
                   env=env, check=True, timeout=15)
    assert probe(image)
    assert probe(image, whole=True)
