from enum import IntEnum
from amitools.vamos.libstructs import TagItemStruct


class CommonTags(IntEnum):
    TAG_DONE = 0
    TAG_IGNORE = 1
    TAG_MORE = 2
    TAG_SKIP = 3
    TAG_USER = 1 << 31


ControlTags = [
    CommonTags.TAG_DONE,
    CommonTags.TAG_IGNORE,
    CommonTags.TAG_MORE,
    CommonTags.TAG_SKIP,
]


class Tag(TagItemStruct):
    def __repr__(self):
        return f"Tag(@{self.addr:08x})"

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
        if tag == CommonTags.TAG_DONE:
            return None
        elif tag == CommonTags.TAG_MORE:
            if data == 0:
                return None
            else:
                return Tag(self.mem, data)
        elif tag == CommonTags.TAG_SKIP:
            addr = self.addr + 8 * (1 + data)
            return Tag(self.mem, addr)
        else:
            return Tag(self.mem, self.addr + 8)

    def succ_real_tag(self):
        succ = self.succ_tag()
        if succ:
            return succ.next_real_tag()

    def get_tuple(self):
        return (self.tag.val, self.data.val)


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
        self.tag = Tag(mem, addr)
        self._alloc = None
        self._mem_obj = None

    def __iter__(self):
        return TagListIter(self.tag)

    def __len__(self):
        tag = self.tag.next_real_tag()
        num = 0
        while tag:
            tag = tag.succ_real_tag()
            num += 1
        return num

    def to_list(self):
        """convert tag list to python list"""
        tag = self.tag.next_real_tag()
        result = []
        while tag:
            result.append(tag.get_tuple())
            tag = tag.succ_real_tag()
        return result

    def find_tag(self, tag):
        """find tag in list and if found return Tag() or None"""
        tag = self.tag.next_real_tag()
        while tag:
            if tag.tag.val == tag:
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
            tag.tag.val = CommonTags.TAG_IGNORE
            return True
        else:
            return False

    @classmethod
    def alloc(cls, alloc, *tag_list, label=None):
        tag_list = list(tag_list)
        num_tags = len(tag_list)
        if num_tags == 0:
            tag_list.append((CommonTags.TAG_DONE, 0))
            num_tags == 1
        # auto add TAG DONE if missing
        elif tag_list[-1][0] != CommonTags.TAG_DONE:
            tag_list.append((CommonTags.TAG_DONE, 0))
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
