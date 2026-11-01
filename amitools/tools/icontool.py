#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

WB_DISKMAGIC = 0xE310

# DiskObject fixed header length used by Deark
DISKOBJECT_LEN = 78

# Offsets (absolute) in DiskObject, matching the Deark scan
OFF_VERSION = 2

# Embedded Gadget starts at offset 4, length 44
OFF_GADGET = 4
GADGET_LEN = 44

# canvas width/height (Deark reads at absolute offsets 12/14)
OFF_MAIN_CANVAS_W = 12
OFF_MAIN_CANVAS_H = 14

# Deark reads SelectRender pointer at absolute offset 26 (used to infer 1 vs 2 icons)
OFF_SELECTRENDER_PTR = 26

# Deark reads icon revision at absolute offset 44 (low byte)
OFF_ICON_REVISION = 44

# icon type byte at 48
OFF_ICON_TYPE = 48

# presence fields (Deark uses nonzero to decide segment exists)
OFF_DEFAULTTOOL_PRESENCE = 50
OFF_TOOLTYPES_PRESENCE = 54
OFF_DRAWERDATA_PRESENCE = 66
OFF_TOOLWINDOW_PRESENCE = 70

# DiskObject icon position fields (LONG). This is what Workbench uses for placement.
OFF_CURRENTX = 58  # 0x3A
OFF_CURRENTY = 62  # 0x3E

# DrawerData segment size in Deark
DRAWERDATA_LEN = 56
# DrawerData begins with embedded NewWindow; Width/Height are the 3rd/4th WORDs
DD_NEWWIN_WIDTH_OFF = 4
DD_NEWWIN_HEIGHT_OFF = 6

# DrawerData2 length for revision==1 (Deark)
DRAWERDATA2_LEN = 6

# ToolTypes table encoding per Deark:
# u32 num_entries_raw; num_entries = num_entries_raw/4 - 1
# then for each entry: u32 tlen, then tlen bytes data
MAX_TOOLTYPES = 1000
MAX_TLEN = 10000

_tt_paren_re = re.compile(r"^\((.*)\)$")

def be_u16(b: bytes, off: int) -> int:
    return struct.unpack_from(">H", b, off)[0]

def be_u32(b: bytes, off: int) -> int:
    return struct.unpack_from(">I", b, off)[0]

def be_i32(b: bytes, off: int) -> int:
    return struct.unpack_from(">i", b, off)[0]

def put_be_i32(buf: bytearray, off: int, v: int) -> None:
    struct.pack_into(">i", buf, off, int(v))

def put_be_u16(buf: bytearray, off: int, v: int) -> None:
    if not (0 <= v <= 0xFFFF):
        raise ValueError("UWORD out of range")
    struct.pack_into(">H", buf, off, int(v))

def u32_at(buf: bytes, pos: int, strict: bool) -> Tuple[int, int]:
    if pos + 4 > len(buf):
        if strict:
            raise ValueError("Out of range reading u32")
        return 0, pos
    return be_u32(buf, pos), pos + 4

def is_diskobject(buf: bytes) -> bool:
    return len(buf) >= 4 and be_u16(buf, 0) == WB_DISKMAGIC

def icon_type_name(t: int) -> str:
    return {
        1: "disk",
        2: "drawer",
        3: "tool",
        4: "project",
        6: "device",
        7: "kick",
    }.get(t, "?")

def bytes_to_tt_str(raw: bytes) -> str:
    # ToolTypes often include a trailing NUL; strip NULs for display/logic.
    s = raw.rstrip(b"\0")
    return s.decode("latin-1", errors="replace")

def tt_str_to_bytes(s: str, keep_nul: bool) -> bytes:
    b = s.encode("latin-1", errors="strict")
    return b + (b"\0" if keep_nul else b"")

def split_kv(s: str) -> Tuple[str, Optional[str]]:
    if "=" not in s:
        return (s, None)
    k, v = s.split("=", 1)
    return k, v

