#!/usr/bin/env python3
"""extract-cli.py - populate test/cli from AmigaOS 3.2.3 sources.

The extracted files are copyrighted AmigaOS binaries and must never be
committed.  The script scans the given sources for every known CLI command,
verifies each one's SHA-1, decompresses ``.Z`` (LZW) members on the fly and
warns about any file that is missing.

Sources may be directories (scanned recursively), Amiga disk images
(``.adf``/``.adz``/``.hdf``/...) or any mix of both.  The simplest way is to
point it at the folder holding the original AmigaOS 3.2 / 3.2.3 disk images.

usage:
    python3 test/cli/extract-cli.py <source> [<source> ...] [-o OUT]
"""

import argparse
import os
import sys

# repo root is two levels above this script (test/cli/<script>); the shared
# helpers live one level up in test/.
HERE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.dirname(HERE)
REPO = os.path.dirname(TEST)
sys.path.insert(1, REPO)
sys.path.insert(1, TEST)

import extract_util  # noqa: E402  (needs the path set up above)

# ---------------------------------------------------------------------------
# the known CLI commands: name, version ($VER: string), SHA-1 and where the
# file lives in AmigaOS 3.2.3
#
# The final 3.2.3 state is the base Workbench 3.2 release overlaid by the
# 3.2.3 update.  The update replaces AssignWedge, ConClip, DefIcons and IPrefs
# and adds AmigaModel, CopyTooltypes, Group, GuessBootDev, MD5Sum, Owner,
# ROMReserveLow and WBInfo; several of those are shipped ``.Z`` compressed, so
# the expected hashes below describe the decompressed final 3.2.3 files.
# ---------------------------------------------------------------------------
CLI_FILES = [
    (
        "AddBuffers",
        "addbuffers 47.1 (28.11.2019)",
        "b8bae93dc109c0bc18f87b372361cf44eb8046c2",
        "Workbench 3.2, C/",
    ),
    (
        "AddDataTypes",
        "adddatatypes 47.2 (20.2.2020)",
        "2f2c1c7f5bd6c9da41f383f94a4c0841ce63edb9",
        "Workbench 3.2, C/",
    ),
    (
        "AmigaModel",
        "amigamodel 47.1 (17.8.2020)",
        "d9a0aea9361f69e5a9bcb689314457a5a79fd6e9",
        "3.2.3 update, C/",
    ),
    (
        "Assign",
        "Assign 47.5 (30.1.2021)",
        "7160378f7ab1a8d01dd023dc20318a0b1d11ae71",
        "Workbench 3.2, C/",
    ),
    (
        "AssignWedge",
        "assignwedge 47.15 (26.10.2021)",
        "1a9614b8bbe292245e9f132aaaf9915591678c61",
        "3.2.3 update, C/AssignWedge.Z",
    ),
    (
        "Avail",
        "avail 47.1 (28.7.2019)",
        "e2947b8456070341dde817298ed917d79dc22552",
        "Workbench 3.2, C/",
    ),
    (
        "BindDrivers",
        "binddrivers 45.1 (12.4.2019)",
        "738cd1481da486fe9863a21d39e52276e5f03c97",
        "Workbench 3.2, C/",
    ),
    (
        "Break",
        "break 47.1 (28.11.2019)",
        "04c35975cbf7a0790a90bd7d7927c2cdbdb8d233",
        "Workbench 3.2, C/",
    ),
    (
        "ChangeTaskPri",
        "changetaskpri 47.1 (28.11.2019)",
        "cfde61b5d9a94d6b77238c8ea9498a8a2826239b",
        "Workbench 3.2, C/",
    ),
    (
        "ConClip",
        "conclip 47.6 (16.10.2021)",
        "ff9950eb8f7a7897faaa9f808152522ad979f077",
        "3.2.3 update, C/ConClip.Z",
    ),
    (
        "Copy",
        "Copy 47.7 (30.1.2021)",
        "8d17b03b0cb92608e31c3da203d1afdf5d6c0a61",
        "Workbench 3.2, C/",
    ),
    (
        "CopyTooltypes",
        "copytooltypes 47.1 (20.10.2019)",
        "09dbf313267f2d4983c0abf381069e289508d4c6",
        "3.2.3 update, C/",
    ),
    (
        "CPU",
        "cpu 47.1 (19.10.2020)",
        "339d3c13eff9d98ee373668c863c56fb660476fb",
        "Workbench 3.2, C/",
    ),
    (
        "Date",
        "date 47.2 (14.12.2019)",
        "28ae411c9fcada25598839710b3b566a6a726f0f",
        "Workbench 3.2, C/",
    ),
    (
        "DefIcons",
        "deficons 47.9 (28.10.2021)",
        "1c3f8c72bf7335cd6094bdbfdcf067ac2a2b3dd7",
        "3.2.3 update, C/DefIcons.Z",
    ),
    (
        "Delete",
        "delete 47.2 (7.1.2020)",
        "030191ef5fdfb185fca182bd286de30b39ae89bd",
        "Workbench 3.2, C/",
    ),
    (
        "Dir",
        "dir 47.2 (19.12.2019)",
        "9c4044d3e06697fdd68cd1add615c6e3ce8ff8fd",
        "Workbench 3.2, C/",
    ),
    (
        "DiskChange",
        "diskchange 45.1 (13.4.2019)",
        "650836abbddba51990ccb58cf847473c3ff85c99",
        "Workbench 3.2, C/",
    ),
    (
        "Ed",
        "ed 47.2 (24.5.2020)",
        "d19392f9e669eaee3aa41edbebc5d2cd46ac10f9",
        "Workbench 3.2, C/",
    ),
    (
        "Eval",
        "Eval 47.2 (30.1.2021)",
        "648fe7e4262b05716af6ff32ab4cb5aef38c93b7",
        "Workbench 3.2, C/",
    ),
    (
        "Filenote",
        "filenote 47.1 (28.11.2019)",
        "43c8a7f8840539b44050a933280d2b56845a7812",
        "Workbench 3.2, C/",
    ),
    (
        "Group",
        "group 47.2 (10.12.2022)",
        "6451090722636d3d9e69a975b8c8d1455cc7b0b0",
        "3.2.3 update, C/Group.Z",
    ),
    (
        "GuessBootDev",
        "guessbootdev 45.2 (4.8.2019)",
        "39d5acd6af505423330ed25b20e1862277e33849",
        "3.2.3 update, C/",
    ),
    (
        "IconX",
        "iconx 45.1 (18.11.2017)",
        "4f49b2fa5531ae1a1851c21ee570b324c0c48437",
        "Workbench 3.2, C/",
    ),
    (
        "Info",
        "Info 45.7 (27.5.2018)",
        "2c9c98a4b7a576eb50c4b2b8f32ea6eeaa9fcabb",
        "Workbench 3.2, C/",
    ),
    (
        "Install",
        "install 47.4 (19.7.2020)",
        "5af5975ef92ec650bf6648cce9697a9a51d5fe42",
        "Workbench 3.2, C/",
    ),
    (
        "IPrefs",
        "IPrefs 47.32 (7.11.2024)",
        "0c7c6cae81ef5c3d79cb72efe41add712970f0f4",
        "3.2.3 update, C/IPrefs.Z",
    ),
    (
        "Join",
        "join 47.2 (7.1.2021)",
        "3b6b1fb2ec0dace4754d09a0079309248634323b",
        "Workbench 3.2, C/",
    ),
    (
        "List",
        "list 47.19 (28.7.2020)",
        "bae8df6ae7ea1ed00965f10ba01289b061179452",
        "Workbench 3.2, C/",
    ),
    (
        "LoadResource",
        "loadresource 47.2 (24.5.2020)",
        "5ed2503fe7e33b3c5b46ba4e7e2a952794248223",
        "Workbench 3.2, C/",
    ),
    (
        "LoadWB",
        "loadwb 47.1 (1.2.2020)",
        "3d02dd9e10a3bded701ba58f31e1a7423b1b78a0",
        "Workbench 3.2, C/",
    ),
    (
        "Lock",
        "lock 47.1 (28.11.2019)",
        "4194a3b434eded744a9a441c88379e7d284d0685",
        "Workbench 3.2, C/",
    ),
    (
        "MakeDir",
        "makedir 47.1 (28.11.2019)",
        "95ac383e94c1d20ea9a1df1cf0f2ded219d8d12d",
        "Workbench 3.2, C/",
    ),
    (
        "MakeLink",
        "makelink 47.1 (28.11.2019)",
        "f1d8d6e57c3942cc61a6603038084abc1d3652e1",
        "Workbench 3.2, C/",
    ),
    (
        "MD5Sum",
        "MD5Sum 47.21 (16.3.2024)",
        "7a34420776012dbbc7bd655cd032def6bdab9b82",
        "3.2.3 update, C/MD5Sum.Z",
    ),
    (
        "Mount",
        "mount 47.2 (24.5.2020)",
        "2d0a52eea75b0014ec88303947ebebf658e50a2d",
        "Workbench 3.2, C/",
    ),
    (
        "Owner",
        "owner 47.2 (10.12.2022)",
        "54bafce8ee40e8bafa6dd3f11215cd1063745ecf",
        "3.2.3 update, C/Owner.Z",
    ),
    (
        "Protect",
        "protect 47.5 (11.4.2020)",
        "9b26a63513e5b8c9ec1c2408e8d079c9b7b1040f",
        "Workbench 3.2, C/",
    ),
    (
        "Relabel",
        "relabel 47.2 (7.1.2020)",
        "b1ddad5f18df7c6abb81e77d17ee6159cccf4bf6",
        "Workbench 3.2, C/",
    ),
    (
        "RemRAD",
        "remrad 47.1 (28.11.2019)",
        "0485fdf28e02a901d45aabc5e1d3ac55623fd011",
        "Workbench 3.2, C/",
    ),
    (
        "Rename",
        "Rename 47.3 (30.1.2021)",
        "294c26dfaea572a873f0f830b46b121f9d94142f",
        "Workbench 3.2, C/",
    ),
    (
        "RequestChoice",
        "requestchoice 45.3 (6.10.2018)",
        "bf4c7f185f4c28bf84ee7872ac32b7de7423e3a5",
        "Workbench 3.2, C/",
    ),
    (
        "RequestFile",
        "requestfile 45.3 (7.9.2018)",
        "7fe5264a195246badc1f92ea7150ad86744c6ba9",
        "Workbench 3.2, C/",
    ),
    (
        "ROMReserveLow",
        "RomReserveLow 47.1 (29.10.2024)",
        "3066d15ae861c8eb60b523a6c043330dc59650e6",
        "3.2.3 update, C/ROMReserveLow.Z",
    ),
    (
        "Search",
        "search 47.1 (28.11.2019)",
        "72a6bbd06f4acca369ad01da2daadc5b940d744f",
        "Workbench 3.2, C/",
    ),
    (
        "SetClock",
        "setclock 47.1 (28.11.2019)",
        "abaff8bfc1a1d798aa3fc70499beb2ae075dd48a",
        "Workbench 3.2, C/",
    ),
    (
        "SetDate",
        "setdate 47.1 (19.9.2019)",
        "776441fae311743f9692e19c0c17b9a1126adcce",
        "Workbench 3.2, C/",
    ),
    (
        "SetFont",
        "setfont 45.1 (20.4.2019)",
        "895c3945eeee1d259c55775d4527c8df299be70d",
        "Workbench 3.2, C/",
    ),
    (
        "SetKeyboard",
        "setkeyboard 47.1 (28.11.2019)",
        "31884318765220bb3c3b79f84f946ade58b0ee70",
        "Workbench 3.2, C/",
    ),
    (
        "SetPatch",
        "setpatch 47.4 (4.8.2020)",
        "93dfc11808dcec0aaa0a8fc164c7cbb6f3cd7466",
        "Workbench 3.2, C/",
    ),
    (
        "Sort",
        "sort 46.4 (22.4.2018)",
        "a7692005073b8b59290dbad6b2905c9a379d68e3",
        "Workbench 3.2, C/",
    ),
    (
        "Status",
        "status 47.1 (28.11.2019)",
        "065742381ef0308f2d574835d74aa217dbe30735",
        "Workbench 3.2, C/",
    ),
    (
        "Type",
        "type 47.3 (7.1.2021)",
        "39ccf36f48f13772f0744bc98c42ee01e7a13984",
        "Workbench 3.2, C/",
    ),
    (
        "Version",
        "version 47.3 (31.1.2021)",
        "359f76f5843dee097c15f4bffce678a7c70e8d45",
        "Workbench 3.2, C/",
    ),
    (
        "Wait",
        "wait 47.1 (28.11.2019)",
        "0c16d8160a37575288310a4bbb86b9611666a5cf",
        "Workbench 3.2, C/",
    ),
    (
        "WBInfo",
        "WBInfo 47.1 (21.9.2021)",
        "5b21931ef82f92abad4bb154b84a979700c3cc1b",
        "3.2.3 update, C/WBInfo.Z",
    ),
    (
        "WBLoad",
        "wbload 47.1 (28.11.2019)",
        "12aceb32c2125442f6a5f6322c17fdbf6c8798fb",
        "Workbench 3.2, C/",
    ),
    (
        "Which",
        "which 45.2 (30.12.2019)",
        "408453c504fdcad87cf9b827ab672effe50d21b6",
        "Workbench 3.2, C/",
    ),
]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "sources",
        nargs="+",
        help="folders and/or Amiga disk images (scanned recursively)",
    )
    ap.add_argument(
        "-o",
        "--output",
        default=HERE,
        help="output folder (default: this script's folder)",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="show extra detail")
    args = ap.parse_args()

    for s in args.sources:
        if not os.path.exists(s):
            ap.error("not a folder or file: %s" % s)
    out_dir = os.path.abspath(args.output)
    cmd_dir = os.path.join(out_dir, "C")
    os.makedirs(cmd_dir, exist_ok=True)

    names = {name.lower() for name, _, _, _ in CLI_FILES}
    want = {sha: (name, ver, where) for name, ver, sha, where in CLI_FILES}

    found, unknown = extract_util.scan_sources(args.sources, names, want, args.verbose)

    print("\n%-16s %-26s %s" % ("file", "version", "status"))
    print("-" * 78)
    missing = []
    ok = 0
    for name, ver, sha, where in CLI_FILES:
        out_path = os.path.join(cmd_dir, name)
        if os.path.isfile(out_path) and extract_util.file_sha1(out_path) == sha:
            print("%-16s %-26s present" % (name, ver))
            ok += 1
        elif sha in found:
            blob, source, logical = found[sha]
            with open(out_path, "wb") as f:
                f.write(blob)
            print("%-16s %-26s extracted <- %s" % (name, ver, source))
            ok += 1
        else:
            print("%-16s %-26s MISSING" % (name, ver))
            missing.append((name, ver, where))

    if missing:
        print("\nWARNING: %d file(s) missing:" % len(missing))
        for name, ver, where in missing:
            print("  - C/%s (%s): expected %s" % (name, ver, where))
    if unknown:
        print(
            "\nnote: %d matching-named file(s) did not match a known SHA-1 "
            "(run with -v to list)" % len(unknown)
        )

    print("\n%d/%d CLI commands available in %s" % (ok, len(CLI_FILES), cmd_dir))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
