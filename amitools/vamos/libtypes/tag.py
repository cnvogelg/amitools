from enum import IntEnum
from amitools.vamos.astructs import ULONG
from amitools.vamos.libstructs import TagItemStruct


class CommonTag(IntEnum):
    TAG_DONE = 0
    TAG_IGNORE = 1
    TAG_MORE = 2
    TAG_SKIP = 3
    TAG_USER = 1 << 31


ControlTags = [
    CommonTag.TAG_DONE,
    CommonTag.TAG_IGNORE,
    CommonTag.TAG_MORE,
    CommonTag.TAG_SKIP,
]


_TAG_DONE = CommonTag.TAG_DONE.value
_TAG_MORE = CommonTag.TAG_MORE.value
_TAG_SKIP = CommonTag.TAG_SKIP.value
# TAG_DONE, TAG_IGNORE, TAG_MORE and TAG_SKIP
_CONTROL_TAGS = frozenset(int(tag) for tag in ControlTags)


# tag lists are walked on every FindTagItem() and NextTagItem(): follow
# them in memory instead of through struct wrappers
def succ_tag_addr(mem, addr):
    """address of the tag item after the one at addr, or 0 at the end"""
    tag = mem.r32(addr)
    if tag == _TAG_DONE:
        return 0
    if tag == _TAG_MORE:
        return mem.r32(addr + 4)
    if tag == _TAG_SKIP:
        return addr + 8 * (1 + mem.r32(addr + 4))
    return addr + 8


def real_tag_addr(mem, addr):
    """address of this or the next real tag item, or 0 at the end"""
    while addr != 0:
        if mem.r32(addr) not in _CONTROL_TAGS:
            return addr
        addr = succ_tag_addr(mem, addr)
    return 0


class Tag(ULONG):
    def __repr__(self):
        return f"TagItem(@{self.addr:08x})"

    def get_tag(self, map_enum=None, do_map=True):
        tag = self.get()
        if do_map:
            try:
                tag = CommonTag(tag)
            except ValueError:
                if map_enum:
                    try:
                        tag = map_enum(tag)
                    except ValueError:
                        pass
        return tag

    def set_tag(self, tag):
        self.set(tag)

    def next_tag(self):
        return Tag(self.mem, self.addr + 4)

    def is_done(self):
        return self.get() == CommonTag.TAG_DONE


class TagItem(TagItemStruct):
    def __repr__(self):
        return f"TagItem(@{self.addr:08x})"

    def next_real_tag(self):
        """return this or the next 'real' tag.

        handle all control tags and return None if TAG_DONE
        """
        addr = real_tag_addr(self._mem, self._addr)
        if addr == self._addr:
            return self
        return TagItem(self._mem, addr) if addr != 0 else None

    def succ_tag(self):
        """successor tag after this one"""
        addr = succ_tag_addr(self._mem, self._addr)
        return TagItem(self._mem, addr) if addr != 0 else None

    def succ_real_tag(self):
        mem = self._mem
        addr = succ_tag_addr(mem, self._addr)
        if addr != 0:
            addr = real_tag_addr(mem, addr)
        return TagItem(mem, addr) if addr != 0 else None

    def next_tag(self):
        return TagItem(self.mem, self.addr + 8)

    def get_tuple(self, map_enum=None, do_map=True):
        tag = self.get_tag(map_enum=map_enum, do_map=do_map)
        data = self.data.val
        return (tag, data)

    def get_tag(self, map_enum=None, do_map=True):
        tag = Tag(mem=self.mem, addr=self.addr)
        return tag.get_tag(map_enum=map_enum, do_map=do_map)

    def get_data(self):
        return self.data.val

    def set_tag(self, tag):
        self.tag.val = tag

    def set_data(self, data):
        self.data.val = data

    def remove(self):
        self.tag.val = CommonTag.TAG_IGNORE

    def end_list(self):
        self.tag.val = CommonTag.TAG_DONE

    def clone_to(self, tag):
        tag.set_tag(self.get_tag())
        tag.set_data(self.get_data())

    def has_same_tag_data(self, tag):
        return self.get_tag() == tag.get_tag() and self.get_data() == tag.get_data()


class TagListIter:
    def __init__(self, tag):
        self.tag = tag.next_real_tag()

    def __iter__(self):
        return self

    def __next__(self):
        if self.tag is None:
            raise StopIteration()
        result = self.tag
        self.tag = self.tag.succ_real_tag()
        return result


