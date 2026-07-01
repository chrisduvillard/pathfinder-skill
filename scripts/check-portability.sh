#!/usr/bin/env bash
#
# Keep local validation and release helpers runnable on common non-GNU shells,
# and keep GitHub Actions supply-chain pins reviewable.
# In particular, grep's Perl-regexp mode is not available in BSD grep, which
# makes otherwise portable repo checks fail on macOS-style environments; and
# GNU grep 3.0 under MSYS/Git-for-Windows aborts when -i and -F are combined
# (e.g. `grep -qiF`), which silently fails the validators on that platform.

set -uo pipefail

root="${1:-.}"
fail=0

scan_perl_grep() {
  awk '
    /^[[:space:]]*($|#)/ { next }
    /^[[:space:]]*([^#[:space:]][^#]*[[:space:]])?grep[[:space:]][^#]*(-[[:alnum:]]*P|--perl-regexp)/ {
      print NR ":" $0
      found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$1"
}

scan_grep_i_f_combo() {
  awk '
    /^[[:space:]]*($|#)/ { next }
    /^[[:space:]]*([^#[:space:]][^#]*[[:space:]])?grep[[:space:]][^#]*(-[[:alnum:]]*i[[:alnum:]]*F|-[[:alnum:]]*F[[:alnum:]]*i)/ {
      print NR ":" $0
      found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$1"
}

for f in "$root"/scripts/*.sh "$root"/.github/workflows/*.yml "$root"/.github/workflows/*.yaml; do
  [ -f "$f" ] || continue

  if scan_perl_grep "$f"; then
    echo "::error file=$f::replace GNU-only grep Perl-regexp usage with portable awk, sed, or grep -E"
    fail=1
  fi

  # GNU grep 3.0 under MSYS/Git-for-Windows aborts (SIGABRT) when -i and -F are
  # combined in one short-flag group (e.g. `grep -qiF`), silently failing the
  # validators on that platform; -i or -F alone is fine. Flag the combo so it
  # cannot regress. Use awk index(tolower()) for a portable case-insensitive literal.
  if scan_grep_i_f_combo "$f"; then
    echo "::error file=$f::replace the GNU grep -i+-F combo (aborts on MSYS GNU grep 3.0) with awk index(tolower()) or grep -F without -i"
    fail=1
  fi
done

# (BE-3/SEC-1) Scan workflow files AND composite-action definitions
# (.github/actions/<name>/action.yml) for uses: pins, so the SHA-pin guarantee covers any local
# composite action too — not only top-level workflows. A non-matching glob stays literal and is
# skipped by the [ -f ] test below, so this is safe when .github/actions/ does not exist.
for f in "$root"/.github/workflows/*.yml "$root"/.github/workflows/*.yaml \
         "$root"/.github/actions/*/action.yml "$root"/.github/actions/*/action.yaml; do
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
  echo "portability: no GNU-only grep usage found and workflow + composite-action actions are SHA-pinned"
fi
exit "$fail"
