import struct
import io


class HunkDebugLineEntry:
    def __init__(self, offset, src_line):
        self.offset = offset
        self.src_line = src_line

    def __str__(self):
        return "[+%08x: %d]" % (self.offset, self.src_line)

    def get_offset(self):
        return self.offset

    def get_src_line(self):
        return self.src_line


class HunkDebugLine:
    """structure to hold source line info"""

    def __init__(self, src_file, base_offset):
        self.tag = "LINE"
        self.src_file = src_file
        self.base_offset = base_offset
        self.entries = []

    def add_entry(self, offset, src_line):
        self.entries.append(HunkDebugLineEntry(offset, src_line))

    def __str__(self):
        prefix = "{%s,%s,@%08x:" % (self.tag, self.src_file, self.base_offset)
        return prefix + ",".join(map(str, self.entries)) + "}"

    def get_src_file(self):
        return self.src_file

    def get_base_offset(self):
        return self.base_offset

    def get_entries(self):
        return self.entries


class HunkDebugAny:
    def __init__(self, tag, data, base_offset):
        self.tag = tag
        self.data = data
        self.base_offset = base_offset

    def __str__(self):
        return "{%s,%d,%s}" % (self.tag, self.base_offset, self.data)


class HunkDebug:
    def encode(self, debug_info):
        """encode a debug info and return a debug_data chunk"""
        out = io.StringIO()
        # +0: base offset
        self._write_long(out, debug_info.base_offset)
        # +4: type tag
        tag = debug_info.tag
        out.write(tag)
        if tag == "LINE":
            # file name
            self._write_string(out, debug_info.src_file)
            # entries
            for e in debug_info.entries:
                self._write_long(out, e.src_line)
                self._write_long(out, e.offset)
        elif tag == "HEAD":
            out.write("DBGV01\0\0")
            out.write(debug_info.data)
        else:  # any
            out.write(debug_info.data)
        # retrieve result
        res = out.getvalue()
        out.close()
        return res

    def decode(self, debug_data):
        """decode a data block from a debug hunk"""
        if len(debug_data) < 12:
            return None
        # +0: base_offset for file
        base_offset = self._read_long(debug_data, 0)
        # +4: tag
        tag = debug_data[4:8]
        if tag == "LINE":  # SAS/C source line info
            # +8: string file name
            src_file, src_size = self._read_string(debug_data, 8)
            dl = HunkDebugLine(src_file, base_offset)
            off = 12 + src_size
            num = (len(debug_data) - off) // 8
            for i in range(num):
                src_line = self._read_long(debug_data, off)
                offset = self._read_long(debug_data, off + 4)
                off += 8
                dl.add_entry(offset, src_line)
            return dl
        elif tag == "HEAD":
            tag2 = debug_data[8:16]
            assert tag2 == "DBGV01\0\0"
            data = debug_data[16:]
            return HunkDebugAny(tag, data, base_offset)
        else:
            data = debug_data[8:]
            return HunkDebugAny(tag, data, base_offset)

    def _read_string(self, buf, pos):
        size = self._read_long(buf, pos) * 4
        off = pos + 4
        data = buf[off : off + size]
        pos = data.find("\0")
        if pos == 0:
            return "", size
        elif pos != -1:
            return data[:pos], size
        else:
            return data, size

    def _write_string(self, f, s):
        n = len(s)
        num_longs = int((n + 3) / 4)
        self._write_long(f, num_longs)
        add = num_longs * 4 - n
        if add > 0:
            s += "\0" * add
        f.write(s)

    def _read_long(self, buf, pos):
        return struct.unpack_from(">I", buf, pos)[0]

    def _write_long(self, f, v):
        data = struct.pack(">I", v)
        f.write(data)


# ----- mini test -----
if __name__ == "__main__":
    import sys
    from .HunkBlockFile import HunkBlockFile, HunkDebugBlock

    hd = HunkDebug()
    for a in sys.argv[1:]:
        hbf = HunkBlockFile()
        hbf.read_path(a)
        for blk in hbf.get_blocks():
            if isinstance(blk, HunkDebugBlock):
                # decode debug data
                dd = hd.decode(blk.debug_data)
                print(a, "->", dd.tag)
                # now encode again
                new_debug_data = hd.encode(dd)
                # compare!
                assert new_debug_data == blk.debug_data
