import os
import io
import struct
import zlib
from dataclasses import dataclass


class BadASFFile(Exception):
    pass


@dataclass
class Chunk:
    tag: str = None
    size: int = 0
    flags: int = 0
    offset: int = 0
    total_size: int = 0
    uncompressed_size: int = 0

    def read(self, fp):
        self.fp = fp
        buf = fp.read(8)
        raw_tag, size = struct.unpack(">4sI", buf)
        self.offset = fp.tell()
        self.tag = raw_tag.decode("ascii")
        self.size = size - 8
        self.uncompressed_size = size
        self.flags = 0
        if size > 8:
            buf = fp.read(4)
            self.flags = struct.unpack(">I", buf)[0]
            self.offset += 4
            self.size -= 4
            if self.flags & 1 == 1:
                buf = fp.read(4)
                self.uncompressed_size = struct.unpack(">I", buf)[0]
                self.offset += 4
                self.size -= 4

        # bogus END: no align?
        if self.tag == "END ":
            self.total_size = 8
        else:
            self.total_size = self._align(size) + size

    def read_data(self):
        if self.size == 0:
            return None
        if self.fp.tell() != self.offset:
            self.fp.seek(self.offset, 0)
        data = self.fp.read(self.size)
        # align?
        align = self._align(self.size)
        self.fp.read(align)
        # uncompress data?
        if self.flags & 1 == 1:
            data = zlib.decompress(data)
            assert len(data) == self.uncompressed_size
        return data

    def skip_data(self):
        if self.size == 0:
            return
        # move forward without header
        size = self.size + self._align(self.size)
        self.fp.seek(size, os.SEEK_CUR)

    def _align(self, size):
        # bogus alignment: if already aligned on long it adds 4 dummy bytes???
        align = 4 - (size & 3)
        return align


class ASFFile:
    def __init__(self, file, mode="r"):
        if mode not in ("r", "w"):
            raise ValueError("ASSFile mode must be 'r' or 'w'")
        self.file = file
        self.fp = None
        if isinstance(file, os.PathLike):
            file = os.fspath(file)
        if isinstance(file, str):
            self.filename = file
            self.fp = io.open(file, mode + "+b")
        else:
            self.fp = file
            self.filename = getattr(file, "name", None)

        if mode == "r":
            self.fp.seek(0, os.SEEK_END)
            self.total_size = self.fp.tell()
            self.fp.seek(0, os.SEEK_SET)
            self._read_header()
            self.chunks = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def __repr__(self):
        result = ["<%s.%s" % (self.__class__.__module__, self.__class__.__qualname__)]
        if self.fp is not None:
            if self._filePassed:
                result.append(" file=%r" % self.fp)
            elif self.filename is not None:
                result.append(" filename=%r" % self.filename)
            result.append(" mode=%r" % self.mode)
        else:
            result.append(" [closed]")
        result.append(">")
        return "".join(result)

    def __del__(self):
        self.close()

    def close(self):
        if self.fp:
            self.fp.close()
            self.fp = None

    def chunklist(self):
        """return list of chunks found in file"""
        if not self.chunks:
            self._read_chunklist()
        return self.chunks

    def get_chunk(self, tag):
        chunks = self.chunklist()
        for chunk in chunks:
            if chunk.tag == tag:
                return chunk

    def get_all_chunks(self, tag):
        result = []
        chunks = self.chunklist()
        for chunk in chunks:
            if chunk.tag == tag:
                result.append(chunk)
        return result

    def load_chunk(self, tag):
        chunk = self.get_chunk(tag)
        if chunk:
            return chunk.read_data()

    def load_all_chunks(self, tag):
        chunks = self.get_all_chunks(tag)
        if chunks:
            return list(map(lambda x: x.read_data(), chunks))

    def _read_chunklist(self):
        chunks = []
        left = self.total_size
        self.fp.seek(self.main_offset, 0)
        while left > 0:
            chunk = Chunk()
            chunk.read(self.fp)
            chunk.skip_data()
            left -= chunk.total_size
            chunks.append(chunk)
        self.chunks = chunks

    def _read_header(self):
        hdr = Chunk()
        hdr.read(self.fp)
        if hdr.tag != "ASF ":
            raise BadASFFile()
        data = hdr.read_data()
        # skip long
        offset = 4
        # header
        self.emu_name, offset = self._read_string(data, offset)
        self.emu_version, offset = self._read_string(data, offset)
        self.desc, offset = self._read_string(data, offset)
        assert offset == hdr.size
        self.total_size -= hdr.total_size
        self.main_offset = hdr.total_size

    def _read_string(self, buf, off):
        data = bytearray()
        while buf[off] != 0:
            data.append(buf[off])
            off += 1
        txt = data.decode("utf-8")
        return txt, off + 1
