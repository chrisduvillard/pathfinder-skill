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
# (3) both plugin.json versions equal VERSION.md; (4) core identity fields match
# between Claude and Codex plugin manifests; (5) Codex default prompts cover the
# supported entry paths; (6) neither marketplace.json declares a version anywhere
# (plugin.json is the single source Claude Code resolves first); (7) the Codex
# marketplace pins source.ref to the immutable release tag for the stable channel;
# (8) the release workflow is manual-only, main-only, and version-confirmed.
#
# Usage: bash scripts/check-manifests.sh [ROOT]   (ROOT defaults to ".")
# Exit 0 when all checks pass; non-zero otherwise.

set -uo pipefail

root="${1:-.}"
fail=0
script_dir="$(cd "$(dirname "$0")" && pwd)"

jq_bin="${JQ:-}"
if [ -z "$jq_bin" ]; then
  if command -v jq >/dev/null 2>&1; then
    jq_bin="jq"
  elif command -v jq.exe >/dev/null 2>&1; then
    jq_bin="jq.exe"
  fi
fi
if [ -z "$jq_bin" ]; then
  echo "::error::jq is required to run scripts/check-manifests.sh; install jq, ensure it is on PATH for this Bash environment, or set JQ=/path/to/jq"
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

# (4) Core identity metadata should not drift between the Claude and Codex plugin
#     manifests. The Codex manifest has extra interface fields by design, so compare
#     only the shared identity surface.
claude_plugin="$root/.claude-plugin/plugin.json"
codex_plugin="$root/.codex-plugin/plugin.json"
identity_fields=(name description homepage repository license author.name author.url)
for field in "${identity_fields[@]}"; do
  cv=$("$jq_bin" -r ".$field // empty" "$claude_plugin" | tr -d '\r')
  xv=$("$jq_bin" -r ".$field // empty" "$codex_plugin" | tr -d '\r')
  if [ "$cv" = "$xv" ] && [ -n "$cv" ]; then
    echo "ok: plugin identity field .$field matches"
  else
    echo "::error file=$codex_plugin::.$field \"$xv\" != $claude_plugin \"$cv\""
    fail=1
  fi
done
ckw=$("$jq_bin" -c '.keywords // []' "$claude_plugin" | tr -d '\r')
xkw=$("$jq_bin" -c '.keywords // []' "$codex_plugin" | tr -d '\r')
if [ "$ckw" = "$xkw" ] && [ "$ckw" != "[]" ]; then
  echo "ok: plugin identity field .keywords matches"
else
  echo "::error file=$codex_plugin::.keywords $xkw != $claude_plugin $ckw"
  fail=1
fi

# (5) Codex default prompts are the install-time entry affordance for supported
#     paths plus the bare chooser/status affordance. Guard them so a manifest edit
#     cannot silently drop a route while every JSON/version check stays green.
required_prompt_fragments=(
  "Show the Pathfinder options"
  "Use the pathfinder skill on this repository"
  "Run Pathfinder autonomously on this repository"
  "/pathfinder charter"
  "Turn this prompt into a runnable /goal"
  "Show Pathfinder status"
)
for fragment in "${required_prompt_fragments[@]}"; do
  # (C4/BE-1) Scope MSYS_NO_PATHCONV=1 to THIS jq call so Git-Bash/MSYS does not path-mangle the
  # leading-slash "/pathfinder charter" fragment into a Windows path (which made this check falsely
  # FAIL locally while Linux CI stayed green). Scoped, not global: $codex_plugin is a relative path,
  # so disabling path conversion here cannot break the file argument (the caveat test-validators.sh
  # documents applies only to ABSOLUTE POSIX path args). Linux ignores the variable.
  if MSYS_NO_PATHCONV=1 "$jq_bin" -e --arg fragment "$fragment" 'any(.interface.defaultPrompt[]?; contains($fragment))' "$codex_plugin" >/dev/null; then
    echo "ok: Codex default prompt covers \"$fragment\""
  else
    echo "::error file=$codex_plugin::missing Codex defaultPrompt containing \"$fragment\""
    fail=1
  fi
done

# Codex interface display copy is the first install-time explanation users see.
# Guard a small concept set so the display description cannot silently drift
# behind the richer defaultPrompt entry paths.
required_display_fragments=(
  "chooser"
  "prompt-to-goal"
  "autonomous"
  "doctrine"
  "worktree"
  "creator model"
  "status/help"
)
for fragment in "${required_display_fragments[@]}"; do
  if "$jq_bin" -e --arg fragment "$fragment" '.interface.longDescription | ascii_downcase | contains($fragment)' "$codex_plugin" >/dev/null; then
    echo "ok: Codex display copy covers \"$fragment\""
  else
    echo "::error file=$codex_plugin::interface.longDescription missing display concept \"$fragment\""
    fail=1
  fi
done

# (6) Neither marketplace.json may declare a version — including one nested under
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

# (7) Stable installs resolve immutably on both hosts. The release tag must
#     match VERSION.md; `main` is documented separately as the edge channel.
codex_market="$root/.agents/plugins/marketplace.json"
codex_refs=$("$jq_bin" -r '[.plugins[]? | select(.name == "pathfinder") | .source.ref?] | @tsv' "$codex_market" | tr -d '\r')
if [ "$codex_refs" = "v$v" ]; then
  echo "ok: $codex_market stable pathfinder source.ref = v$v"
else
  echo "::error file=$codex_market::stable pathfinder source.ref must equal immutable tag \"v$v\", got \"${codex_refs:-<missing>}\""
  fail=1