def key_eq(a: str, b: str, ignore_case: bool) -> bool:
    return a.lower() == b.lower() if ignore_case else a == b

def canon_key(user_key: str) -> str:
    s = user_key.strip()
    m = _tt_paren_re.match(s)
    if m:
        return m.group(1).strip()
    return s

@dataclass
class TTItem:
    raw: str              # normalized display string (no trailing NUL)
    key: str              # canonical key (no parens)
    kind: str             # "kv" | "bool"
    value: Optional[str]  # for kv: string; for bool: "true"/"false"
    negated: bool         # True if (KEY)

def parse_tt_item(line: str) -> TTItem:
    s = line.strip()
    m = _tt_paren_re.match(s)
    if m:
        k = m.group(1).strip()
        return TTItem(raw=s, key=k, kind="bool", value="false", negated=True)
    if "=" in s:
        k, v = s.split("=", 1)
        return TTItem(raw=s, key=k.strip(), kind="kv", value=v, negated=False)
    # boolean true
    return TTItem(raw=s, key=s, kind="bool", value="true", negated=False

    )

@dataclass
class ParsedIcon:
    data: bytearray
    version: int
    revision: int
    icon_type: int
    has_drawerdata: bool
    has_defaulttool: bool
    has_tooltypes: bool
    has_toolwindow: bool
    num_main_icons: int

    drawerdata: Optional[bytes]
    main_icons_blob: bytes
    defaulttool: Optional[bytes]
    tooltypes_raw_entries: List[bytes]
    toolwindow: Optional[bytes]
    drawerdata2: Optional[bytes]
    glowicons: Optional[bytes]

    tooltypes_pos: Optional[int]

