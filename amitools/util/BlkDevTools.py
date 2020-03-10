#!/usr/bin/env python3
# based heavily on "iops" by Benjamin Schweizer
# https://github.com/gopher/iops


import sys
import array
import struct
import os


def getblkdevsize(dev):
    """report the size for a block device"""
    size = 0
    if sys.platform == "darwin":
        # mac os x ioctl from sys/disk.h
        import fcntl

        DKIOCGETBLOCKSIZE = 0x40046418  # _IOR('d', 24, uint32_t)
        DKIOCGETBLOCKCOUNT = 0x40086419  # _IOR('d', 25, uint64_t)

        fh = open(dev, "r")
        buf = array.array("B", list(range(0, 4)))  # uint32
        r = fcntl.ioctl(fh.fileno(), DKIOCGETBLOCKSIZE, buf, 1)
        blocksize = struct.unpack("I", buf)[0]
        buf = array.array("B", list(range(0, 8)))  # uint64
        r = fcntl.ioctl(fh.fileno(), DKIOCGETBLOCKCOUNT, buf, 1)
        blockcount = struct.unpack("Q", buf)[0]
        fh.close()
        size = blocksize * blockcount

    elif sys.platform.startswith("freebsd"):
        # freebsd ioctl from sys/disk.h
        import fcntl

        DIOCGMEDIASIZE = 0x40086481  # _IOR('d', 129, uint64_t)

        fh = open(dev, "r")
        buf = array.array("B", list(range(0, 8)))  # off_t / int64
        r = fcntl.ioctl(fh.fileno(), DIOCGMEDIASIZE, buf, 1)
        size = struct.unpack("q", buf)[0]
        fh.close()

    elif sys.platform == "win32":
        # win32 ioctl from winioctl.h, requires pywin32
        try:
            import win32file
        except ImportError:
            raise SystemExit(
                "Package pywin32 not found, see http://sf.net/projects/pywin32/"
            )
        IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000
        dh = win32file.CreateFile(
            dev, 0, win32file.FILE_SHARE_READ, None, win32file.OPEN_EXISTING, 0, None
        )
        info = win32file.DeviceIoControl(dh, IOCTL_DISK_GET_DRIVE_GEOMETRY, "", 24)
        win32file.CloseHandle(dh)
        (cyl_lo, cyl_hi, media_type, tps, spt, bps) = struct.unpack("6L", info)
        size = ((cyl_hi << 32) + cyl_lo) * tps * spt * bps

    else:  # linux or compat
        # linux 2.6 lseek from fcntl.h
        fh = open(dev, "r")
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.close()

    if not size:
        raise Exception("getblkdevsize: Unsupported platform")

    return size


# test
if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(a, getblkdevsize(a))
