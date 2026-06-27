#!/usr/bin/env bash
#
# Keep local validation and release helpers runnable on common non-GNU shells.
# In particular, grep's Perl-regexp mode is not available in BSD grep, which
# makes otherwise portable repo checks fail on macOS-style environments.

set -uo pipefail

root="${1:-.}"
fail=0

for f in "$root"/scripts/*.sh "$root"/.github/workflows/*.yml; do
  [ -f "$f" ] || continue
  case "$f" in
    */scripts/check-portability.sh) continue ;;
  esac

  if grep -nE 'grep[[:space:]][^#]*(-[[:alnum:]]*P|--perl-regexp)' "$f"; then
    echo "::error file=$f::replace GNU-only grep Perl-regexp usage with portable awk, sed, or grep -E"
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "portability: no GNU-only grep usage found in validation/release paths"
fi
exit "$fail"
