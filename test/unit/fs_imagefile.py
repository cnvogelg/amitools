"""Image-file buffering must respect Windows mandatory byte-range locks."""

import io
import sys
from types import SimpleNamespace

import pytest

from amitools.fs.blkdev import ImageFile as imagefile_module
from amitools.fs.blkdev.ImageFile import ImageFile
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.vamos.disk import HostFileLock


@pytest.mark.parametrize("platform", ["win32", "linux"])
@pytest.mark.parametrize("read_only", [True, False])
def image_file_platform_buffering_test(tmp_path, monkeypatch, platform, read_only):
    path = tmp_path / "image.hdf"
    path.write_bytes(b"a" * 512 + b"z" * 512)
    # Replace the module reference, not global sys.platform, so pytest and
    # pathlib keep using the actual host platform.
    monkeypatch.setattr(
        imagefile_module, "sys", SimpleNamespace(platform=platform), raising=False
    )
    image = ImageFile(str(path), read_only=read_only)
    image.open()
    try:
        assert isinstance(image.fobj, io.FileIO) == (platform == "win32")
        assert image.read_blk(0) == b"a" * 512
        assert image.read_blk(1) == b"z" * 512
        if not read_only:
            image.write_blk(1, b"w" * 512)
            assert image.read_blk(1) == b"w" * 512
    finally:
        image.close()


def image_file_preserves_supplied_stream_test(monkeypatch):
    monkeypatch.setattr(
        imagefile_module, "sys", SimpleNamespace(platform="win32"), raising=False
    )
    stream = io.BytesIO(b"a" * 1024)
    image = ImageFile("unused", fobj=stream)
    image.open()
    try:
        assert image.fobj is stream
        assert image.read_blk(1) == b"a" * 512
        image.write_blk(1, b"z" * 512)
        assert stream.getvalue() == b"a" * 512 + b"z" * 512
    finally:
        image.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows mandatory locks")
@pytest.mark.parametrize("read_only", [True, False])
def raw_block_device_windows_locked_image_test(tmp_path, read_only):
    path = tmp_path / "image.hdf"
    size = 16 * 1024
    path.write_bytes(b"a" * size)
    lock = HostFileLock(path, read_only=read_only)
    competitor = HostFileLock(path, read_only=read_only)
    try:
        lock.acquire()
        # Exercise the plain RawBlockDevice API and block-size reopening,
        # without DiskImage's private opening path.
        for block_size in (512, 1024):
            raw = RawBlockDevice(str(path), read_only=read_only, block_bytes=block_size)
            raw.open()
            try:
                assert raw.read_block(0) == b"a" * block_size
                last = size // block_size - 1
                assert raw.read_block(last) == b"a" * block_size
                if not read_only:
                    raw.write_block(last, b"z" * block_size)
                    assert raw.read_block(last) == b"z" * block_size
                    raw.write_block(last, b"a" * block_size)
                with pytest.raises(IOError, match="exclusively lock"):
                    competitor.acquire()
            finally:
                raw.close()
    finally:
        competitor.release()
        lock.release()
    try:
        competitor.acquire()
    finally:
        competitor.release()
