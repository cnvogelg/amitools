from amitools.fs.block.Block import *
import amitools.fs.DosType as DosType


class FSHeaderDeviceNode:
    valid_flags = (
        "type",
        "task",
        "lock",
        "handler",
        "stack_size",
        "priority",
        "startup",
        "seg_list_blk",
        "global_vec",
    )

    def __init__(
        self,
        type=0,
        task=0,
        lock=0,
        handler=0,
        stack_size=0,
        priority=0,
        startup=0,
        seg_list_blk=0,
        global_vec=0,
    ):
        self.type = type
        self.task = task
        self.lock = lock
        self.handler = handler
        self.stack_size = stack_size
        self.priority = priority
        self.startup = startup
        self.seg_list_blk = seg_list_blk
        self.global_vec = global_vec

    def dump(self):
        print("DeviceNode")
        print(" type:           0x%08x" % self.type)
        print(" task:           0x%08x" % self.task)
        print(" lock:           0x%08x" % self.lock)
        print(" handler:        0x%08x" % self.handler)
        print(" stack_size:     0x%08x" % self.stack_size)
        print(" seg_list_blk:   0x%08x" % self.seg_list_blk)
        print(" global_vec:     0x%08x" % self.global_vec)

    def get_flags(self, patch_flags=0x1FF):
        res = []
        if patch_flags & 0x01 == 0x01:
            res.append(("type", self.type))
        if patch_flags & 0x02 == 0x02:
            res.append(("task", self.task))
        if patch_flags & 0x04 == 0x04:
            res.append(("lock", self.lock))
        if patch_flags & 0x08 == 0x08:
            res.append(("handler", self.handler))
        if patch_flags & 0x10 == 0x10:
            res.append(("stack_size", self.stack_size))
        if patch_flags & 0x20 == 0x20:
            res.append(("priority", self.priority))
        if patch_flags & 0x40 == 0x40:
            res.append(("startup", self.startup))
        if patch_flags & 0x80 == 0x80:
            res.append(("seg_list_blk", self.seg_list_blk))
        if patch_flags & 0x100 == 0x100:
            res.append(("global_vec", self.global_vec))
        return res

    def set_flags(self, flags):
        mask = 0
        for f in flags:
            key = f[0]
            val = int(f[1])
            if key == "type":
                self.type = val
                mask |= 0x01
            elif key == "task":
                self.task = val
                mask |= 0x02
            elif key == "lock":
                self.lock = val
                mask |= 0x04
            elif key == "handler":
                self.handler = val
                mask |= 0x08
            elif key == "stack_size":
                self.stack_size = val
                mask |= 0x10
            elif key == "priority":
                self.priority = val
                mask |= 0x20
            elif key == "startup":
                self.startup = val
                mask |= 0x40
            elif key == "seg_list_blk":
                self.seg_list_blk = val
                mask |= 0x80
            elif key == "global_vec":
                self.global_vec = val
                mask |= 0x100
            else:
                raise ValueError("Invalid flag: " + key)
        return mask

    def get_valid_flag_names(self):
        return (
            "type",
            "task",
            "lock",
            "handler",
            "stack_size",
            "priority",
            "startup",
            "seg_list_blk",
            "global_vec",
        )

    def read(self, blk):
        self.type = blk._get_long(11)
        self.task = blk._get_long(12)
        self.lock = blk._get_long(13)
        self.handler = blk._get_long(14)
        self.stack_size = blk._get_long(15)
        self.priority = blk._get_long(16)
        self.startup = blk._get_long(17)
        self.seg_list_blk = blk._get_long(18)
        self.global_vec = blk._get_long(19)

    def write(self, blk):
        blk._put_long(11, self.type)
        blk._put_long(12, self.task)
        blk._put_long(13, self.lock)
        blk._put_long(14, self.handler)
        blk._put_long(15, self.stack_size)
        blk._put_long(16, self.priority)
        blk._put_long(17, self.startup)
        blk._put_long(18, self.seg_list_blk)
        blk._put_long(19, self.global_vec)

    def clear_flags(self):
        self.ftype = 0
        self.task = 0
        self.lock = 0
        self.handler = 0
        self.stack_size = 0
        self.priority = 0
        self.startup = 0


class FSHeaderBlock(Block):
    def __init__(self, blkdev, blk_num):
        Block.__init__(self, blkdev, blk_num, chk_loc=2, is_type=Block.FSHD)

    def create(
        self,
        host_id=0,
        next=Block.no_blk,
        flags=0,
        dos_type=0,
        version=0,
        patch_flags=0,
        size=64,
        dev_node=None,
    ):
        Block.create(self)
        self.size = size
        self.host_id = host_id
        self.next = next
        self.flags = flags

        self.dos_type = dos_type
        self.version = version
        self.patch_flags = patch_flags

        if dev_node == None:
            dev_node = FSHeaderDeviceNode()
        self.dev_node = dev_node

    def write(self):
        self._create_data()

        self._put_long(1, self.size)
        self._put_long(3, self.host_id)
        self._put_long(4, self.next)
        self._put_long(5, self.flags)

        self._put_long(8, self.dos_type)
        self._put_long(9, self.version)
        self._put_long(10, self.patch_flags)

        self.dev_node.write(self)

        Block.write(self)

    def read(self):
        Block.read(self)
        if not self.valid:
            return False

        self.size = self._get_long(1)
        self.host_id = self._get_long(3)
        self.next = self._get_long(4)
        self.flags = self._get_long(5)

        self.dos_type = self._get_long(8)
        self.version = self._get_long(9)
        self.patch_flags = self._get_long(10)

        self.dev_node = FSHeaderDeviceNode()
        self.dev_node.read(self)

        return self.valid

    def get_version_tuple(self):
        return ((self.version >> 16), (self.version & 0xFFFF))

    def get_version_string(self):
        return "%d.%d" % self.get_version_tuple()

    def get_flags(self):
        return self.dev_node.get_flags(self.patch_flags)

    def get_valid_flag_names(self):
        return self.dev_node.get_valid_flag_names()

    def dump(self):
        Block.dump(self, "FSHeader")

        print(" size:           %d" % self.size)
        print(" host_id:        %d" % self.host_id)
        print(" next:           %s" % self._dump_ptr(self.next))
        print(" flags:          0x%08x" % self.flags)
        print(
            " dos_type:       0x%08x = %s"
            % (self.dos_type, DosType.num_to_tag_str(self.dos_type))
        )
        print(
            " version:        0x%08x = %s" % (self.version, self.get_version_string())
        )
        print(" patch_flags:    0x%08x" % self.patch_flags)

        self.dev_node.dump()

    def set_flags(self, flags):
        mask = self.dev_node.set_flags(flags)
        self.patch_flags |= mask

    def set_flag(self, key, value):
        mask = self.dev_node.set_flags([(key, value)])
        self.patch_flags |= mask

    def clear_flags(self):
        self.patch_flags = 0x180
        self.dev_node.clear_flags()
