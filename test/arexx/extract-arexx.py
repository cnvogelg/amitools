#!/usr/bin/env python3
"""extract-arexx.py - populate test/arexx from AmigaOS 3.2.3 sources.

The extracted files are copyrighted AmigaOS binaries and must never be
committed.  The script scans the given sources for every known ARexx file,
verifies each one's SHA-1, decompresses ``.Z`` (LZW) members on the fly and
warns about any file that is missing.

Sources may be directories (scanned recursively), Amiga disk images
(``.adf``/``.adz``/``.hdf``/...) or any mix of both.  The simplest way is to
point it at the folder holding the original AmigaOS 3.2 / 3.2.3 disk images.

usage:
    python3 test/arexx/extract-arexx.py <source> [<source> ...] [-o OUT]
"""

import argparse
import hashlib
import os
import sys

# repo root is two levels above this script (test/arexx/<script>)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
sys.path.insert(1, REPO)

from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.ADFSVolume import ADFSVolume

# ---------------------------------------------------------------------------
# the known ARexx files: relative output path, source file name, version,
# SHA-1 and where the file lives in AmigaOS 3.2.3
#
# The bulk of the ARexx set is unchanged since AmigaOS 3.2 and lives on the
# Workbench 3.2 disk.  The 3.2.3 update only replaced rexxsupport.library and
# arexx.class (both shipped ``.Z`` compressed inside the update ADFs), so the
# expected hashes below describe the final 3.2.3 state.
# ---------------------------------------------------------------------------
AREXX_FILES = [
    # --- libraries ---
    ("Libs/rexxsyslib.library", "rexxsyslib.library", "47.2 (19.8.2019)",
     "54982a5e9919097050c3fe56cb319e20763e6326",
     "Workbench 3.2, Libs/"),
    ("Libs/rexxsupport.library", "rexxsupport.library", "47.2 (2.4.2023)",
     "d0d25ee6584eba401f62f18de7758e6fb886ed31",
     "3.2.3 update, Libs/rexxsupport.library.Z"),
    # --- ARexx master ---
    ("System/RexxMast", "RexxMast", "47.2 (5.8.2019)",
     "c5ff779e18ea2d15275f62ccab5746b2d66d2d5d",
     "Workbench 3.2, System/"),
    # --- BOOPSI class ---
    ("Classes/arexx.class", "arexx.class", "47.3 (3.6.2024)",
     "a4dd6d7051bf73dfd62c87c3a4e70447ac4f2617",
     "3.2.3 update, Classes/arexx.class.Z"),
    # --- ARexx host commands (REXX:) ---
    ("Rexxc/HI", "HI", "45.1 (7.12.2017)",
     "8c0be07a0a339f1386d55431cbfa1562349b8772", "Workbench 3.2, Rexxc/"),
    ("Rexxc/RX", "RX", "45.9 (14.1.2018)",
     "cb62bb549d954f889b46faf00e8655975eea3a89", "Workbench 3.2, Rexxc/"),
    ("Rexxc/RXC", "RXC", "45.1 (7.12.2017)",
     "f143b053179a100758f9e1943ae5fec1410513e5", "Workbench 3.2, Rexxc/"),
    ("Rexxc/RXLIB", "RXLIB", "45.1 (7.12.2017)",
     "ad6ed8b0adb785cd81f334a302ba3195a4b35370", "Workbench 3.2, Rexxc/"),
    ("Rexxc/RXSET", "RXSET", "45.1 (7.12.2017)",
     "361ee72cf92846c40d1b1b1726e05d7e53cba5eb", "Workbench 3.2, Rexxc/"),
    ("Rexxc/TCC", "TCC", "45.1 (7.12.2017)",
     "765c34d8a57367dba79925f97014a50040a962ec", "Workbench 3.2, Rexxc/"),
    ("Rexxc/TCO", "TCO", "45.1 (7.12.2017)",
     "8864f978ddfd47d88ccc6c591e899e682f86b081", "Workbench 3.2, Rexxc/"),
    ("Rexxc/TE", "TE", "45.1 (7.12.2017)",
     "b0daae98210379c522eec5ceae38d68ae2fc3757", "Workbench 3.2, Rexxc/"),
    ("Rexxc/TS", "TS", "45.1 (7.12.2017)",
     "13b27bd330fd0cd47b4006ecd8bbb14c843a727b", "Workbench 3.2, Rexxc/"),
    ("Rexxc/WaitForPort", "WaitForPort", "45.1 (7.12.2017)",
     "cf2a4fdbe02c712d7db36a86acda2936ffc46a48", "Workbench 3.2, Rexxc/"),
]

# extensions that are treated as Amiga disk images
DISK_EXTS = (".adf", ".adz", ".adf.gz", ".hdf", ".hdz", ".hdf.gz",
             ".rdb", ".rdisk", ".rdisk.gz")

# .Z compressed members are recognised case-insensitively
Z_SUFFIX = ".z"


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def file_sha1(path):
    with open(path, "rb") as f:
        return sha1(f.read())


def is_disk_image(path):
    lo = path.lower()
    return lo.endswith(DISK_EXTS)


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
    """scan a single Amiga disk image for known ARexx files"""
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
    """scan a plain host directory (recursively) for ARexx files and images"""
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


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+",
                    help="folders and/or Amiga disk images (scanned recursively)")
    ap.add_argument("-o", "--output", default=HERE,
                    help="output folder (default: this script's folder)")
    ap.add_argument("-v", "--verbose", action="store_true", help="show extra detail")
    args = ap.parse_args()

    for s in args.sources:
        if not os.path.exists(s):
            ap.error("not a folder or file: %s" % s)
    out_dir = os.path.abspath(args.output)
    os.makedirs(out_dir, exist_ok=True)

    names = {src.lower() for _, src, _, _, _ in AREXX_FILES}
    want = {sha: (out_rel, src, ver, where)
            for out_rel, src, ver, sha, where in AREXX_FILES}

    found = {}
    unknown = []
    for src in args.sources:
        print("scanning: %s" % src)
        scan_source(src, names, want, found, unknown, args.verbose)

    print("\n%-28s %-14s %s" % ("file", "version", "status"))
    print("-" * 78)
    missing = []
    ok = 0
    for out_rel, src, ver, sha, where in AREXX_FILES:
        out_path = os.path.join(out_dir, out_rel)
        if os.path.isfile(out_path) and file_sha1(out_path) == sha:
            print("%-28s %-14s present" % (out_rel, ver))
            ok += 1
        elif sha in found:
            blob, source, logical = found[sha]
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(blob)
            print("%-28s %-14s extracted <- %s" % (out_rel, ver, source))
            ok += 1
        else:
            print("%-28s %-14s MISSING" % (out_rel, ver))
            missing.append((out_rel, ver, where))

    if missing:
        print("\nWARNING: %d file(s) missing:" % len(missing))
        for out_rel, ver, where in missing:
            print("  - %s (%s): expected %s" % (out_rel, ver, where))
    if unknown:
        print("\nnote: %d matching-named file(s) did not match a known SHA-1 "
              "(run with -v to list)" % len(unknown))

    print("\n%d/%d ARexx files available in %s" % (ok, len(AREXX_FILES), out_dir))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
