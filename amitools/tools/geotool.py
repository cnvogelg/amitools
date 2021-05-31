#!/usr/bin/env python3


import sys
import os.path
import amitools.util.KeyValue as KeyValue
import amitools.util.ByteSize as ByteSize
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory


def main(args=None):
    if not args:
        a = sys.argv
    else:
        a = args
    n = len(a)
    if n < 3:
        print(
            "Usage: (detect <size|file> [options] | setup <options> | open <file> [options] | create <file> <options>)"
        )
        print(
            """Options:
             size=<size>
             chs=<n>,<n>,<n>
             c=<n> h=<n> s=<n>
             algo=1|2
             """
        )
        return 1
    else:
        cmd = a[1]
        # detect disk geometry from given image file
        if cmd == "detect":
            if os.path.exists(a[2]):
                # its a file
                size = os.path.getsize(a[2])
            else:
                # parse size string
                size = ByteSize.parse_byte_size_str(a[2])
            if size == None:
                print("Invalid size!")
            else:
                d = DiskGeometry()
                opts = None
                if n > 3:
                    opts = KeyValue.parse_key_value_strings(a[3:])
                print("size:  ", size)
                print("opts:  ", opts)
                size = d.detect(size, opts)
                if size != None:
                    print("geo:   ", d)
                else:
                    print("FAILED")
        # setup a new disk geometry from options
        elif cmd == "setup":
            d = DiskGeometry()
            opts = KeyValue.parse_key_value_strings(a[2:])
            print("opts:  ", opts)
            size = d.setup(opts)
            if size != None:
                print("setup: ", size, ByteSize.to_byte_size_str(size))
                print("geo:   ", d)
            else:
                print("FAILED")
        # open a blkdev and detect geometry
        elif cmd == "open":
            opts = None
            if n > 3:
                opts = KeyValue.parse_key_value_strings(a[3:])
            print("opts:   ", opts)
            f = BlkDevFactory()
            blkdev = f.open(a[2], options=opts)
            if blkdev != None:
                print("blkdev: ", blkdev.__class__.__name__)
                print("geo:    ", blkdev.get_geometry())
                blkdev.close()
            else:
                print("FAILED")
        # create a new blkdev with setup geometry
        elif cmd == "create":
            opts = KeyValue.parse_key_value_strings(a[3:])
            print("opts:   ", opts)
            f = BlkDevFactory()
            blkdev = f.create(a[2], options=opts)
            if blkdev != None:
                print("blkdev: ", blkdev.__class__.__name__)
                print("geo:    ", blkdev.get_geometry())
                blkdev.close()
            else:
                print("FAILED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
