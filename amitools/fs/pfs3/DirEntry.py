"""PFS3 directory entries and their extra fields"""

import struct

from .Const import (
    CMSIZE,
    DIRENTRY_HEADER,
    EXTRA_FSIZEX,
    EXTRA_GID,
    EXTRA_LINK_HI,
    EXTRA_LINK_LO,
    EXTRA_MASK,
    EXTRA_NUM,
    EXTRA_PROT_HI,
    EXTRA_PROT_LO,
    EXTRA_ROLL_HI,
    EXTRA_ROLL_LO,
    EXTRA_UID,
    EXTRA_VSIZE_HI,
    EXTRA_VSIZE_LO,
    FNSIZE,
    MAX_ENTRYSIZE,
    ST_FILE,
    ST_LINKDIR,
    ST_LINKFILE,
    ST_USERDIR,
    TYPE_NAMES,
)


class DirEntryError(Exception):
    pass


def entry_base_size(nlen, clen):
    """size of an entry without extra fields: 19 + n + c rounded up to even"""
    return (20 + nlen + clen) & ~1


class DirEntry:
    """one directory entry. The extra fields are kept as values: link, uid,
    gid, prot (bits 8..31), virtualsize, rollpointer and fsizex"""

    def __init__(
        self,
        type=ST_FILE,
        anode=0,
        fsize=0,
        date=(0, 0, 0),
        protection=0,
        name=b"",
        comment=b"",
        link=0,
        uid=0,
        gid=0,
        prot=0,
        virtualsize=0,
        rollpointer=0,
        fsizex=0,
        has_extra=True,
    ):
        self.type = type
        self.anode = anode
        self.fsize = fsize
        self.date = tuple(date)
        self.protection = protection
        self.name = bytes(name)
        self.comment = bytes(comment)
        self.link = link
        self.uid = uid
        self.gid = gid
        self.prot = prot
        self.virtualsize = virtualsize
        self.rollpointer = rollpointer
        self.fsizex = fsizex
        # write a flags word (MODE_DIR_EXTENSION)
        self.has_extra = has_extra

    def copy(self):
        e = DirEntry()
        e.__dict__.update(self.__dict__)
        return e

    def __repr__(self):
        return "DirEntry(%s %r anode=%d size=%d)" % (
            TYPE_NAMES.get(self.type, str(self.type)),
            self.name,
            self.anode,
            self.get_size(True),
        )

    # ----- values -----

    def get_protect32(self):
        return (self.prot & 0xFFFFFF00) | (self.protection & 0xFF)

    def set_protect32(self, protect):
        self.protection = protect & 0xFF
        self.prot = protect & 0xFFFFFF00

    def get_size(self, largefile):
        if largefile:
            return self.fsize | (self.fsizex << 32)
        return self.fsize

    def set_size(self, size):
        self.fsize = size & 0xFFFFFFFF
        self.fsizex = (size >> 32) & 0xFFFF

    def is_dir(self):
        return self.type == ST_USERDIR

    def is_link(self):
        return self.type in (ST_LINKDIR, ST_LINKFILE)

    # ----- parse -----

    @classmethod
    def parse(cls, data, off, end, dir_extension):
        """parse the entry at data[off:]. end is the end of the entry area.
        Returns the entry and its size. Raises DirEntryError for an entry
        that does not fit its rules"""
        if off >= end:
            raise DirEntryError("entry beyond entry area")
        size = data[off]
        if size == 0:
            return None, 0
        if size & 1 or size < 20:
            raise DirEntryError("invalid entry size %d" % size)
        if off + size > end:
            raise DirEntryError("entry crosses the end of the block")
        typ = struct.unpack_from(">b", data, off + 1)[0]
        anode, fsize = struct.unpack_from(">II", data, off + 2)
        date = struct.unpack_from(">HHH", data, off + 10)
        protection = data[off + 16]
        nlen = data[off + 17]
        if nlen >= FNSIZE:
            raise DirEntryError("name length %d too long" % nlen)
        if DIRENTRY_HEADER + nlen >= size:
            raise DirEntryError("name does not fit entry")
        name = bytes(data[off + 18 : off + 18 + nlen])
        clen = data[off + 18 + nlen]
        if clen >= CMSIZE:
            raise DirEntryError("comment length %d too long" % clen)
        if 0x13 + nlen + clen > size:
            raise DirEntryError("comment does not fit entry")
        comment = bytes(data[off + 19 + nlen : off + 19 + nlen + clen])
        e = cls(
            type=typ,
            anode=anode,
            fsize=fsize,
            date=date,
            protection=protection,
            name=name,
            comment=comment,
            has_extra=dir_extension,
        )
        base = entry_base_size(nlen, clen)
        if dir_extension and size >= base + 2:
            words = [0] * EXTRA_NUM
            p = off + size - 2
            flags = struct.unpack_from(">H", data, p)[0] & EXTRA_MASK
            for i in range(EXTRA_NUM):
                if flags & (1 << i):
                    p -= 2
                    if p < off + base:
                        raise DirEntryError("extra fields overlap name")
                    words[i] = struct.unpack_from(">H", data, p)[0]
            e.link = (words[EXTRA_LINK_HI] << 16) | words[EXTRA_LINK_LO]
            e.uid = words[EXTRA_UID]
            e.gid = words[EXTRA_GID]
            e.prot = (words[EXTRA_PROT_HI] << 16) | (words[EXTRA_PROT_LO] & 0xFF00)
            e.virtualsize = (words[EXTRA_VSIZE_HI] << 16) | words[EXTRA_VSIZE_LO]
            e.rollpointer = (words[EXTRA_ROLL_HI] << 16) | words[EXTRA_ROLL_LO]
            e.fsizex = words[EXTRA_FSIZEX]
        return e, size

    # ----- build -----

    def _extra_words(self):
        return [
            (self.link >> 16) & 0xFFFF,
            self.link & 0xFFFF,
            self.uid & 0xFFFF,
            self.gid & 0xFFFF,
            (self.prot >> 16) & 0xFFFF,
            self.prot & 0xFF00,
            (self.virtualsize >> 16) & 0xFFFF,
            self.virtualsize & 0xFFFF,
            (self.rollpointer >> 16) & 0xFFFF,
            self.rollpointer & 0xFFFF,
            self.fsizex & 0xFFFF,
        ]

    def get_entry_size(self):
        size = entry_base_size(len(self.name), len(self.comment))
        if self.has_extra:
            size += 2 + 2 * sum(1 for w in self._extra_words() if w)
        return size

    def build(self):
        """the entry as bytes. Only non-zero extra words are stored"""
        nlen = len(self.name)
        clen = len(self.comment)
        if nlen == 0 or nlen >= FNSIZE:
            raise DirEntryError("invalid name length %d" % nlen)
        if clen >= CMSIZE:
            raise DirEntryError("invalid comment length %d" % clen)
        size = self.get_entry_size()
        if size > MAX_ENTRYSIZE:
            raise DirEntryError("entry too large: %d" % size)
        b = bytearray(size)
        b[0] = size
        struct.pack_into(">b", b, 1, self.type)
        struct.pack_into(">II", b, 2, self.anode, self.fsize)
        struct.pack_into(">HHH", b, 10, *self.date)
        b[16] = self.protection & 0xFF
        b[17] = nlen
        b[18 : 18 + nlen] = self.name
        b[18 + nlen] = clen
        b[19 + nlen : 19 + nlen + clen] = self.comment
        if self.has_extra:
            words = self._extra_words()
            flags = 0
            p = size - 2
            for i, w in enumerate(words):
                if w:
                    flags |= 1 << i
                    p -= 2
                    struct.pack_into(">H", b, p, w)
            struct.pack_into(">H", b, size - 2, flags)
        else:
            if self.link or self.uid or self.gid or self.prot or self.fsizex:
                raise DirEntryError("extra fields need MODE_DIR_EXTENSION")
            if self.virtualsize or self.rollpointer:
                raise DirEntryError("extra fields need MODE_DIR_EXTENSION")
        return bytes(b)


def name_upper(name):
    """the upper case form PFS3 compares names in"""
    out = bytearray(name)
    for i, c in enumerate(out):
        if 0x61 <= c <= 0x7A or 0xE0 <= c <= 0xF6 or 0xF8 <= c <= 0xFE:
            out[i] = c - 0x20
    return bytes(out)
