#!/usr/bin/env python3
# xdfscan
# quickly scan large sets of Amiga disk image files


import sys
import argparse
import os.path
import time

from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.validate.Validator import Validator
from amitools.fs.validate.Progress import Progress

# ----- logging -----


class MyProgress(Progress):
    def __init__(self):
        Progress.__init__(self)
        self.clk = int(time.perf_counter() * 1000)

    def begin(self, msg):
        Progress.begin(self, msg)

    def add(self):
        Progress.add(self)
        clk = int(time.perf_counter() * 1000)
        delta = clk - self.clk
        # update display every 250ms
        if delta > 250:
            self.clk = clk
            print("%s: %d" % (self.msg, self.num), end="\r"),
            sys.stdout.flush()


def pre_log_path(path, msg):
    print("%20s  %s  " % (msg, path), end="\r"),
    sys.stdout.flush()


def log_path(path, msg):
    print("%20s  %s  " % (msg, path))


def print_block(percent):
    print("%3.1f%%" % (percent / 10.0), end="\r"),
    sys.stdout.flush()


# ----- scanner -----

factory = BlkDevFactory()


def scan(path, args):
    if not os.path.exists(path):
        log_path(path, "DOES NOT EXIST")
        return 1
    if os.path.isdir(path):
        return scan_dir(path, args)
    elif os.path.isfile(path):
        return scan_file(path, args)


def scan_dir(path, args):
    for name in sorted(os.listdir(path)):
        epath = os.path.join(path, name)
        result = scan(epath, args)
        if result != 0:
            return result
    return 0


def check_extension(path, args):
    ext = []
    if not args.skip_disks:
        ext += [".adf", ".adz", ".adf.gz"]
    if not args.skip_hds:
        ext += [".hdf"]
    for a in ext:
        if path.endswith(a):
            return True
    return False


def scan_file(path, args):
    if not check_extension(path, args):
        return 0
    try:
        pre_log_path(path, "scan")
        ret_code = 0

        # create a block device for image file
        blkdev = factory.open(path, read_only=True)

        # create validator
        progress = MyProgress()
        v = Validator(blkdev, min_level=args.level, debug=args.debug, progress=progress)

        # 1. check boot block
        res = []
        boot_dos, bootable = v.scan_boot()
        if boot_dos:
            # 2. check root block
            root = v.scan_root()
            if not root:
                # disk is bootable
                if bootable:
                    res.append("boot")
                else:
                    res.append("    ")
                # invalid root
                res.append("nofs")
            else:
                # 3. scan tree
                v.scan_dir_tree()
                # 4. scan files
                v.scan_files()
                # 5. scan_bitmap
                v.scan_bitmap()

                # summary
                e, w = v.get_summary()
                if w > 0:
                    res.append("w%03d" % w)
                if e > 0:
                    res.append("E%03d" % e)
                else:
                    res.append("    ")
                # disk is bootable
                if bootable:
                    res.append("boot")
                else:
                    res.append("    ")
                if e == 0 and w == 0:
                    res.append(" ok ")
                else:
                    res.append("NOK ")
        else:
            # boot block is not dos
            res.append("NDOS")

        # report result
        if len(res) == 0:
            res.append("done")
        log_path(path, " ".join(res))
        # summary
        if args.verbose:
            v.log.dump()
        return ret_code
    except IOError as e:
        log_path(path, "BLKDEV?")
        if args.verbose:
            print(e)
        return 0


# ----- main -----
def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input", nargs="+", help="input image file or directory (to scan tree)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False, help="be more verbos"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", default=False, help="show debug info"
    )
    parser.add_argument(
        "-q",
        "--quick",
        action="store_true",
        default=False,
        help="quick mode. faster: skip image if root is invalid",
    )
    parser.add_argument(
        "-l",
        "--level",
        default=2,
        help="show only level or above (0=debug, 1=info, 2=warn, 3=error)",
        type=int,
    )
    parser.add_argument(
        "-D",
        "--skip-disks",
        action="store_true",
        default=False,
        help="do not scan disk images",
    )
    parser.add_argument(
        "-H",
        "--skip-hds",
        action="store_true",
        default=False,
        help="do not scan hard disk images",
    )
    args = parser.parse_args(args=args)

    # main scan loop
    ret = 0
    for i in args.input:
        ret = scan(i, args)
        if ret != 0:
            break
    return ret


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("aborting...")
