"""Host disk image backends for Amiga devices exposed by vamos."""

import struct
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

import amitools.fs.DosType as DosType
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.block.rdb.PartitionBlock import PartitionDosEnv
from amitools.fs.block.rdb.RDBlock import RDBlock
from amitools.fs.rdb.RDisk import RDisk
from amitools.util.Win32Disk import DiskLock, is_windows_disk

from .spec import RAW_KEYS

# characters allowed in a sanitized default raw-device name
_SAFE_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)


def _blkdev_read_only(blkdev):
    """the effective read-only state of an opened ``amitools.fs`` block device"""
    read_only = getattr(blkdev, "read_only", None)
    if read_only is None:
        image_file = getattr(blkdev, "img_file", None)
        read_only = getattr(image_file, "read_only", False)
    return bool(read_only)


def _read_dos_type(blkdev):
    """the DOS type stored in the image's boot block, or DOS0"""
    try:
        block = blkdev.read_block(0)
    except Exception:
        return DosType.DOS0
    if len(block) >= 4:
        value = struct.unpack_from(">I", block, 0)[0]
        if DosType.is_valid(value):
            return value
    return DosType.DOS0


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
        if is_windows_disk(self.image):
            try:
                self._file = DiskLock(self.image, read_only=self.read_only)
            except OSError as exc:
                raise IOError(
                    "cannot exclusively lock disk %s: %s" % (self.image, exc)
                ) from exc
            self._kind = "physical_disk"
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
    """An RDB partition exported as an AmigaDOS device.

    ``driver_data`` is the filesystem driver (a seglist hunk stream) the RDB
    stores for the partition's DOS type, and ``driver_globvec`` its
    ``dol_GlobVec``. Both are ``None`` when the RDB has no matching driver.
    A native handler without an explicit ``binary=`` mounts with them
    (HANDLER.md step 24d).
    """

    name: str
    index: int
    dos_env: object
    driver_data: Optional[bytes] = None
    driver_globvec: Optional[int] = None


