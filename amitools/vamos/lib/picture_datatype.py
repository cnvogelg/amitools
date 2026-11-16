"""Decode bounded, palette-based ILBM pictures without host image codecs."""

import struct


def decode_ilbm(data):
    if len(data) < 12 or data[:4] != b"FORM" or data[8:12] != b"ILBM":
        raise ValueError("Not an ILBM picture")
    end = 8 + int.from_bytes(data[4:8], "big")
    if not 12 <= end <= len(data):
        raise ValueError("Truncated FORM")
    chunks = {}
    pos = 12
    while pos < end:
        if pos + 8 > end:
            raise ValueError("Truncated chunk header")
        ident, size = struct.unpack_from(">4sI", data, pos)
        pos += 8
        if pos + size + (size & 1) > end:
            raise ValueError("Truncated chunk")
        chunks[ident] = data[pos : pos + size]
        pos += size + (size & 1)
    header = chunks.get(b"BMHD", b"")
    if len(header) != 20 or b"BODY" not in chunks:
        raise ValueError("Missing picture header or body")
    width, height = struct.unpack_from(">HH", header)
    depth, masking, compression = header[8:11]
    cmap = chunks.get(b"CMAP", b"")
    mode = int.from_bytes(chunks.get(b"CAMG", bytes(4)), "big")
    if (
        not width
        or not height
        or not 1 <= depth <= 8
        or masking > 2
        or compression > 1
        or mode & 0x880
        or len(cmap) % 3
    ):
        raise ValueError("Unsupported ILBM picture mode")
    stride = ((width + 15) // 16) * 2
    if stride * height * (depth + (masking == 1)) > 4 * 1024 * 1024:
        raise ValueError("Picture exceeds guest bitmap limit")
    body = chunks[b"BODY"]
    planes = [bytearray() for _ in range(depth + (masking == 1))]
    pos = 0
    for y in range(height):
        for plane in planes:
            row = bytearray()
            while len(row) < stride:
                if pos >= len(body):
                    raise ValueError("Truncated bitmap")
                if not compression:
                    row.extend(body[pos : pos + stride])
                    pos += stride
                    break
                count = body[pos]
                pos += 1
                if count <= 127:
                    row.extend(body[pos : pos + count + 1])
                    pos += count + 1
                elif count != 128:
                    if pos >= len(body):
                        raise ValueError("Truncated ByteRun1 repeat")
                    row.extend(bytes([body[pos]]) * (257 - count))
                    pos += 1
            if len(row) != stride:
                raise ValueError("ByteRun1 crosses a plane row")
            plane.extend(row)
    mask = planes.pop() if masking == 1 else None
    if masking == 2:
        transparent = int.from_bytes(header[12:14], "big")
        mask = bytearray(stride * height)
        for y in range(height):
            for x in range(width):
                offset, bit = y * stride + x // 8, 0x80 >> (x & 7)
                color = sum(
                    (1 << i) for i, plane in enumerate(planes) if plane[offset] & bit
                )
                if color != transparent:
                    mask[offset] |= bit
    return header, planes, mask, cmap, mode
