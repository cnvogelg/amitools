#!/bin/sh
#
# Fetch the real AmigaDOS file system handler fixtures used by the native
# handler end-to-end tests (test/unit/handler_native_e2e.py).
#
# The handlers are third-party binaries. This script downloads them from their
# upstream sources, verifies the extracted handler against a pinned sha256 and
# installs it next to this script. Re-running is safe: a file that already
# matches is left untouched.
#
# The two Aminet archives need an LHA unpacker: either the `lha` command (found
# on $PATH, or set $LHA to its path) or Python's `lhafile` module. Install one
# of them first, e.g. `pip install lhafile`.
#
# Usage: test/handler/download.sh

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$here"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' 0 1 2 15

have() { command -v "$1" >/dev/null 2>&1; }

die() {
    echo "download.sh: $*" >&2
    exit 1
}

sha256() {
    if have shasum; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif have sha256sum; then
        sha256sum "$1" | awk '{print $1}'
    else
        die "no sha256 tool (need shasum or sha256sum)"
    fi
}

# extract_lha ARCHIVE MEMBER DEST
# Unpack a single MEMBER from an LHA ARCHIVE into DEST (an absolute path).
extract_lha() {
    archive=$1
    member=$2
    dest=$3
    exdir="$tmp/ex"
    rm -rf "$exdir"
    mkdir -p "$exdir"
    if [ -n "${LHA:-}" ] && [ -x "$LHA" ]; then
        ( cd "$exdir" && "$LHA" x "$archive" "$member" >/dev/null )
    elif have lha; then
        ( cd "$exdir" && lha x "$archive" "$member" >/dev/null )
    elif python3 -c 'import lhafile' >/dev/null 2>&1; then
        python3 - "$archive" "$member" "$dest" <<'PY'
import shutil
import sys

import lhafile

archive, member, dest = sys.argv[1:4]
with lhafile.Lhafile(archive) as lha:
    names = [n.replace("\\", "/") for n in lha.namelist()]
    if member not in names:
        sys.exit("member not found in archive: %s" % member)
    with lha.open(names[names.index(member)]) as src, open(dest, "wb") as out:
        shutil.copyfileobj(src, out)
PY
        return 0
    else
        die "no LHA unpacker: install the 'lha' command or 'pip install lhafile'"
    fi
    [ -f "$exdir/$member" ] || die "member not found in archive: $member"
    mv "$exdir/$member" "$dest"
}

# verify NAME FILE WANT
verify() {
    name=$1
    file=$2
    want=$3
    got=$(sha256 "$file")
    if [ "$got" != "$want" ]; then
        die "$name: sha256 mismatch (got $got, want $want)"
    fi
    echo "$name: ok ($want)"
}

# install_from_lha NAME URL MEMBER WANT DEST
install_from_lha() {
    name=$1
    url=$2
    member=$3
    want=$4
    dest=$5
    if [ -f "$dest" ] && [ "$(sha256 "$dest")" = "$want" ]; then
        echo "$name: up to date ($dest)"
        return 0
    fi
    echo "$name: downloading $url"
    archive="$tmp/$(basename "$url")"
    curl -fsSL -o "$archive" "$url"
    rm -f "$dest"
    extract_lha "$archive" "$member" "$dest"
    verify "$name" "$dest" "$want"
}

# install_binary NAME URL WANT DEST
install_binary() {
    name=$1
    url=$2
    want=$3
    dest=$4
    if [ -f "$dest" ] && [ "$(sha256 "$dest")" = "$want" ]; then
        echo "$name: up to date ($dest)"
        return 0
    fi
    echo "$name: downloading $url"
    out="$tmp/$(basename "$dest")"
    curl -fsSL -o "$out" "$url"
    verify "$name" "$out" "$want"
    mv "$out" "$dest"
}

install_from_lha \
    "pfs3aio" \
    "https://aminet.net/disk/misc/pfs3aio.lha" \
    "pfs3aio" \
    "185fae785d0f6e15a1936ecb44e4cb18a21b6f701094c57edbd331e5f9a16047" \
    "$here/pfs3aio"

install_from_lha \
    "SmartFilesystem" \
    "https://aminet.net/disk/misc/SFS.lha" \
    "Smartfilesystem/AmigaOS3.x/L/SmartFilesystem" \
    "c7dd174131035a0f5845be1076fb5c55642f6aa2125d4b5d8c029b141dcc8205" \
    "$here/SmartFilesystem"

install_binary \
    "FastFileSystem" \
    "https://github.com/reinauer/FastFileSystem/releases/download/v0.2/FastFileSystem.OS3" \
    "2c66aeaa747a0ba3b4e40281663d5de2b99c1345987d510d5ce4a3d1453d0b7a" \
    "$here/FastFileSystem"

echo "all handler fixtures ready in $here"
