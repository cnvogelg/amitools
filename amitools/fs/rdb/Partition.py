import os
from amitools.fs.block.rdb.PartitionBlock import *
from amitools.fs.blkdev.PartBlockDevice import PartBlockDevice
import amitools.util.ByteSize as ByteSize
import amitools.fs.DosType as DosType


class Partition:
    def __init__(self, blkdev, blk_num, num, cyl_blks, rdisk):
        self.blkdev = blkdev
        self.blk_num = blk_num
        self.num = num
        self.cyl_blks = cyl_blks
        self.rdisk = rdisk
        self.block_bytes = rdisk.block_bytes
        self.part_blk = None

    def get_next_partition_blk(self):
        if self.part_blk != None:
            return self.part_blk.next
        else:
            return 0xFFFFFFFF

    def get_blk_num(self):
        """return the block number of the partition block"""
        return self.blk_num

    def read(self):
        # read fs header
        self.part_blk = PartitionBlock(self.blkdev, self.blk_num)
        if not self.part_blk.read():
            self.valid = False
            return False
        self.valid = True
        return True

    def create_blkdev(self, auto_close_rdb_blkdev=False):
        """create a block device for accessing this partition"""
        return PartBlockDevice(self.blkdev, self.part_blk, auto_close_rdb_blkdev)

    def write(self):
        self.part_blk.write()

    # ----- Query -----

    def dump(self):
        self.part_blk.dump()

    def get_num_cyls(self):
        p = self.part_blk
        return p.dos_env.high_cyl - p.dos_env.low_cyl + 1

    def get_num_blocks(self):
        """return total number of blocks in this partition"""
        return self.get_num_cyls() * self.cyl_blks

    def get_num_bytes(self):
        return self.get_num_blocks() * self.block_bytes

    def get_drive_name(self):
        return self.part_blk.drv_name

    def get_flags(self):
        return self.part_blk.flags

    def get_index(self):
        return self.num

    def get_cyl_range(self):
        de = self.part_blk.dos_env
        if de == None:
            return None
        else:
            return (de.low_cyl, de.high_cyl)

    def get_info(self, total_blks=0):
        """return a string line with typical info about this partition"""
        p = self.part_blk
        de = p.dos_env
        name = "'%s'" % p.drv_name
        part_blks = self.get_num_blocks()
        part_bytes = self.get_num_bytes()
        extra = ""
        if total_blks != 0:
            ratio = 100.0 * part_blks / total_blks
            extra += "%6.2f%%  " % ratio
        # add dos type
        dos_type = de.dos_type
        extra += DosType.num_to_tag_str(dos_type)
        extra += "/0x%04x" % dos_type
        return "Partition: #%d %-06s %8d %8d  %10d  %s  %s" % (
            self.num,
            name,
            de.low_cyl,
            de.high_cyl,
            part_blks,
            ByteSize.to_byte_size_str(part_bytes),
            extra,
        )

    def get_extra_infos(self):
        result = []
        p = self.part_blk
        de = p.dos_env
        # layout
        result.append(
            "blk_longs=%d, sec/blk=%d, surf=%d, blk/trk=%d"
            % (de.block_size, de.sec_per_blk, de.surfaces, de.blk_per_trk)
        )
        result.append("fs_block_size=%d" % (de.block_size * 4 * de.sec_per_blk))
        # max transfer
        result.append("max_transfer=0x%x" % de.max_transfer)
        result.append("mask=0x%x" % de.mask)
        result.append("num_buffer=%d" % de.num_buffer)
        # add flags
        flags = p.flags
        if flags & PartitionBlock.FLAG_BOOTABLE == PartitionBlock.FLAG_BOOTABLE:
            result.append("bootable=1 pri=%d" % de.boot_pri)
        else:
            result.append("bootable=0")
        if flags & PartitionBlock.FLAG_NO_AUTOMOUNT == PartitionBlock.FLAG_NO_AUTOMOUNT:
            result.append("automount=0")
        else:
            result.append("automount=1")
        return result

    # ----- Import/Export -----

    def export_data(self, file_name):
        """Export contents of partition to file"""
        blkdev = self.create_blkdev()
        blkdev.open()
        num_blks = blkdev.num_blocks
        with open(file_name, "wb") as fh:
            for b in range(num_blks):
                data = blkdev.read_block(b)
                fh.write(data)
        blkdev.close()

    def import_data(self, file_name):
        """Import contents of partition from file"""
        part_dev = self.create_blkdev()
        part_dev.open()
        part_blks = part_dev.num_blocks
        blk_size = part_dev.block_bytes
        total = part_blks * blk_size
        # open image
        file_size = os.path.getsize(file_name)
        file_blks = file_size // blk_size
        if file_size % blk_size != 0:
            raise ValueError("image file not block size aligned!")
        # check sizes
        if total < file_size:
            raise ValueError(
                "import image too large: partition=%d != file=%d" % (total, file_size)
            )
        if total > file_size:
            raise ValueError(
                "import image too small: partition=%d != file=%d" % (total, file_size)
            )
        # copy image
        with open(file_name, "rb") as fh:
            for b in range(file_blks):
                data = fh.read(blk_size)
                part_dev.write_block(b, data)
        part_dev.close()
