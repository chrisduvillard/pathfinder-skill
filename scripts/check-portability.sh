#!/usr/bin/env bash
#
# Keep local validation and release helpers runnable on common non-GNU shells,
# and keep GitHub Actions supply-chain pins reviewable.
# In particular, grep's Perl-regexp mode is not available in BSD grep, which
# makes otherwise portable repo checks fail on macOS-style environments.

set -uo pipefail

root="${1:-.}"
fail=0

for f in "$root"/scripts/*.sh "$root"/.github/workflows/*.yml "$root"/.github/workflows/*.yaml; do
  [ -f "$f" ] || continue
  case "$f" in
    */scripts/check-portability.sh) continue ;;
  esac

  if grep -nE '^[[:space:]]*([^#[:space:]][^#]*[[:space:]])?grep[[:space:]][^#]*(-[[:alnum:]]*P|--perl-regexp)' "$f"; then
    echo "::error file=$f::replace GNU-only grep Perl-regexp usage with portable awk, sed, or grep -E"
    fail=1
  fi
done

for f in "$root"/.github/workflows/*.yml "$root"/.github/workflows/*.yaml; do
  [ -f "$f" ] || continue
  line_no=0
  while IFS= read -r line || [ -n "$line" ]; do
    line_no=$((line_no + 1))
    trimmed="${line#"${line%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    case "$trimmed" in
      ""|\#*) continue ;;
      uses:*|-\ uses:*) ;;
      *) continue ;;
    esac

    action_ref="${trimmed#*uses:}"
    action_ref="${action_ref%%#*}"
    action_ref="${action_ref#"${action_ref%%[![:space:]]*}"}"
    action_ref="${action_ref%"${action_ref##*[![:space:]]}"}"
    action_ref="${action_ref%\"}"
    action_ref="${action_ref#\"}"
    action_ref="${action_ref%\'}"
    action_ref="${action_ref#\'}"

    case "$action_ref" in
      ./*) continue ;;
      *@????????????????????????????????????????)
        sha="${action_ref##*@}"
        case "$sha" in
          *[!0-9a-fA-F]*)
            echo "::error file=$f,line=$line_no::pin external GitHub Action to a full 40-character commit SHA, got \"$action_ref\""
            fail=1
            ;;
        esac
        ;;
      *)
        echo "::error file=$f,line=$line_no::pin external GitHub Action to a full 40-character commit SHA, got \"$action_ref\""
        fail=1
        ;;
    esac
  done < "$f"
done

if [ "$fail" -eq 0 ]; then
  echo "portability: no GNU-only grep usage found and workflow actions are SHA-pinned"
fi
exit "$fail"
