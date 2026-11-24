#!/usr/bin/env bash
#
# blob_encode.sh - pack the copyrighted test fixtures into an encrypted blob.
#
# Reads the manifest test/blob_files.txt (one path per line, relative to the
# test/ directory) and writes test/blob.tar.zstd.enc holding exactly those
# files.  The archive is zstd compressed and AES-256 encrypted, so it is safe
# to commit: it can only be opened with the passphrase that is kept in the CI
# secret BLOB_PASSPHRASE and never stored in the repository.
#
# Regenerate it after adding/removing files in the manifest or replacing a
# fixture on disk:
#
#     BLOB_PASSPHRASE=... test/blob_encode.sh
#
# If BLOB_PASSPHRASE is not set the passphrase is read from the terminal.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIST="$HERE/blob_files.txt"
OUT="$HERE/blob.tar.zstd.enc"

[[ -f "$LIST" ]] || { echo "error: manifest not found: $LIST" >&2; exit 1; }

# --- passphrase: BLOB_PASSPHRASE wins, otherwise prompt --------------------
if [[ -z "${BLOB_PASSPHRASE:-}" ]]; then
    read -r -s -p "passphrase: " BLOB_PASSPHRASE
    echo >&2
fi
[[ -n "$BLOB_PASSPHRASE" ]] || { echo "error: empty passphrase" >&2; exit 1; }
export BLOB_PASSPHRASE

# --- read the manifest, dropping comments and blank lines ------------------
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
grep -v -E '^[[:space:]]*(#|$)' "$LIST" > "$TMP" || true
[[ -s "$TMP" ]] || { echo "error: no files listed in $LIST" >&2; exit 1; }

# --- sanity checks: every entry exists and is not tracked by git -----------
rc=0
while IFS= read -r path; do
    if [[ ! -e "$HERE/$path" ]]; then
        echo "error: listed file does not exist: test/$path" >&2
        rc=1
    elif [[ -n "$(git -C "$HERE" ls-files -- "$path")" ]]; then
        echo "error: listed file is tracked by git: test/$path" >&2
        rc=1
    fi
done < "$TMP"
[[ $rc -eq 0 ]] || exit 1

# --- pack: tar (paths relative to test/) | zstd | openssl ------------------
tar -C "$HERE" -cf - -T "$TMP" \
    | zstd -q -19 \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
        -out "$OUT.tmp" -pass env:BLOB_PASSPHRASE
mv "$OUT.tmp" "$OUT"

echo "wrote $(wc -c < "$OUT" | tr -d ' ') bytes: test/blob.tar.zstd.enc"
echo "included $(wc -l < "$TMP" | tr -d ' ') entries from test/blob_files.txt"