fi
claude_market="$root/.claude-plugin/marketplace.json"
claude_ref=$("$jq_bin" -r '.plugins[]? | select(.name == "pathfinder") | .source.ref? // empty' "$claude_market" | tr -d '\r')
claude_repo=$("$jq_bin" -r '.plugins[]? | select(.name == "pathfinder") | .source.repo? // empty' "$claude_market" | tr -d '\r')
if [ "$claude_ref" = "v$v" ] && [ "$claude_repo" = "chrisduvillard/pathfinder-skill" ]; then
  echo "ok: $claude_market stable source = $claude_repo@$claude_ref"
else
  echo "::error file=$claude_market::stable source must be chrisduvillard/pathfinder-skill at v$v"
  fail=1
fi

# (8) A merge or VERSION.md edit must never create a tag or GitHub Release.
# Parse every workflow semantically so YAML formatting, explicit keys, aliases, or
# flow mappings cannot hide a trigger, job, or contents-write permission.
release_workflow="$root/.github/workflows/release.yml"
if [ -n "${PATHFINDER_CONTROLLER_PYTHON:-}" ]; then
  release_python="$PATHFINDER_CONTROLLER_PYTHON"
elif [ -x "$root/.venv/bin/python" ]; then
  release_python="$root/.venv/bin/python"
elif [ -x "$root/.venv/Scripts/python.exe" ]; then
  release_python="$root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  release_python="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  release_python="$(command -v python)"
else
  echo "::error::Python 3.11+ is required to validate workflow release authority"
  exit 1
fi
if ! "$release_python" -c 'import yaml' >/dev/null 2>&1; then
  echo "::error::install workflow validation dependencies from requirements-controller.txt"
  exit 1
fi
if ! "$release_python" "$script_dir/validate-release-workflows.py" "$root"; then
  fail=1
fi

requested_binding_state=$(awk '
  /^      - name: Create release if VERSION.md declares a new version[[:space:]]*$/ { in_step=1; next }
  in_step && /^      - name:/ { exit }
  in_step && /^        env:[[:space:]]*$/ { in_env=1; next }
  in_env && /^        [^[:space:]]/ { in_env=0 }
  in_env && /^          (REQUESTED_VERSION|DECLARED_VERSION):/ {
    if ($0 ~ /^          REQUESTED_VERSION:/) {
      requested_keys++
      if ($0 ~ /^          REQUESTED_VERSION: \$\{\{ inputs\.version \}\}[[:space:]]*$/) requested_exact++
    }
    if ($0 ~ /^          DECLARED_VERSION:/) {
      declared_keys++
      if ($0 ~ /^          DECLARED_VERSION: \$\{\{ needs\.validate\.outputs\.version \}\}[[:space:]]*$/) declared_exact++
    }
  }
  END {
    print (requested_keys + 0) ":" (requested_exact + 0) ":" \
      (declared_keys + 0) ":" (declared_exact + 0)
  }
' "$release_workflow")
release_program=$(awk '
  /^      - name: Create release if VERSION.md declares a new version[[:space:]]*$/ { in_step=1; next }
  in_step && /^        run: \|[[:space:]]*$/ { in_run=1; next }
  in_run && /^          / { sub(/^          /, ""); print; next }
  in_run && /^[[:space:]]*$/ { print ""; next }
  in_run { exit }
' "$release_workflow")
if [ "$requested_binding_state" != "1:1:1:1" ] || [ -z "$release_program" ]; then
  echo "::error file=$release_workflow::release workflow must bind requested and validated versions and expose one executable release program"
  fail=1
else
  release_probe_dir=$(mktemp -d)
  release_probe_log="$release_probe_dir/gh.log"
  printf '%s\n' '#!/usr/bin/env sh' \
    'printf "%s\n" "$*" >> "$PATHFINDER_RELEASE_GH_LOG"' \
    'if [ "$1 $2" = "release view" ]; then exit 0; fi' \
    'exit 90' > "$release_probe_dir/gh"
  chmod +x "$release_probe_dir/gh"

  release_probe() {
    probe_ref="$1"
    probe_version="$2"
    : > "$release_probe_log"
    (
      cd "$root" || exit 1
      PATH="$release_probe_dir:$PATH" \
      PATHFINDER_RELEASE_GH_LOG="$release_probe_log" \
      GITHUB_REF="$probe_ref" \
      GH_TOKEN="probe-no-secret" \
      COMMIT_SHA="0000000000000000000000000000000000000000" \
      DECLARED_VERSION="$v" \
      REQUESTED_VERSION="$probe_version" \
      REPO="example/pathfinder-probe" \
      bash -c "$release_program"
    ) >/dev/null 2>&1
  }

  if release_probe "refs/heads/not-main" "$v" || [ -s "$release_probe_log" ]; then
    echo "::error file=$release_workflow::release program must reject a non-main ref before any GitHub release call"
    fail=1
  elif release_probe "refs/heads/main" "0.0.0-probe" || [ -s "$release_probe_log" ]; then
    echo "::error file=$release_workflow::release program must reject a mismatched requested version before any GitHub release call"
    fail=1
  elif ! release_probe "refs/heads/main" "$v" \
    || [ "$(cat "$release_probe_log")" != "release view v$v" ]; then
    echo "::error file=$release_workflow::release program must reach only the idempotent release lookup for an exact main/version request"
    fail=1
  else
    echo "ok: $release_workflow executable program rejects non-main and mismatched-version requests before GitHub access"
  fi
  rm -rf "$release_probe_dir"
fi

if [ "$fail" -eq 0 ]; then
  echo "manifests: all checks pass at $v"
fi
exit "$fail"
