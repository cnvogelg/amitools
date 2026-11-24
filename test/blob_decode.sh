#!/usr/bin/env bash
#
# blob_decode.sh - restore the encrypted fixtures into the test/ tree.
#
# Unpacks test/blob.tar.zstd.enc (created by test/blob_encode.sh) into test/,
# recreating every path listed in test/blob_files.txt.  The passphrase is read
# from BLOB_PASSPHRASE or prompted for.
#
# On CI the passphrase comes from the BLOB_PASSPHRASE secret; locally it is the
# same passphrase used when running blob_encode.sh.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLOB="$HERE/blob.tar.zstd.enc"

[[ -f "$BLOB" ]] || { echo "error: blob not found: $BLOB" >&2; exit 1; }

if [[ -z "${BLOB_PASSPHRASE:-}" ]]; then
    read -r -s -p "passphrase: " BLOB_PASSPHRASE
    echo >&2
fi
[[ -n "$BLOB_PASSPHRASE" ]] || { echo "error: empty passphrase" >&2; exit 1; }
export BLOB_PASSPHRASE

# openssl decrypt | zstd decompress | untar into test/
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$BLOB" \
        -pass env:BLOB_PASSPHRASE \
    | zstd -d -q \
    | tar -C "$HERE" -xf -

echo "restored fixtures into test/"
