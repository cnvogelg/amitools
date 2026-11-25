#!/usr/bin/env python3
"""extract-shell-seg.py - populate test/shell-seg from disk images and Kickstart ROMs.

The extracted files are copyrighted AmigaOS binaries and must never be
committed.  The script extracts every known shell it can find, verifies each
one's SHA-1, and warns about any that are missing.

usage:
    python3 test/shell-seg/extract-shell-seg.py <disk-dir> <kickstart-dir> [-o OUT]
"""

import argparse
import hashlib
import importlib
import io
import os
import sys

# repo root is two levels above this script (test/shell-seg/<script>)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
sys.path.insert(1, REPO)

BlkDevFactory = importlib.import_module(
    "amitools.fs.blkdev.BlkDevFactory"
).BlkDevFactory
ADFSVolume = importlib.import_module("amitools.fs.ADFSVolume").ADFSVolume
RomSplitter = importlib.import_module("amitools.rom.romsplitter").RomSplitter
BinFmtHunk = importlib.import_module("amitools.binfmt.hunk.BinFmtHunk").BinFmtHunk

# ---------------------------------------------------------------------------
# the known Shell-Seg files: name, SHA-1, kind, AmigaOS release, where it lives
# ---------------------------------------------------------------------------
SHELL_SEGS = [
    (
        "Shell-Seg-1.3",
        "4bbe3ccb55fab49c83ff7ab52b2af277e6d92429",
        "disk",
        "AmigaOS 1.3",
        "L/Shell-Seg on Workbench 1.3 (no $VER)",
    ),
    (
        "Shell-Seg-37.69",
        "40a54732afd46a4649e53088e722da0e0f4e6900",
        "rom",
        "AmigaOS 2.x",
        "shell resident in Kickstart 37.175",
    ),
    (
        "Shell-Seg-39.13",
        "0534b29813f87247d9bdd8f02c25e6ebe58fe699",
        "rom",
        "AmigaOS 3.0",
        "shell resident in Kickstart 39.106",
    ),
    (
        "Shell-Seg-40.2",
        "02ba4b4368ed89177acfc17b45cbde4ae2062d2a",
        "rom",
        "AmigaOS 3.1",
        "shell resident in Kickstart 40.68",
    ),
    (
        "Shell-Seg-45.7",
        "f091f33d28abe5c55de0e881d16861dfc703df01",
        "rom",
        "AmigaOS 3.9",
        "shell resident in Kickstart 45.66 (Cloanto OS 3.X)",
    ),
    (
        "Shell-Seg-46.10",
        "8609de3b11da6b5d40d375a8d383fa2513316b28",
        "disk",
        "AmigaOS 3.1.4",
        "L/Shell-Seg on the Modules 3.1.4 disks",
    ),
    (
        "Shell-Seg-47.47",
        "0fe2a77ee989b343149f234ec7935aee2e0339f8",
        "disk",
        "AmigaOS 3.2",
        "L/Shell-Seg on the Modules 3.2 disk",
    ),
    (
        "Shell-Seg-47.48",
        "2be0093a67cacf6efec1258d5bd91db4ee7f1f6f",
        "disk",
        "AmigaOS 3.2.1-3.2.3",
        "L/Shell-Seg on the Modules 3.2.1 disk",
    ),
]

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


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def file_sha1(path):
    with open(path, "rb") as f:
        return sha1(f.read())


def iter_files(root, exts):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            if fn.lower().endswith(exts):
                yield os.path.join(dirpath, fn)


def walk_dir(node):
    for child in node.get_entries():
        if child.is_dir():
            yield from walk_dir(child)
        elif child.is_file():
            yield child