def get_main_icon_size(buf: bytes, pos: int, strict: bool) -> int:
    if pos + 20 > len(buf):
        if strict:
            raise ValueError("Main icon header out of range")
        return 0
    width = be_u16(buf, pos + 4)
    height = be_u16(buf, pos + 6)
    depth = be_u16(buf, pos + 8)
    src_rowspan = ((width + 15) // 16) * 2
    src_planespan = src_rowspan * height
    bytesused = 20 + src_planespan * depth
    if strict:
        if depth < 1 or depth > 8:
            raise ValueError(f"Unsupported depth {depth}")
        if bytesused <= 20 or bytesused > 10_000_000:
            raise ValueError("Main icon size unreasonable")
        if pos + bytesused > len(buf):
            raise ValueError("Main icon bitmap out of range")
    return int(bytesused)

def parse_tooltypes_table(buf: bytes, pos: int, strict: bool) -> Tuple[List[bytes], int]:
    pos0 = pos
    num_entries_raw, pos = u32_at(buf, pos, strict=strict)
    if num_entries_raw == 0:
        return [], pos - pos0
    if strict and (num_entries_raw % 4 != 0):
        raise ValueError("ToolTypes header not multiple of 4")
    num_entries = (num_entries_raw // 4) - 1
    if strict:
        if num_entries < 0 or num_entries > MAX_TOOLTYPES:
            raise ValueError(f"ToolTypes count unreasonable: {num_entries}")
    entries: List[bytes] = []
    for _ in range(max(0, num_entries)):
        tlen, pos = u32_at(buf, pos, strict=strict)
        if strict and tlen > MAX_TLEN:
            raise ValueError("ToolType entry too large")
        if pos + tlen > len(buf):
            raise ValueError("ToolType entry out of range")
        entries.append(bytes(buf[pos:pos + tlen]))
        pos += tlen
    return entries, pos - pos0

def build_tooltypes_table(entries: List[bytes]) -> bytes:
    num_entries_raw = 4 * (len(entries) + 1)
    out = bytearray()
    out += struct.pack(">I", num_entries_raw)
    for e in entries:
        out += struct.pack(">I", len(e))
        out += e
    return bytes(out)

def detect_glowicons_tail(buf: bytes, pos: int) -> Optional[bytes]:
    if pos < 0 or pos >= len(buf):
        return None
    rem = len(buf) - pos
    if rem >= 24:
        if buf[pos:pos+4] == b"FORM" and buf[pos+8:pos+12] == b"ICON":
            return bytes(buf[pos:])
    if rem > 0:
        return bytes(buf[pos:])
    return None

def parse_icon_file(path: str, strict: bool) -> ParsedIcon:
    data = bytearray(open(path, "rb").read())
    if not is_diskobject(data):
        raise ValueError("Not an Amiga icon (.info) (WB_DISKMAGIC mismatch)")
    if strict and len(data) < DISKOBJECT_LEN:
        raise ValueError("File too small for DiskObject")

    version = be_u16(data, OFF_VERSION)
    revision = be_u32(data, OFF_ICON_REVISION) & 0xFF
    itype = data[OFF_ICON_TYPE]

    has_defaulttool = (be_u32(data, OFF_DEFAULTTOOL_PRESENCE) != 0)
    has_tooltypes = (be_u32(data, OFF_TOOLTYPES_PRESENCE) != 0)
    has_drawerdata = (be_u32(data, OFF_DRAWERDATA_PRESENCE) != 0)
    has_toolwindow = (be_u32(data, OFF_TOOLWINDOW_PRESENCE) != 0)

    selectrender_ptr = be_u32(data, OFF_SELECTRENDER_PTR)
    num_main_icons = 1 if selectrender_ptr == 0 else 2

    pos = DISKOBJECT_LEN

    drawerdata = None
    if has_drawerdata:
        if strict and pos + DRAWERDATA_LEN > len(data):
            raise ValueError("DrawerData out of range")
        drawerdata = bytes(data[pos:pos + DRAWERDATA_LEN])
        pos += DRAWERDATA_LEN

    main_start = pos
    for _ in range(num_main_icons):
        sz = get_main_icon_size(data, pos, strict=strict)
        pos += sz
    if strict and pos > len(data):
        raise ValueError("Main icons overrun file")
    main_icons_blob = bytes(data[main_start:pos])

    defaulttool = None
    if has_defaulttool:
        if strict and pos + 4 > len(data):
            raise ValueError("DefaultTool header out of range")
        dlen = be_u32(data, pos)
        pos += 4
        if strict and pos + dlen > len(data):
            raise ValueError("DefaultTool data out of range")
        defaulttool = bytes(data[pos-4:pos + dlen])  # include length field
        pos += dlen

    tooltypes_pos = None
    tooltypes_entries: List[bytes] = []
    if has_tooltypes:
        tooltypes_pos = pos
        entries, used = parse_tooltypes_table(data, pos, strict=strict)
        tooltypes_entries = entries
        pos += used

    toolwindow = None
    if has_toolwindow:
        if strict and pos + 4 > len(data):
            raise ValueError("ToolWindow header out of range")
        wlen = be_u32(data, pos)
        if strict and pos + 4 + wlen > len(data):
            raise ValueError("ToolWindow data out of range")
        toolwindow = bytes(data[pos:pos + 4 + wlen])
        pos += 4 + wlen

    drawerdata2 = None
    if has_drawerdata and revision == 1:
        if strict and pos + DRAWERDATA2_LEN > len(data):
            raise ValueError("DrawerData2 out of range")
        drawerdata2 = bytes(data[pos:pos + DRAWERDATA2_LEN])
        pos += DRAWERDATA2_LEN

    glowicons = detect_glowicons_tail(data, pos)

    return ParsedIcon(
        data=data,
        version=version,
        revision=revision,
        icon_type=itype,
        has_drawerdata=has_drawerdata,
        has_defaulttool=has_defaulttool,
        has_tooltypes=has_tooltypes,
        has_toolwindow=has_toolwindow,
        num_main_icons=num_main_icons,
        drawerdata=drawerdata,
        main_icons_blob=main_icons_blob,
        defaulttool=defaulttool,
        tooltypes_raw_entries=tooltypes_entries,
        toolwindow=toolwindow,
        drawerdata2=drawerdata2,
        glowicons=glowicons,
        tooltypes_pos=tooltypes_pos,
    )

def set_current_xy(icon: ParsedIcon, x: int, y: int) -> None:
    if len(icon.data) >= OFF_CURRENTY + 4:
        put_be_i32(icon.data, OFF_CURRENTX, x)
        put_be_i32(icon.data, OFF_CURRENTY, y)
    else:
        raise ValueError("Icon too small to have CurrentX/CurrentY")

def set_drawer_winsize(icon: ParsedIcon, w: int, h: int) -> bool:
    if not icon.has_drawerdata or icon.drawerdata is None:
        return False
    dd = bytearray(icon.drawerdata)
    put_be_u16(dd, DD_NEWWIN_WIDTH_OFF, w)
    put_be_u16(dd, DD_NEWWIN_HEIGHT_OFF, h)
    icon.drawerdata = bytes(dd)
    return True

def apply_tooltypes_ops(
    entries_raw: List[bytes],
    op_set_kv: Optional[Tuple[str, str]],
    op_set_flag: Optional[str],
    op_unset_flag: Optional[str],
    op_del: Optional[str],
    op_norm: bool,
    ignore_case: bool
) -> List[bytes]:
    entries = [bytes_to_tt_str(e) for e in entries_raw]

    def matches_key(line: str, want_key: str) -> bool:
        item = parse_tt_item(line)
        return key_eq(item.key, want_key, ignore_case)

    # delete (removes KEY, (KEY), and KEY=VAL)
    if op_del:
        want = canon_key(op_del)
        entries = [s for s in entries if not matches_key(s, want)]

    # set KV (removes all prior forms, then writes KEY=VAL)
    if op_set_kv:
        k, v = op_set_kv
        want = canon_key(k)
        entries = [s for s in entries if not matches_key(s, want)]
        entries.append(f"{want}={v}")

    # set flag true (removes all prior forms, then writes KEY)
    if op_set_flag:
        want = canon_key(op_set_flag)
        entries = [s for s in entries if not matches_key(s, want)]
        entries.append(f"{want}")

    # unset flag (removes all prior forms, then writes (KEY))
    if op_unset_flag:
        want = canon_key(op_unset_flag)
        entries = [s for s in entries if not matches_key(s, want)]
        entries.append(f"({want})")

    if op_norm:
        # last-wins across all forms (kv, KEY, (KEY))
        last_by_key: dict[str, str] = {}
        other: List[str] = []

        def canon(k: str) -> str:
            return k.lower() if ignore_case else k

        for s in entries:
            s2 = s.strip()
            if s2 == "":
                continue
            item = parse_tt_item(s2)
            if item.key == "":
                continue
            last_by_key[canon(item.key)] = s2

        # Preserve stable order by original appearance of first-seen key
        seen = set()
        for s in entries:
            item = parse_tt_item(s)
            ck = canon(item.key)
            if ck in seen:
                continue
            if ck in last_by_key:
                other.append(last_by_key[ck])
                seen.add(ck)

        entries = other

    # Re-encode. Preserve original trailing NUL per entry position if possible;
    # otherwise default to keeping NUL (it’s common and harmless).
    new_raw: List[bytes] = []
    for i, s in enumerate(entries):
        keep_nul = True
        if i < len(entries_raw):
            keep_nul = entries_raw[i].endswith(b"\0")
        new_raw.append(tt_str_to_bytes(s, keep_nul=keep_nul))
    return new_raw

def rebuild_file(icon: ParsedIcon, new_tooltypes: Optional[List[bytes]], compact: bool) -> bytes:
    out = bytearray()

    # DiskObject header (78 bytes) with any in-place edits already applied
    out += icon.data[:DISKOBJECT_LEN]

    # DrawerData
    if icon.has_drawerdata:
        if icon.drawerdata is None:
            raise ValueError("DrawerData flagged but missing")
        out += icon.drawerdata

    # Main icons blob
    out += icon.main_icons_blob

    # DefaultTool segment
    if icon.has_defaulttool:
        if icon.defaulttool is None:
            raise ValueError("DefaultTool flagged but missing")
        out += icon.defaulttool

    # ToolTypes
    if icon.has_tooltypes:
        if new_tooltypes is None and not compact:
            if icon.tooltypes_pos is None:
                raise ValueError("ToolTypes flagged but position unknown")
            entries, used = parse_tooltypes_table(icon.data, icon.tooltypes_pos, strict=False)
            out += icon.data[icon.tooltypes_pos:icon.tooltypes_pos + used]
        else:
            tt_entries = new_tooltypes if new_tooltypes is not None else icon.tooltypes_raw_entries
            out += build_tooltypes_table(tt_entries)

    # ToolWindow
    if icon.has_toolwindow:
        if icon.toolwindow is None:
            raise ValueError("ToolWindow flagged but missing")
        out += icon.toolwindow

    # DrawerData2
    if icon.has_drawerdata and icon.revision == 1:
        if icon.drawerdata2 is None:
            raise ValueError("DrawerData2 expected but missing")
        out += icon.drawerdata2

    # GlowIcons / extra tail
    if icon.glowicons:
        out += icon.glowicons

    return bytes(out)

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Batch edit Amiga Workbench .info ToolTypes / icon position / drawer window size"
    )
    ap.add_argument("paths", nargs="+", help="Paths to .info files (or base names without .info)")

    ap.add_argument("--list", action="store_true", help="List parsed metadata + tooltypes")
    ap.add_argument("--get", metavar="KEY", help="Get ToolType KEY. For booleans, prints KEY=true/false. Accepts KEY or (KEY).")
    ap.add_argument("--set", metavar="KEY=VAL", help="Set/replace ToolType KEY=VAL")
    ap.add_argument("--set-flag", metavar="KEY", help="Set boolean ToolType KEY (writes KEY)")
    ap.add_argument("--unset", metavar="KEY", help="Unset/disable boolean ToolType KEY (writes (KEY))")
    ap.add_argument("--delete", metavar="KEY", help="Delete ToolType KEY (removes KEY, (KEY), and KEY=VAL)")
    ap.add_argument("--normalize", action="store_true", help="Normalize tooltypes (last-wins per key, remove empties)")
    ap.add_argument("--ignore-case", action="store_true", help="Match keys case-insensitively")

    ap.add_argument("--pos", metavar="X,Y", help="Set DiskObject CurrentX,CurrentY (icon placement)")
    ap.add_argument("--winsize", metavar="W,H", help="Disk/Drawer: set DrawerData NewWindow Width,Height")
    ap.add_argument("--compact", action="store_true", help="Rebuild file to compact segments (esp. ToolTypes)")
    ap.add_argument("--strict", action="store_true", help="Fail fast on suspicious lengths/bounds")

    ap.add_argument("--dry-run", action="store_true", help="Don’t write, just show what would change")
    ap.add_argument("--backup", action="store_true", help="Write .bak backup once before modifying")
    args = ap.parse_args()

    if not (args.list or args.get or args.set or args.set_flag or args.unset or args.delete or args.normalize or args.pos or args.winsize or args.compact):
        ap.error("No operation specified")

    op_set_kv = None
    if args.set:
        if "=" not in args.set:
            ap.error("--set requires KEY=VAL")
        k, v = args.set.split("=", 1)
        op_set_kv = (k, v)

    pos_xy = None
    if args.pos:
        if "," not in args.pos:
            ap.error("--pos requires X,Y")
        xs, ys = args.pos.split(",", 1)
        pos_xy = (int(xs, 0), int(ys, 0))

    win_wh = None
    if args.winsize:
        if "," not in args.winsize:
            ap.error("--winsize requires W,H")
        ws, hs = args.winsize.split(",", 1)
        win_wh = (int(ws, 0), int(hs, 0))

    rc = 0

    for p in args.paths:
        info_path = p if p.lower().endswith(".info") else p + ".info"
        try:
            icon = parse_icon_file(info_path, strict=args.strict)
        except Exception as e:
            print(f"{info_path}: ERROR: {e}", file=sys.stderr)
            rc = 2
            continue

        if args.list:
            print(f"{info_path}:")
            print(f"  type: {icon.icon_type} ({icon_type_name(icon.icon_type)})")
            print(f"  version: {icon.version}, revision: {icon.revision}, main_icons: {icon.num_main_icons}")
            try:
                cx = be_i32(icon.data, OFF_CURRENTX)
                cy = be_i32(icon.data, OFF_CURRENTY)
                print(f"  currentxy: {cx},{cy}")
            except Exception:
                print("  currentxy: (unavailable)")
            w = be_u16(icon.data, OFF_MAIN_CANVAS_W)
            h = be_u16(icon.data, OFF_MAIN_CANVAS_H)
            print(f"  canvas: {w}x{h}")
            print(f"  has_drawerdata: {icon.has_drawerdata}  has_defaulttool: {icon.has_defaulttool}  has_tooltypes: {icon.has_tooltypes}  has_toolwindow: {icon.has_toolwindow}")
            if icon.has_tooltypes and icon.tooltypes_raw_entries:
                for e in icon.tooltypes_raw_entries:
                    print(f"  {bytes_to_tt_str(e)}")
            else:
                print("  (no tooltypes)")
            print()

        if args.get:
            want = canon_key(args.get)
            last: Optional[TTItem] = None
            for e in icon.tooltypes_raw_entries:
                item = parse_tt_item(bytes_to_tt_str(e))
                if key_eq(item.key, want, args.ignore_case):
                    last = item
            if last is None:
                print(f"{info_path}: {args.get} not set")
            else:
                if last.kind == "kv":
                    print(f"{info_path}: {want}={last.value}")
                else:
                    state = "false" if last.negated else "true"
                    print(f"{info_path}: {want}={state}")

        changed = False

        if pos_xy is not None:
            set_current_xy(icon, pos_xy[0], pos_xy[1])
            changed = True

        if win_wh is not None:
            ok = set_drawer_winsize(icon, win_wh[0], win_wh[1])
            if not ok:
                print(f"{info_path}: NOTE: --winsize ignored (no DrawerData in this icon)")
            else:
                changed = True

        new_tooltypes = None
        if icon.has_tooltypes and (op_set_kv or args.set_flag or args.unset or args.delete or args.normalize):
            new_tooltypes = apply_tooltypes_ops(
                icon.tooltypes_raw_entries,
                op_set_kv=op_set_kv,
                op_set_flag=args.set_flag,
                op_unset_flag=args.unset,
                op_del=args.delete,
                op_norm=args.normalize,
                ignore_case=args.ignore_case,
            )
            if new_tooltypes != icon.tooltypes_raw_entries:
                changed = True

        if changed or args.compact:
            new_bytes = rebuild_file(icon, new_tooltypes=new_tooltypes, compact=args.compact)

            old_bytes = open(info_path, "rb").read()
            if new_bytes == old_bytes:
                # nothing to do
                continue

            if args.dry_run:
                print(f"{info_path}: would update")
                continue

            if args.backup:
                bak = info_path + ".bak"
                if not os.path.exists(bak):
                    shutil.copy2(info_path, bak)

            with open(info_path, "wb") as f:
                f.write(new_bytes)
            print(f"{info_path}: updated")

    return rc

if __name__ == "__main__":
    raise SystemExit(main())

