#!/usr/bin/env bash
#
# blob_check.sh - verify that no listed fixture can be committed.
#
# Every path in test/blob_files.txt must be ignored by a .gitignore so it can
# never end up in the repository by accident.  Run by CI (the lint job).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIST="$HERE/blob_files.txt"

[[ -f "$LIST" ]] || { echo "error: manifest not found: $LIST" >&2; exit 1; }

count=0
rc=0
while IFS= read -r path; do
    count=$((count + 1))
    if [[ -n "$(git -C "$HERE" ls-files -- "$path")" ]]; then
        echo "error: test/$path is tracked by git" >&2
        rc=1
    elif ! git -C "$HERE" check-ignore -q -- "$path"; then
        echo "error: test/$path is not ignored by .gitignore" >&2
        rc=1
    fi
done < <(grep -v -E '^[[:space:]]*(#|$)' "$LIST" || true)

[[ $rc -eq 0 ]] || exit 1
echo "blob files: $count entries, all ignored and untracked"