def scan_disks(disk_dir, want, verbose=False):
    """find Shell-Seg files on disk images. returns {sha1: (data, source)}"""
    factory = BlkDevFactory()
    found = {}
    unknown = []
    for path in iter_files(disk_dir, DISK_EXTS):
        try:
            blkdev = factory.open(path, read_only=True)
        except Exception:
            continue  # not a usable Amiga disk image (game, non-standard, ...)
        try:
            vol = ADFSVolume(blkdev)
            vol.open()
            root = vol.get_root_dir()
            root.read(recursive=True)
            for node in walk_dir(root):
                name = node.name.name.get_ami_str().decode("latin-1")
                if name.lower() != "shell-seg":
                    continue
                data = bytes(node.get_file_data())
                digest = sha1(data)
                if digest in want:
                    found.setdefault(digest, (data, path))
                else:
                    unknown.append((path, digest))
                    if verbose:
                        print("  ? unknown Shell-Seg %s in %s" % (digest[:12], path))
        except Exception as e:
            if verbose:
                print("  ! cannot read %s: %s" % (path, e))
        finally:
            blkdev.close()
    return found, unknown


def scan_roms(kickstart_dir, want, verbose=False):
    """extract shell residents from Kickstart ROMs. returns {sha1: (data, source)}"""
    rs = RomSplitter()
    bfh = BinFmtHunk()
    found = {}
    unknown = []
    for path in iter_files(kickstart_dir, (".rom",)):
        try:
            rom = rs.find_rom(path)
        except Exception:
            continue
        if rom is None:
            if verbose:
                print("  - %s not in ROM split database, skipped" % path)
            continue
        for entry in rs.get_all_entries():
            if not entry.name.lower().startswith("shell"):
                continue
            try:
                img = rs.extract_bin_img(entry)
            except Exception:
                continue
            buf = io.BytesIO()
            bfh.save_image_fobj(buf, img)
            data = buf.getvalue()
            digest = sha1(data)
            if digest in want:
                found.setdefault(digest, (data, path))
            else:
                unknown.append((path, digest))
                if verbose:
                    print("  ? unknown %s (%s) in %s" % (entry.name, digest[:12], path))
    return found, unknown


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "disk_dir", help="folder with Amiga disk images (scanned recursively)"
    )
    ap.add_argument(
        "kickstart_dir", help="folder with Kickstart ROMs (scanned recursively)"
    )
    ap.add_argument(
        "-o",
        "--output",
        default=HERE,
        help="output folder (default: this script's folder)",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="show extra detail")
    args = ap.parse_args()

    for d in (args.disk_dir, args.kickstart_dir):
        if not os.path.isdir(d):
            ap.error("not a folder: %s" % d)
    out_dir = os.path.abspath(args.output)
    os.makedirs(out_dir, exist_ok=True)

    want = {
        sha: (name, kind, release, detail)
        for name, sha, kind, release, detail in SHELL_SEGS
    }

    print("scanning disk images: %s" % args.disk_dir)
    disk_found, disk_unknown = scan_disks(args.disk_dir, want, args.verbose)
    print("scanning Kickstart ROMs: %s" % args.kickstart_dir)
    rom_found, rom_unknown = scan_roms(args.kickstart_dir, want, args.verbose)

    # disk copies win over ROM reconstructions when both exist
    found = dict(rom_found)
    found.update(disk_found)

    print("\n%-18s %-8s %s" % ("file", "SHA-1", "status"))
    print("-" * 72)
    missing = []
    ok = 0
    for name, sha, kind, release, detail in SHELL_SEGS:
        out_path = os.path.join(out_dir, name)
        if os.path.isfile(out_path) and file_sha1(out_path) == sha:
            print("%-18s %s  present" % (name, sha[:12]))
            ok += 1
        elif sha in found:
            data, src = found[sha]
            with open(out_path, "wb") as f:
                f.write(data)
            print("%-18s %s  extracted <- %s" % (name, sha[:12], src))
            ok += 1
        else:
            print("%-18s %s  MISSING" % (name, sha[:12]))
            missing.append((name, release, detail))

    if missing:
        print("\nWARNING: %d shell(s) missing:" % len(missing))
        for name, release, detail in missing:
            print("  - %s (%s): expected %s" % (name, release, detail))
    if disk_unknown or rom_unknown:
        print(
            "\nnote: %d unknown Shell-Seg shell module(s) were skipped "
            "(run with -v to list)" % (len(disk_unknown) + len(rom_unknown))
        )

    print("\n%d/%d shells available in %s" % (ok, len(SHELL_SEGS), out_dir))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
