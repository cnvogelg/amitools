import os.path

from .Block import Block
import amitools.fs.DosType as DosType


class BootBlock(Block):
    def __init__(self, blkdev, blk_num=0):
        Block.__init__(self, blkdev, blk_num)
        self.dos_type = None
        self.got_root_blk = None
        self.got_chksum = 0
        self.calc_chksum = 0
        self.boot_code = None
        self.num_extra = self.blkdev.bootblocks - 1
        self.max_boot_code = self.blkdev.bootblocks * self.blkdev.block_bytes - 12
        self.extra_blks = []

    def create(self, dos_type=DosType.DOS0, root_blk=None, boot_code=None):
        Block.create(self)
        self._create_data()
        self.dos_type = dos_type
        self.valid_dos_type = True
        # root blk
        self.calc_root_blk = int(self.blkdev.num_blocks // 2)
        if root_blk != None:
            self.got_root_blk = root_blk
        else:
            self.got_root_blk = self.calc_root_blk
        # create extra blks
        self.extra_blks = []
        for i in range(self.num_extra):
            b = Block(self.blkdev, self.blk_num + 1 + i)
            b._create_data()
            self.extra_blks.append(b)
        # setup boot code
        return self.set_boot_code(boot_code)

    def set_boot_code(self, boot_code):
        if boot_code != None:
            if len(boot_code) <= self.max_boot_code:
                self.boot_code = boot_code
                self.valid = True
            else:
                self.valid = False
        else:
            self.boot_code = None
            self.valid = True
        return self.valid

    def _calc_chksum(self):
        all_blks = [self] + self.extra_blks
        n = self.blkdev.block_longs
        chksum = 0
        for blk in all_blks:
            for i in range(n):
                if i != 1:  # skip chksum
                    chksum += blk._get_long(i)
                    if chksum > 0xFFFFFFFF:
                        chksum += 1
                        chksum &= 0xFFFFFFFF
        return (~chksum) & 0xFFFFFFFF

    def read(self):
        self._read_data()
        # read extra boot blocks
        self.extra_blks = []
        for i in range(self.num_extra):
            b = Block(self.blkdev, self.blk_num + 1 + i)
            b._read_data()
            self.extra_blks.append(b)

        self.dos_type = self._get_long(0)
        self.got_chksum = self._get_long(1)
        self.got_root_blk = self._get_long(2)
        self.calc_chksum = self._calc_chksum()
        # calc position of root block
        self.calc_root_blk = int(self.blkdev.num_blocks // 2)
        # check validity
        self.valid_chksum = self.got_chksum == self.calc_chksum
        self.valid_dos_type = DosType.is_valid(self.dos_type)
        self.valid = self.valid_dos_type

        # look for boot_code
        if self.valid:
            self.read_boot_code()
        return self.valid

    def read_boot_code(self):
        boot_code = self.data[12:]
        for blk in self.extra_blks:
            boot_code += blk.data.raw
        # remove nulls at end
        pos = len(boot_code) - 4
        while pos > 0:
            tag = boot_code[pos : pos + 3]
            if tag != "DOS" and boot_code[pos] != 0:
                pos += 4
                break
            pos -= 4
        # something left
        if pos > 0:
            boot_code = boot_code[:pos]
            self.boot_code = boot_code

    def write(self):
        self._create_data()
        self._put_long(0, self.dos_type)
        self._put_long(2, self.got_root_blk)

        if self.boot_code != None:
            self.write_boot_code()
            self.calc_chksum = self._calc_chksum()
            self._put_long(1, self.calc_chksum)
            self.valid_chksum = True
        else:
            self.calc_chksum = 0
            self.valid_chksum = False

        self._write_data()

    def write_boot_code(self):
        n = len(self.boot_code)
        bb = self.blkdev.block_bytes
        first_size = bb - 12
        boot_code = self.boot_code
        # spans more blocks
        if n > first_size:
            extra = boot_code[first_size:]
            boot_code = boot_code[:first_size]
            # write extra blocks
            pos = 0
            off = 0
            n -= first_size
            while n > 0:
                num = n
                if num > bb:
                    num = bb
                self.extra_blks[pos].data[:num] = extra[off : off + num]
                self.extra_blks[pos]._write_data()
                off += num
                pos += 1
                n -= num
            # use this for first block
            n = first_size

        # embed boot code in boot block
        self.data[12 : 12 + n] = boot_code

    def dump(self):
        print("BootBlock(%d):" % self.blk_num)
        print(
            " dos_type:  0x%08x %s (valid: %s) is_ffs=%s is_intl=%s is_dircache=%s"
            % (
                self.dos_type,
                DosType.num_to_tag_str(self.dos_type),
                self.valid_dos_type,
                DosType.is_ffs(self.dos_type),
                DosType.is_intl(self.dos_type),
                DosType.is_dircache(self.dos_type),
            )
        )
        print(" root_blk:  %d (got %d)" % (self.calc_root_blk, self.got_root_blk))
        print(
            " chksum:    0x%08x (got) 0x%08x (calc) -> bootable: %s"
            % (self.got_chksum, self.calc_chksum, self.valid_chksum)
        )
        print(" valid:     %s" % self.valid)
        if self.boot_code != None:
            print(" boot_code: %d bytes" % len(self.boot_code))

    def get_boot_code_dir(self):
        my_dir = os.path.dirname(__file__)
        bc_dir = os.path.join(my_dir, "bootcode")
        if os.path.exists(bc_dir):
            return bc_dir
        else:
            return None
