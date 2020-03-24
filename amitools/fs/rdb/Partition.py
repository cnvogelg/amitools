from amitools.fs.block.rdb.PartitionBlock import *
from amitools.fs.blkdev.PartBlockDevice import PartBlockDevice
import amitools.util.ByteSize as ByteSize
import amitools.fs.DosType as DosType
from json import dumps, loads


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

    def get_info(self, total_blks=0, json_out=False):
        if json_out:
            return self._get_info_json(total_blks)
        return self._get_info_str(total_blks)

    def _get_info_str(self, total_blks):
        """return a string line with typical info about this partition"""
        json_obj = loads(self._get_info_json(total_blks))

        p = self.part_blk
        de = p.dos_env
        extra = ""
        if json_obj[self.num].get('ratio'):
            extra += "%s  " % json_obj[self.num]['ratio']
        # add dos type
        extra += "%s/%s" % (json_obj[self.num]['dos_type'], json_obj[self.num]['dos_type_hex'])

        return "Partition: #%d %-06s %8d %8d  %10d  %s  %s" % (
            self.num,
            json_obj[self.num]['name'],
            json_obj[self.num]['start_cyl'],
            json_obj[self.num]['end_cyl'],
            json_obj[self.num]['blocks'],
            json_obj[self.num]['size'],
            extra,
        )

    def _get_info_json(self,total_blks):
        """return a json string with typical info about this partition"""

        p = self.part_blk
        name = "'%s'" % p.drv_name
        part_blks = self.get_num_blocks()
        part_bytes = self.get_num_bytes()

        json_obj = {
            self.num: {
                "name": name,
                "start_cyl": p.dos_env.low_cyl,
                "end_cyl": p.dos_env.high_cyl,
                "blocks": part_blks,
                "size": ByteSize.to_byte_size_str(part_bytes),
                "dos_type": DosType.num_to_tag_str(p.dos_env.dos_type),
                "dos_type_hex": "0x%04x" % p.dos_env.dos_type
            }
        }

        if total_blks != 0:
            ratio = 100.0 * part_blks / total_blks
            json_obj[self.num]["ratio"] = "%.2f%%" % ratio

        return dumps(json_obj)

    def get_extra_infos(self, json_out=False):
        if json_out:
            return self._get_extra_infos_json()
        return self._get_extra_infos_str()

    def _get_extra_infos_str(self):
        json_obj = loads(self._get_extra_infos_json())

        result = []
        result.append(
            "blk_longs=%d, sec/blk=%d, surf=%d, blk/trk=%d"
            % (json_obj['blk_longs'], json_obj['sec_blk'], json_obj['surf'], json_obj['blk_trk'])
        )
        result.append("fs_block_size=%s" % json_obj['fs_block_size'])
        # max transfer
        result.append("max_transfer=%s" % json_obj['max_transfer'])
        result.append("mask=%s" % json_obj['mask'])
        result.append("num_buffer=%s" % json_obj['num_buffer'])
        # Flags
        result.append("bootable=%d" % json_obj['bootable'])
        if json_obj.get('priority') is not None:
            result.append("pri=%d" % json_obj['priority'])
        result.append("automount=%d" % json_obj['automount'])

        return result

    def _get_extra_infos_json(self):
        p = self.part_blk

        json_obj = {
          "blk_longs": p.dos_env.block_size,
          "sec_blk": p.dos_env.sec_per_blk,
          "surf": p.dos_env.surfaces,
          "blk_trk": p.dos_env.blk_per_trk,
          "fs_block_size": "%d" % (p.dos_env.block_size * 4 * p.dos_env.sec_per_blk),
          "max_transfer": "0x%x" % p.dos_env.max_transfer,
          "mask": "0x%x" % p.dos_env.mask,
          "num_buffer": "%d" % p.dos_env.num_buffer,
          "bootable": 0,
          "automount": 1
        }
        # add flags
        flags = p.flags
        if flags & PartitionBlock.FLAG_BOOTABLE == PartitionBlock.FLAG_BOOTABLE:
            json_obj['bootable'] = 1
            json_obj['priority'] = p.dos_env.boot_pri

        if flags & PartitionBlock.FLAG_NO_AUTOMOUNT == PartitionBlock.FLAG_NO_AUTOMOUNT:
            json_obj['automount'] = 0

        return dumps(json_obj)