class TagList:
    def __init__(self, mem, addr):
        self.tag = TagItem(mem, addr)
        self._mem = mem
        self._addr = addr
        self._alloc = None
        self._mem_obj = None

    def get_addr(self):
        return self._addr

    def get_mem(self):
        return self._mem

    def get_first_tag(self):
        return self.tag

    def __repr__(self):
        return f"[TagList,@{self._addr:08x}]"

    def __iter__(self):
        return TagListIter(self.tag)

    def __len__(self):
        mem = self._mem
        num = 0
        addr = real_tag_addr(mem, self._addr)
        while addr != 0:
            num += 1
            addr = succ_tag_addr(mem, addr)
            if addr != 0:
                addr = real_tag_addr(mem, addr)
        return num

    def to_list(self, map_enum=None, do_map=True):
        """convert tag list to python list"""
        tag = self.tag.next_real_tag()
        result = []
        while tag:
            result.append(tag.get_tuple(map_enum=map_enum, do_map=do_map))
            tag = tag.succ_real_tag()
        return result

    def find_tag(self, tag_val):
        """find tag/tag item in list and if found return TagItem() or None"""
        # auto convert tag item
        if isinstance(tag_val, TagItem):
            tag_val = tag_val.tag.val

        mem = self._mem
        tag_val &= 0xFFFFFFFF
        addr = real_tag_addr(mem, self._addr)
        while addr != 0:
            if mem.r32(addr) == tag_val:
                return TagItem(mem, addr)
            addr = succ_tag_addr(mem, addr)
            if addr != 0:
                addr = real_tag_addr(mem, addr)
        return None

    def set_tag(self, tag, data):
        tag = self.find_tag(tag)
        if tag:
            tag.data.val = data
            return True
        else:
            return False

    def delete_tag(self, tag):
        """find tag and overwrite it with TAG_IGNORE"""
        tag = self.find_tag(tag)
        if tag:
            tag.tag.val = CommonTag.TAG_IGNORE
            return True
        else:
            return False

    def get_tag_data(self, tag_val, def_value=0):
        tag = self.find_tag(tag_val)
        if tag:
            return tag.data.val
        else:
            return def_value

    def clone_to(self, tag_list):
        new_tag = tag_list.get_first_tag()
        for tag in self:
            print(tag, new_tag, tag.get_tag())
            tag.clone_to(new_tag)
            new_tag = new_tag.next_tag()

    @classmethod
    def alloc(cls, alloc, *tag_list, label=None):
        tag_list = list(tag_list)
        num_tags = len(tag_list)
        if num_tags == 0:
            tag_list.append((CommonTag.TAG_DONE, 0))
            num_tags == 1
        # auto add TAG DONE if missing
        elif tag_list[-1][0] != CommonTag.TAG_DONE:
            tag_list.append((CommonTag.TAG_DONE, 0))
            num_tags += 1
        # size of tag list
        num_bytes = num_tags * 8
        mem_obj = alloc.alloc_memory(num_bytes, label=label)
        mem = alloc.get_mem()
        addr = mem_obj.addr
        # fill list
        for tag, data in tag_list:
            mem.w32(addr, tag)
            mem.w32(addr + 4, data & 0xFFFFFFFF)
            addr += 8

        tag_list = cls(mem, mem_obj.addr)
        tag_list._alloc = alloc
        tag_list._mem_obj = mem_obj
        return tag_list

    def free(self):
        if self._alloc and self._mem_obj:
            self._alloc.free_memory(self._mem_obj)
            self._alloc = None
            self._mem_obj = None


class TagArrayIter:
    def __init__(self, tag):
        self.tag = tag

    def __iter__(self):
        return self

    def __next__(self):
        if self.tag.is_done():
            raise StopIteration()
        result = self.tag
        self.tag = self.tag.next_tag()
        return result


class TagArray:
    def __init__(self, mem, addr):
        self._mem = mem
        self._addr = addr
        self._alloc = None
        self._mem_obj = None

    def get_addr(self):
        return self._addr

    def get_mem(self):
        return self._mem

    def __repr__(self):
        return f"[TagArray,@{self._addr:08x}]"

    def __iter__(self):
        tag = Tag(self._mem, self._addr)
        return TagArrayIter(tag)

    def __len__(self):
        num = 0
        for tag in self:
            num += 1
        return num

    def to_list(self, map_enum=None, do_map=True):
        """convert tag list to python list"""
        result = []
        for tag in self:
            val = tag.get_tag(map_enum=map_enum, do_map=do_map)
            result.append(val)
        return result

    def find_tag(self, tag_val):
        """find tag and return True/False"""
        if isinstance(tag_val, TagItem):
            tag_val = tag_val.tag.val

        for tag in self:
            if tag.get_tag() == tag_val:
                return True
        return False

    @classmethod
    def alloc(cls, alloc, *tag_array, label=None):
        tag_array = list(tag_array)
        num_tags = len(tag_array)
        if num_tags == 0:
            tag_array.append(CommonTag.TAG_DONE)
            num_tags == 1
        # auto add TAG DONE if missing
        elif tag_array[-1] != CommonTag.TAG_DONE:
            tag_array.append(CommonTag.TAG_DONE)
            num_tags += 1
        # size of tag list
        num_bytes = num_tags * 4
        mem_obj = alloc.alloc_memory(num_bytes, label=label)
        mem = alloc.get_mem()
        addr = mem_obj.addr
        # fill list
        for tag in tag_array:
            mem.w32(addr, tag)
            addr += 4

        tag_array = cls(mem, mem_obj.addr)
        tag_array._alloc = alloc
        tag_array._mem_obj = mem_obj
        return tag_array

    def free(self):
        if self._alloc and self._mem_obj:
            self._alloc.free_memory(self._mem_obj)
            self._alloc = None
            self._mem_obj = None
