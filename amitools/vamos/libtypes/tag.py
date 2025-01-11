from enum import IntEnum
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


class TagItem(TagItemStruct):
    def __repr__(self):
        return f"TagItem(@{self.addr:08x})"

    def next_real_tag(self):
        """return this or the next 'real' tag.

        handle all control tags and return None if TAG_DONE
        """
        tag_obj = self
        while tag_obj:
            tag = tag_obj.tag.val
            if tag not in ControlTags:
                return tag_obj
            tag_obj = tag_obj.succ_real_tag()
        return tag_obj

    def succ_tag(self):
        """successor tag after this one"""
        tag = self.tag.val
        data = self.data.val
        if tag == CommonTag.TAG_DONE:
            return None
        elif tag == CommonTag.TAG_MORE:
            if data == 0:
                return None
            else:
                return TagItem(self.mem, data)
        elif tag == CommonTag.TAG_SKIP:
            addr = self.addr + 8 * (1 + data)
            return TagItem(self.mem, addr)
        else:
            return TagItem(self.mem, self.addr + 8)

    def succ_real_tag(self):
        succ = self.succ_tag()
        if succ:
            return succ.next_real_tag()

    def get_tuple(self, map_enum=None, do_map=True):
        tag = self.get_tag(map_enum=map_enum, do_map=do_map)
        data = self.data.val
        return (tag, data)

    def get_tag(self, map_enum=None, do_map=True):
        tag = self.tag.val
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

    def get_data(self):
        return self.data.val

    def set_tag(self, tag):
        self.tag.val = tag

    def set_data(self, data):
        self.data.val = data

    def remove(self):
        self.tag.val = CommonTag.TAG_IGNORE


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
        tag = self.tag.next_real_tag()
        num = 0
        while tag:
            tag = tag.succ_real_tag()
            num += 1
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

        tag = self.tag.next_real_tag()
        while tag:
            if tag.tag.val == tag_val:
                return tag
            tag = tag.succ_real_tag()

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
            mem.w32(addr + 4, data)
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