@dataclass(frozen=True)
class DosDevice:
    """One DOS device a backend publishes in the device list.

    ``dos_env`` is the geometry source for the device's ``DosEnvec`` and
    ``explicit_name`` records whether the name was chosen by the user
    (``?name=``, or an RDB partition name). A name clash on an explicit name
    is a setup error, while a defaulted raw name may be disambiguated with the
    unit number (HANDLER.md step 25d).
    """

    name: str
    dos_env: object
    explicit_name: bool = True


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
        blkdev = RawBlockDevice(
            str(self.image),
            read_only=self.read_only,
            block_bytes=block_size,
        )
        blkdev.open()
        return blkdev

    @staticmethod
    def _scan_for_rdb(blkdev):
        for block_num in range(min(16, blkdev.num_blocks)):
            rdb = RDBlock(blkdev, block_num)
            if rdb.read():
                return rdb
        return None

    @staticmethod
    def _match_driver(filesystems, dos_env):
        """the RDB driver (seglist data, globvec) for a partition's DOS type

        The RDB stores one filesystem per DOS type; a partition mounts the one
        whose ``dos_type`` matches its own. Returns ``(None, None)`` when no
        filesystem matches, so a native handler with an explicit ``binary=``
        (or a Python handler) is unaffected.
        """
        dos_type = getattr(dos_env, "dos_type", None)
        if dos_type is None:
            return None, None
        for fs in filesystems:
            fshd = fs.fshd
            if fshd is not None and fshd.dos_type == dos_type:
                # only a header that declares the global_vec flag carries one
                glob_vec = dict(fshd.get_flags()).get("global_vec")
                if glob_vec is not None and glob_vec >= 0x80000000:
                    glob_vec -= 0x100000000
                return fs.get_data(), glob_vec
        return None, None

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
                dos_env = part.part_blk.dos_env
                driver_data, driver_globvec = self._match_driver(rdisk.fs, dos_env)
                self.partitions.append(
                    DiskPartition(
                        name,
                        index,
                        dos_env,
                        driver_data=driver_data,
                        driver_globvec=driver_globvec,
                    )
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

    def dos_devices(self):
        """every RDB partition as a ``(name, DosEnvec source)`` device"""
        return [
            DosDevice(partition.name, partition.dos_env, True)
            for partition in self.partitions
        ]

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


class RawDiskImage:
    """Expose a raw ADF/HDF image (no RDB) at whole-disk granularity.

    Unlike :class:`DiskImage` this opens the image through
    :class:`~amitools.fs.blkdev.BlkDevFactory`, so ADF (DD/HD), HDF geometry
    detection and gzipped ``.adz``/``.hdz`` images are all handled there.
    There is no partition table: the whole disk is published as one synthetic
    DOS device (HANDLER.md steps 25c/25d).
    """

    def __init__(
        self,
        image,
        *,
        read_only: bool = True,
        options=None,
        unit: int = 0,
        name=None,
    ):
        self.image = Path(image)
        self.read_only = read_only
        self.options = dict(options or {})
        self.unit = unit
        self.name = name
        self.block_size = 512
        self.total_blocks = 0
        self.cyls = 0
        self.heads = 0
        self.secs = 0
        self.blkdev = None
        self.partitions = []
        self.host_lock = HostFileLock(self.image, read_only=read_only)

    @property
    def is_open(self) -> bool:
        return self.blkdev is not None

    @property
    def exclusive(self) -> bool:
        return self.host_lock.is_locked

    def open(self):
        if self.is_open:
            return self
        self.host_lock.acquire()
        blkdev = None
        try:
            blkdev = BlkDevFactory().open(
                str(self.image),
                read_only=self.read_only,
                options=self.options,
            )
            self.blkdev = blkdev
            self.block_size = blkdev.block_bytes
            self.total_blocks = blkdev.num_blocks
            self.cyls = blkdev.cyls
            self.heads = blkdev.heads
            self.secs = blkdev.sectors
            # the factory downgrades to read-only when the host file is not
            # writable, so trust the opened device over the request
            self.read_only = _blkdev_read_only(blkdev)
            # publish the whole disk as one synthetic partition so a native
            # handler can resolve it through ``backend.partitions`` (step 27b)
            self.partitions = [self._make_partition()]
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

    def dos_devices(self):
        """the whole disk as one synthetic ``(name, DosEnvec source)`` device"""
        if not self.partitions:
            # not open yet: build the synthetic device on demand
            return [
                DosDevice(self._device_name(), self._make_dos_env(), self._explicit)
            ]
        return [
            DosDevice(partition.name, partition.dos_env, self._explicit)
            for partition in self.partitions
        ]

    @property
    def _explicit(self) -> bool:
        return self.name is not None

    def _device_name(self) -> str:
        if self.name is not None:
            return str(self.name)
        stem = self.image.stem
        safe = "".join(c if c in _SAFE_NAME_CHARS else "_" for c in stem)
        if not safe:
            safe = "disk%d" % self.unit
        return safe

    def _make_dos_env(self):
        """a whole-disk ``DosEnvec`` source built from the detected geometry"""
        env = PartitionDosEnv(
            block_size=max(self.block_size // 4, 1),
            surfaces=self.heads,
            blk_per_trk=self.secs,
            low_cyl=0,
            high_cyl=max(self.cyls - 1, 0),
            reserved=2,
            dos_type=_read_dos_type(self.blkdev) if self.blkdev else DosType.DOS0,
        )
        env.update_size()
        return env

    def _make_partition(self):
        """the whole disk as one synthetic partition for the native handler

        A native handler resolves its block device through
        ``DiskSession.get_backend(unit).partitions`` (HANDLER.md step 27b). A
        raw image has no partition table, so the whole disk is published as a
        single partition: index 0, the whole-disk geometry and no RDB driver.
        """
        return DiskPartition(self._device_name(), 0, self._make_dos_env())

    def close(self) -> None:
        blkdev = self.blkdev
        self.blkdev = None
        self.partitions = []
        first_error = None
        try:
            if blkdev is not None:
                blkdev.close()
        except Exception as exc:
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


def open_disk_backend(image, *, read_only=True, options=None, unit=0):
    """open the backend matching an image's on-disk type (HANDLER.md 25b).

    An RDB image (``RDSK`` magic or an ``.rdb``/``.rdisk`` extension) gets a
    :class:`DiskImage`, which exposes the whole RDB and its partitions; every
    other image gets a :class:`RawDiskImage`. ``options`` carries the raw
    geometry/type keys (``type``/``bs``/``chs``/``algo``) and the optional
    ``name``; an RDB image rejects the raw-only keys so a mistyped option fails
    loudly.
    """
    options = dict(options or {})
    factory = BlkDevFactory()
    image_type = factory.detect_type(str(image), None, options)
    if image_type is not None and (image_type & factory.TYPE_MASK) == factory.TYPE_RDB:
        raw_keys = RAW_KEYS.intersection(options)
        if raw_keys:
            raise ValueError(
                "RDB image does not accept raw options: %s"
                % ", ".join(sorted(raw_keys))
            )
        return DiskImage(image, read_only=read_only)
    name = options.pop("name", None)
    return RawDiskImage(
        image,
        read_only=read_only,
        options=options,
        unit=unit,
        name=name,
    )
