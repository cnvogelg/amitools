"""Host disk image backends for Amiga devices exposed by vamos."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None

from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.block.rdb.RDBlock import RDBlock
from amitools.fs.rdb.RDisk import RDisk


class HostFileLock:
    """Hold a non-blocking exclusive lock for one disk-image session."""

    def __init__(self, image, *, read_only=True):
        self.image = Path(image)
        self.read_only = read_only
        self._file = None
        self._kind = None
        self._lock_offset = 0

    @property
    def is_locked(self):
        return self._file is not None

    def acquire(self):
        if self.is_locked:
            return
        mode = "rb" if self.read_only else "r+b"
        lock_file = open(self.image, mode)
        try:
            if fcntl is not None:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                lock_kind = "flock"
            elif msvcrt is not None:  # pragma: no cover - Windows
                # Windows locks also deny reads through our other handle.
                # Images have a fixed size, so all sessions can lock the
                # byte just beyond EOF without overlapping any disk data.
                lock_file.seek(0, 2)
                self._lock_offset = lock_file.tell()
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                lock_kind = "msvcrt"
            else:  # pragma: no cover - unsupported Python platform
                raise OSError("host file locking is unavailable")
        except OSError as exc:
            lock_file.close()
            raise IOError(
                "cannot exclusively lock disk image %s: %s" % (self.image, exc)
            ) from exc
        self._file = lock_file
        self._kind = lock_kind

    def release(self):
        lock_file = self._file
        lock_kind = self._kind
        self._file = None
        self._kind = None
        if lock_file is None:
            return
        try:
            if lock_kind == "flock":
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            elif lock_kind == "msvcrt":  # pragma: no cover - Windows
                lock_file.seek(self._lock_offset)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lock_file.close()


@runtime_checkable
class BlockBackend(Protocol):
    """Block interface consumed by the vamos disk device implementation."""

    block_size: int
    total_blocks: int
    cyls: int
    heads: int
    secs: int
    read_only: bool
    exclusive: bool

    def read_blocks(self, blk_num: int, num_blks: int = 1) -> bytes:
        pass

    def write_blocks(self, blk_num: int, data: bytes, num_blks: int = 1) -> None:
        pass

    def sync(self) -> None:
        pass

    def close(self) -> None:
        pass


@dataclass(frozen=True)
class DiskPartition:
    """An RDB partition exported as an AmigaDOS device."""

    name: str
    index: int
    dos_env: object


class DiskImage:
    """Expose a standard RDB image at whole-disk block granularity.

    ``BlkDevFactory`` deliberately returns a partition block device for RDB
    images.  That is the right abstraction for filesystem tools, but an Amiga
    ``scsi.device`` must expose the whole disk because the filesystem applies
    the partition offset from its DosEnvec itself.
    """

    def __init__(
        self,
        image,
        *,
        read_only: bool = True,
        block_size: Optional[int] = None,
    ):
        self.image = Path(image)
        self.read_only = read_only
        self.requested_block_size = block_size
        self.block_size = block_size or 512
        self.total_blocks = 0
        self.cyls = 0
        self.heads = 0
        self.secs = 0
        self.blkdev = None
        self.rdb = None
        self.rdb_block = None
        self.partitions = []
        self.host_lock = HostFileLock(self.image, read_only=read_only)

    @property
    def is_open(self) -> bool:
        return self.blkdev is not None

    @property
    def exclusive(self) -> bool:
        return self.host_lock.is_locked

    def _open_raw(self, block_size):
        fobj = None
        if fcntl is None and msvcrt is not None:
            # Buffered reads of the last sector can extend past EOF and
            # hit the Windows lock byte. Keep reads within their exact
            # requested range, including when reopening for an RDB size.
            mode = "rb" if self.read_only else "r+b"
            fobj = open(self.image, mode, buffering=0)
        blkdev = RawBlockDevice(
            str(self.image),
            read_only=self.read_only,
            block_bytes=block_size,
            fobj=fobj,
        )
        try:
            blkdev.open()
        except Exception:
            if fobj is not None:
                fobj.close()
            raise
        return blkdev

    @staticmethod
    def _scan_for_rdb(blkdev):
        for block_num in range(min(16, blkdev.num_blocks)):
            rdb = RDBlock(blkdev, block_num)
            if rdb.read():
                return rdb
        return None

    def open(self):
        if self.is_open:
            return self

        self.host_lock.acquire()
        blkdev = None
        try:
            blkdev = self._open_raw(self.block_size)
            rdb = self._scan_for_rdb(blkdev)
            if rdb is None:
                raise IOError("no RDB found in blocks 0-15")
            rdb_block_size = rdb.block_size
            if rdb_block_size != self.block_size:
                blkdev.close()
                blkdev = None
                blkdev = self._open_raw(rdb_block_size)
                rdb = self._scan_for_rdb(blkdev)
                if rdb is None:
                    raise IOError("no RDB found in blocks 0-15")
            rdisk = RDisk(blkdev)
            rdisk.rdb = rdb
            if not rdisk.open():
                raise IOError("invalid or unsupported RDB image")

            pd = rdisk.rdb.phy_drv
            total_blocks = pd.cyls * pd.heads * pd.secs
            if total_blocks <= 0:
                raise IOError("RDB has invalid physical geometry")
            if total_blocks > blkdev.num_blocks:
                raise IOError(
                    "RDB geometry exceeds disk image: %d > %d blocks"
                    % (total_blocks, blkdev.num_blocks)
                )
            self.blkdev = blkdev
            self.rdb = rdisk
            self.rdb_block = rdb.blk_num
            self.block_size = blkdev.block_bytes
            self.cyls = pd.cyls
            self.heads = pd.heads
            self.secs = pd.secs
            self.total_blocks = total_blocks
            self.partitions = []
            for index, part in enumerate(rdisk.parts):
                drv_name = part.get_drive_name()
                if hasattr(drv_name, "get_unicode"):
                    name = drv_name.get_unicode()
                else:
                    name = str(drv_name)
                self.partitions.append(
                    DiskPartition(name, index, part.part_blk.dos_env)
                )
            return self
        except Exception:
            if blkdev is not None:
                try:
                    blkdev.close()
                except Exception:
                    pass
            try:
                self.host_lock.release()
            except Exception:
                pass
            raise

    def _check_range(self, blk_num: int, num_blks: int) -> None:
        if blk_num < 0 or num_blks < 0:
            raise ValueError("negative block range")
        if blk_num + num_blks > self.total_blocks:
            raise ValueError("block range exceeds disk image")

    def read_blocks(self, blk_num: int, num_blks: int = 1) -> bytes:
        if self.blkdev is None:
            raise RuntimeError("disk image is not open")
        self._check_range(blk_num, num_blks)
        if num_blks == 0:
            return b""
        return self.blkdev.read_block(blk_num, num_blks)

    def write_blocks(self, blk_num: int, data: bytes, num_blks: int = 1) -> None:
        if self.blkdev is None:
            raise RuntimeError("disk image is not open")
        if self.read_only:
            raise PermissionError("disk image is read-only")
        self._check_range(blk_num, num_blks)
        expected = num_blks * self.block_size
        if len(data) != expected:
            raise ValueError(
                "block write has %d bytes, expected %d" % (len(data), expected)
            )
        if num_blks == 0:
            return
        self.blkdev.write_block(blk_num, data, num_blks)

    def sync(self) -> None:
        if self.blkdev is not None:
            self.blkdev.flush()

    def close(self) -> None:
        rdisk = self.rdb
        blkdev = self.blkdev
        self.rdb = None
        self.rdb_block = None
        self.blkdev = None
        self.partitions = []
        first_error = None
        try:
            if rdisk is not None:
                rdisk.close()
        except Exception as exc:
            first_error = exc
        try:
            if blkdev is not None:
                blkdev.close()
        except Exception as exc:
            if first_error is None:
                first_error = exc
        try:
            self.host_lock.release()
        except Exception as exc:
            if first_error is None:
                first_error = exc
        if first_error is not None:
            raise first_error

    def describe(self) -> str:
        mode = "read-only" if self.read_only else "read-write"
        return (
            f"{self.image} ({mode}, {self.cyls}/{self.heads}/{self.secs}, "
            f"{self.block_size}-byte sectors)"
        )
