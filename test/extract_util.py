#!/usr/bin/env python3
"""extract_util.py - shared helpers for the AmigaOS test-fixture extractors.

The ``test/arexx`` and ``test/cli`` fixtures are populated from the original
(copyrighted) AmigaOS disk images.  Their extractors share the Amiga disk-image
scanning, the SHA-1 helpers, the name matching and the Unix ``compress``
(``.Z``) LZW decoder used for the AmigaOS 3.2.3 update members.

Importing this module needs the repository root on ``sys.path`` so that
``amitools`` can be imported; the extractors set that up before importing it.
"""

import hashlib
import os

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory

# extensions that are treated as Amiga disk images
DISK_EXTS = (
    ".adf",
    ".adz",
    ".adf.gz",
    ".hdf",
    ".hdz",
    ".hdf.gz",
    ".rdb",
    ".rdisk",
    ".rdisk.gz",
)

# .Z compressed members are recognised case-insensitively
Z_SUFFIX = ".z"


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def file_sha1(path):
    with open(path, "rb") as f:
        return sha1(f.read())


def is_disk_image(path):
    return path.lower().endswith(DISK_EXTS)


# ---------------------------------------------------------------------------
# minimal Unix 'compress' (.Z) decompressor
#
# AmigaOS update disks store some binaries as ``.Z`` members.  There is no
# standard Python module for the LZW format used by compress(1), so a small
# decoder is included here.
# ---------------------------------------------------------------------------
def decompress_z(data):
    """decompress a Unix compress(1) '.Z' stream (LZW, 9..16 bit codes)"""
    if len(data) < 3 or data[0] != 0x1F or data[1] != 0x9D:
        raise ValueError("not a .Z stream")
    flags = data[2]
    max_bits = flags & 0x1F
    block_mode = bool(flags & 0x80)
    if max_bits < 9 or max_bits > 16:
        raise ValueError("unsupported .Z max bits: %d" % max_bits)
    max_max_code = 1 << max_bits

    # bit reader: codes are packed LSB first
    pos = 3
    bit_buf = 0
    bit_cnt = 0

    def get_code(nbits):
        nonlocal pos, bit_buf, bit_cnt
        while bit_cnt < nbits:
            if pos >= len(data):
                return None
            bit_buf |= data[pos] << bit_cnt
            pos += 1
            bit_cnt += 8
        code = bit_buf & ((1 << nbits) - 1)
        bit_buf >>= nbits
        bit_cnt -= nbits
        return code

    clear_code = 256
    # prefix/suffix tables; literals are their own suffix
    prefix = [0] * max_max_code
    suffix = list(range(256)) + [0] * (max_max_code - 256)

    # current code width and first free dictionary slot (set by reset())
    n_bits = 9
    max_code = (1 << n_bits) - 1
    free_ent = 257 if block_mode else 256

    def reset():
        nonlocal n_bits, max_code, free_ent
        n_bits = 9
        max_code = (1 << n_bits) - 1
        free_ent = 257 if block_mode else 256

    reset()
    out = bytearray()
    old_code = -1
    fin_char = 0

    while True:
        code = get_code(n_bits)
        if code is None:
            break
        if code == clear_code and block_mode:
            reset()
            old_code = -1
            continue
        if old_code == -1:
            if code >= 256:
                raise ValueError("bad first .Z code")
            out.append(code)
            fin_char = code
            old_code = code
            continue
        in_code = code
        stack = bytearray()
        if code >= free_ent:
            stack.append(fin_char)
            code = old_code
        while code >= 256:
            stack.append(suffix[code])
            code = prefix[code]
        fin_char = suffix[code]
        stack.append(fin_char)
        out.extend(reversed(stack))
        if free_ent < max_max_code:
            prefix[free_ent] = old_code
            suffix[free_ent] = fin_char
            free_ent += 1
            if free_ent > max_code and n_bits < max_bits:
                n_bits += 1
                max_code = (1 << n_bits) - 1
        old_code = in_code

    return bytes(out)


def candidate_blobs(name, data):
    """yield (logical_name, blob) for a file, adding the .Z decompressed form"""
    yield name, data
    if name.lower().endswith(Z_SUFFIX):
        try:
            yield name[: -len(Z_SUFFIX)], decompress_z(data)
        except (ValueError, IndexError):
            pass


# ---------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------
def walk_volume(node):
    """yield all file nodes of an opened Amiga volume recursively"""
    for child in node.get_entries():
        if child.is_dir():
            yield from walk_volume(child)
        elif child.is_file():
            yield child


def wanted_name(base, names):
    """is a file base name (optionally with a .Z suffix) a wanted source?"""
    lo = base.lower()
    if lo in names:
        return True
    if lo.endswith(Z_SUFFIX):
        return lo[: -len(Z_SUFFIX)] in names
    return False


def check_blobs(source, base, data, names, want, found, unknown, verbose):
    """match the raw/decompressed content of one file against the wanted set"""
    for logical, blob in candidate_blobs(base, data):
        if logical.lower() not in names:
            continue
        digest = sha1(blob)
        if digest in want:
            found.setdefault(digest, (blob, source, logical))
        else:
            unknown.append((source, logical, digest))
            if verbose:
                print("  ? unknown %s (%s) in %s" % (logical, digest[:12], source))


def scan_disk(path, names, want, found, unknown, verbose):
    """scan a single Amiga disk image for wanted files"""
    factory = BlkDevFactory()
    blkdev = None
    try:
        blkdev = factory.open(path, read_only=True)
        vol = ADFSVolume(blkdev)
        vol.open()
        root = vol.get_root_dir()
        root.read(recursive=True)
        for node in walk_volume(root):
            name = node.name.name.get_ami_str().decode("latin-1")
            base = os.path.basename(name)
            if not wanted_name(base, names):
                continue
            data = bytes(node.get_file_data())
            check_blobs(path, base, data, names, want, found, unknown, verbose)
    except Exception as e:
        if verbose:
            print("  ! cannot read %s: %s" % (path, e))
    finally:
        if blkdev is not None:
            blkdev.close()


def scan_file(path, names, want, found, unknown, verbose):
    """scan one host file, either as a disk image or as a plain file"""
    if is_disk_image(path):
        scan_disk(path, names, want, found, unknown, verbose)
        return
    fn = os.path.basename(path)
    if not wanted_name(fn, names):
        return
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return
    check_blobs(path, fn, data, names, want, found, unknown, verbose)


def scan_tree(root_dir, names, want, found, unknown, verbose):
    """scan a plain host directory (recursively) for wanted files and images"""
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        for fn in sorted(filenames):
            scan_file(os.path.join(dirpath, fn), names, want, found, unknown, verbose)


def scan_source(src, names, want, found, unknown, verbose):
    if os.path.isdir(src):
        scan_tree(src, names, want, found, unknown, verbose)
    elif os.path.isfile(src):
        scan_file(src, names, want, found, unknown, verbose)
    else:
        print("warning: skipping missing source: %s" % src)


def scan_sources(sources, names, want, verbose=False):
    """scan every source and return (found, unknown).

    ``found`` maps a SHA-1 to ``(blob, source, logical_name)``; ``unknown``
    collects same-named files whose SHA-1 did not match the wanted set.
    """
    found = {}
    unknown = []
    for src in sources:
        print("scanning: %s" % src)
        scan_source(src, names, want, found, unknown, verbose)
    return found, unknown
