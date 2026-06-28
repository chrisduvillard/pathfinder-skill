#!/usr/bin/env bash
#
# Manifest + version-consistency checks, runnable locally AND in CI.
#
# These checks used to live only inline in .github/workflows/manifests.yml, so a
# contributor who bumped VERSION.md but forgot to mirror a plugin.json (the most
# common historical mistake — see the VERSION.md changelog) could run every command
# CONTRIBUTING listed, see green locally, and only learn of the break from CI (DX-2).
# Extracting them here lets CONTRIBUTING and manifests.yml run the exact same logic.
#
# Asserts: (1) all four manifests are valid JSON; (2) VERSION.md has exactly one
# 'Version: X.Y.Z' line and a matching 'Changes in v<version>:' changelog heading;
# (3) both plugin.json versions equal VERSION.md; (4) neither marketplace.json declares
# a version anywhere (plugin.json is the single source Claude Code resolves first);
# (5) the Codex marketplace keeps source.ref pinned to main for rolling release.
#
# Usage: bash scripts/check-manifests.sh [ROOT]   (ROOT defaults to ".")
# Exit 0 when all checks pass; non-zero otherwise.

set -uo pipefail

root="${1:-.}"
fail=0

jq_bin="${JQ:-}"
if [ -z "$jq_bin" ]; then
  if command -v jq >/dev/null 2>&1; then
    jq_bin="jq"
  elif command -v jq.exe >/dev/null 2>&1; then
    jq_bin="jq.exe"
  fi
fi
if [ -z "$jq_bin" ]; then
  echo "::error::jq is required to run scripts/check-manifests.sh; install jq or ensure it is on PATH for this Bash environment"
  exit 1
fi

# (1) JSON validity.
for f in "$root"/.claude-plugin/plugin.json \
         "$root"/.codex-plugin/plugin.json \
         "$root"/.claude-plugin/marketplace.json \
         "$root"/.agents/plugins/marketplace.json; do
  if "$jq_bin" empty "$f" 2>/dev/null; then
    echo "ok: $f is valid JSON"
  else
    echo "::error file=$f::invalid JSON (fix before merge)"
    fail=1
  fi
done

version_re='^Version:[[:space:]]+[0-9]+\.[0-9]+\.[0-9]+[[:space:]]*$'

# (2) VERSION.md hygiene: exactly one full-line 'Version:' line so the parse
#     below cannot silently pick the wrong version, plus a changelog heading for it.
vlines=$(grep -cE "$version_re" "$root/VERSION.md" || true)
if [ "$vlines" -ne 1 ]; then
  echo "::error file=VERSION.md::expected exactly one full-line 'Version: X.Y.Z' line, found $vlines"
  exit 1
fi
# Full-line, >=1-space regex; keep this parser in sync with release.yml.
v=$(awk '/^Version:[[:space:]]+[0-9]+\.[0-9]+\.[0-9]+[[:space:]]*$/ { print $2; exit }' "$root/VERSION.md" | tr -d '\r')
if [ -z "$v" ]; then
  echo "::error file=VERSION.md::could not parse a full-line 'Version: X.Y.Z' line"
  exit 1
fi
echo "VERSION.md declares $v"
if ! grep -qF "Changes in v$v:" "$root/VERSION.md"; then
  echo "::error file=VERSION.md::no 'Changes in v$v:' changelog heading for the declared version"
  exit 1
fi
echo "ok: changelog heading present for v$v"

# (3) Both plugin.json versions must equal VERSION.md.
for f in "$root"/.claude-plugin/plugin.json "$root"/.codex-plugin/plugin.json; do
  pv=$("$jq_bin" -r '.version' "$f" | tr -d '\r')
  if [ "$pv" = "$v" ]; then
    echo "ok: $f = $pv"
  else
    echo "::error file=$f::version \"$pv\" != VERSION.md \"$v\""
    fail=1
  fi
done

# (4) Neither marketplace.json may declare a version — including one nested under
#     .plugins[].source (TR-5). plugin.json is the single source Claude Code resolves
#     first; a duplicate elsewhere could silently mask it.
for f in "$root"/.claude-plugin/marketplace.json "$root"/.agents/plugins/marketplace.json; do
  if "$jq_bin" -e '(.version != null) or (any(.plugins[]?; .version != null)) or (any(.plugins[]?.source?; (.version? != null)))' "$f" >/dev/null; then
    echo "::error file=$f::marketplace entry declares a version; plugin.json is the single version source — remove it"
    fail=1
  else
    echo "ok: $f sources its version from plugin.json"
  fi
done

# (5) The Codex marketplace deliberately tracks main as a rolling release. Guard
#     the ref so a tag pin cannot silently diverge from the documented distribution
#     model while all version checks stay green.
codex_market="$root/.agents/plugins/marketplace.json"
codex_refs=$("$jq_bin" -r '[.plugins[]? | select(.name == "pathfinder") | .source.ref?] | @tsv' "$codex_market" | tr -d '\r')
if [ "$codex_refs" = "main" ]; then
  echo "ok: $codex_market pathfinder source.ref = main"
else
  echo "::error file=$codex_market::pathfinder marketplace source.ref must be \"main\" for rolling release, got \"${codex_refs:-<missing>}\""
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "manifests: all checks pass at $v"
fi
exit "$fail"
