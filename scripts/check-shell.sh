#!/usr/bin/env bash
#
# Run ShellCheck against every Bash source in the repository or packaged tree.

set -uo pipefail

root="${1:-.}"
fail=0
count=0

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "::error::ShellCheck is required (https://www.shellcheck.net/)"
  exit 1
fi

if [ ! -d "$root" ]; then
  echo "::error::ShellCheck root is not a directory: $root"
  exit 1
fi
root="$(cd "$root" && pwd)"

check_file() {
  local file="$1"
  count=$((count + 1))
  if ! shellcheck --severity=warning "$file"; then
    fail=1
  fi
}

if git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  while IFS= read -r -d '' file; do
    check_file "$root/$file"
  done < <(git -C "$root" ls-files -z --cached --others --exclude-standard -- '*.sh' '*.bash')
else
  while IFS= read -r -d '' file; do
    check_file "$file"
  done < <(
    find "$root" \
      \( -type d \( -name .git -o -name .venv -o -name .agent-work -o -name .agent-workspace \) -prune \) -o \
      \( -type f \( -name '*.sh' -o -name '*.bash' \) -print0 \)
  )
fi

if [ "$count" -eq 0 ]; then
  echo "::error::no Bash files found under $root"
  exit 1
fi

if [ "$fail" -eq 0 ]; then
  echo "shellcheck: $count Bash files pass"
fi
exit "$fail"
