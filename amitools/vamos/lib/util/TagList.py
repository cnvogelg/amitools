from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import TagItemStruct

TAG_DONE = 0
TAG_IGNORE = 1
TAG_MORE = 2
TAG_SKIP = 3

TAG_USER = 1 << 31


class Tag:
    def __init__(self, tag, data, tag_info):
        self.user = tag & TAG_USER == TAG_USER
        self.tag = tag & ~TAG_USER
        self.data = data
        if tag_info != None and self.tag in tag_info:
            self.name = tag_info[self.tag]
        else:
            self.name = None

    def __str__(self):
        if self.user:
            return "(U:%s/%08x->%08x)" % (self.name, self.tag, self.data)
        else:
            return "(S:%s/%08x->%08x)" % (self.name, self.tag, self.data)


class TagList:
    def __init__(self, tag_info):
        self.tags = []
        self.tag_info = tag_info

    def add(self, tag, data):
        self.tags.append(Tag(tag, data, self.tag_info))

    def find_tag(self, tagname):
        for tag in self.tags:
            if tag.name == tagname:
                return tag
        return None

    def __str__(self):
        return "[%s]" % ",".join(map(str, self.tags))


def taglist_parse_tagitem_ptr(mem, addr, tag_info=None):
    result = TagList(tag_info)
    while True:
        tag = mem.r32(addr)
        data = mem.r32(addr + 4)
        if tag == TAG_DONE:
            break
        elif tag == TAG_IGNORE:
            addr += 8
        elif tag == TAG_SKIP:
            addr += 8 * (1 + data)
        elif tag == TAG_MORE:
            addr = data
        else:
            result.add(tag, data)
            addr += 8
    return result


def next_tag_item(ctx, ti_addr):
    if ti_addr == 0:
        return None
    while True:
        tag, data = get_tag(ctx, ti_addr)
        if tag == TAG_DONE:
            return None
        elif tag == TAG_MORE:
            ti_addr = data
            if data == 0:
                return None
        elif tag == TAG_IGNORE:
            ti_addr += 8
        elif tag == TAG_SKIP:
            ti_addr += 8 * (1 + data)
        else:
            return ti_addr


def get_tag(ctx, ti_addr):
    ti = AccessStruct(ctx.mem, TagItemStruct, ti_addr)
    tag = ti.r_s("ti_Tag")
    data = ti.r_s("ti_Data")
    return tag, data
