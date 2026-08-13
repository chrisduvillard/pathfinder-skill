#!/usr/bin/env bash
#
# Meta-tests for the awk/grep PARSERS embedded in the drift-guard validators.
#
# The validators in scripts/check-*.sh gate every mirrored invariant, but their own
# hand-rolled parsers (the code-fence open/close tracker, the 4-backtick compensator,
# the check_skill_section window scanner, and the VERSION.md / changelog parsers) had
# no test — a regression in one of them would silently weaken or false-pass every
# invariant it scopes, caught only by manual dogfooding. (TR-3 / TR-4.)
#
# Strategy, two complementary styles:
#   * Whole-script tests (fence tracker, quad compensator, section scanner): copy the
#     REAL valid skill tree into a fixture, inject exactly ONE defect, run the REAL
#     check-skill-consistency.sh, and assert it now exits non-zero AND names the check.
#     The baseline test proves an unmodified copy passes, so a failure means the injected
#     defect — and only it — was caught. (check-skill-consistency uses no jq, so absolute
#     fixture paths are safe on every platform.)
#   * Extracted-logic tests (VERSION.md parser, release.yml changelog extractor): pull the
#     REAL regex / awk program out of the script or workflow at runtime and run it on a
#     tiny fixture. This tests the current source without invoking jq — avoiding the
#     Windows/MSYS case where jq.exe cannot open an absolute POSIX fixture path under
#     MSYS_NO_PATHCONV=1 (which the manifest check needs for its "/pathfinder charter" arg).
#
# Mutating a parser's core condition turns the matching test red. Read-only against the
# repo; all writes go to a mktemp fixture removed on exit.
#
# Usage: bash scripts/test-validators.sh [ROOT-ignored]
# Exit 0 when every parser behaves as specified; non-zero otherwise.

set -uo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
skillsrc="$here/scripts/check-skill-consistency.sh"
mansrc="$here/scripts/check-manifests.sh"
relsrc="$here/.github/workflows/release.yml"
if [ -x "$here/.venv/bin/python" ]; then
  manifest_python="$here/.venv/bin/python"
elif [ -n "${PATHFINDER_CONTROLLER_PYTHON:-}" ]; then
  manifest_python="$PATHFINDER_CONTROLLER_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  manifest_python="$(command -v python3)"
else
  manifest_python="$(command -v python)"
fi
fail=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ok()  { echo "ok: $*"; }
bad() { echo "::error::$*"; fail=1; }

# BSD sed requires an argument after -i while GNU sed does not. Keep fixture
# mutations portable by writing a sibling file and replacing the fixture only
# after sed succeeds.
rewrite() {  # <file> <sed-arguments...>
  local file="$1" staged
  shift
  staged="$file.new"
  if sed "$@" "$file" > "$staged"; then
    mv "$staged" "$file"
  else
    rm -f "$staged"
    bad "fixture mutation failed for $file"
    return 1
  fi
}

# Fresh fixture root = a copy of the surfaces check-skill-consistency.sh reads.
newroot() {
  local d
  d="$(mktemp -d "$tmp/root.XXXXXX")"
  cp -r "$here/skills" "$d/skills"
  cp "$here/CONTRIBUTING.md" "$d/CONTRIBUTING.md"
  printf '%s' "$d"
}

new_manifest_root() {
  local d
  d="$(mktemp -d "$tmp/manifests.XXXXXX")"
  mkdir -p "$d/.github/workflows" "$d/.claude-plugin" "$d/.codex-plugin" "$d/.agents/plugins"
  cp "$here/.github/workflows/release.yml" "$d/.github/workflows/release.yml"
  cp "$here/.claude-plugin/plugin.json" "$d/.claude-plugin/plugin.json"
  cp "$here/.claude-plugin/marketplace.json" "$d/.claude-plugin/marketplace.json"
  cp "$here/.codex-plugin/plugin.json" "$d/.codex-plugin/plugin.json"
  cp "$here/.agents/plugins/marketplace.json" "$d/.agents/plugins/marketplace.json"
  cp "$here/VERSION.md" "$d/VERSION.md"
  printf '%s' "$d"
}

csc() { MSYS_NO_PATHCONV=1 bash "$skillsrc" "$1" 2>&1; }

assert_pass() {  # <root> <label>
  local out ec
  out="$(csc "$1")"; ec=$?
  if [ "$ec" -eq 0 ]; then ok "$2"; else bad "$2 (exit=$ec, expected 0)"; printf '%s\n' "$out" | tail -4; fi
}
assert_catch() {  # <root> <regex> <label>
  local out ec
  out="$(csc "$1")"; ec=$?
  if [ "$ec" -ne 0 ] && printf '%s' "$out" | grep -Eq "$2"; then
    ok "$3"
  else
    bad "$3 (exit=$ec; expected non-zero output matching /$2/)"
  fi
}

assert_manifest_pass() {  # <root> <label>
  local out ec
  out="$(cd "$1" && PATHFINDER_CONTROLLER_PYTHON="$manifest_python" bash "$mansrc" . 2>&1)"; ec=$?
  if [ "$ec" -eq 0 ]; then ok "$2"; else bad "$2 (exit=$ec, expected 0)"; printf '%s\n' "$out" | tail -4; fi
}
assert_manifest_catch() {  # <root> <regex> <label>
  local out ec
  out="$(cd "$1" && PATHFINDER_CONTROLLER_PYTHON="$manifest_python" bash "$mansrc" . 2>&1)"; ec=$?
  if [ "$ec" -ne 0 ] && printf '%s' "$out" | grep -Eq "$2"; then
    ok "$3"
  else
    bad "$3 (exit=$ec; expected non-zero output matching /$2/)"
  fi
}

echo "== baseline: a clean copy passes check-skill-consistency (guards against fixture rot) =="
assert_pass "$(newroot)" "baseline: clean tree passes check-skill-consistency"

echo "== parser 1: code-fence open/close tracker =="
# A reference file ENDING inside an open 4-backtick fence must be reported, not silently
# balanced — the class the pre-v2.12.0 parity-counter was blind to.
R="$(newroot)"
printf '\n````text\nunterminated 4-backtick fence — no closing line\n' >> "$R/skills/pathfinder/references/scout-brief-template.md"
assert_catch "$R" "unterminated|open fence|mis-nested" "fence tracker catches a file ending inside an open 4-backtick fence"

echo "== parser 2: 4-backtick goal-pack compensator =="
# Deleting one goal-pack 4-backtick fence makes the count odd; the compensator (and/or the
# tracker) must catch the corrupted nesting. (The documented symmetric net-even blind spot is
# a KNOWN limitation — see NOTE at end — so this locks in the even/>=2 contract, not that trap.)
R="$(newroot)"
awk 'BEGIN{done=0} /^````/ && done==0 {done=1; next} {print}' \
  "$R/skills/pathfinder/references/routes/goal-generation.md" > "$R/skills/pathfinder/references/routes/goal-generation.md.new" \
  && mv "$R/skills/pathfinder/references/routes/goal-generation.md.new" "$R/skills/pathfinder/references/routes/goal-generation.md"
assert_catch "$R" "4-backtick|goal-pack|fence" "quad compensator catches an odd 4-backtick count (removed one goal-pack fence)"

echo "== parser 2b: structural quad-wrapper assertion (the net-even trap) =="
# Append a stray 4-backtick pair that wraps NO triple fence. The count guard still passes (count is
# even and >= 2), so only the STRUCTURAL guard can catch a 4-backtick region enclosing no nested
# triple — the exact blind spot the count-only compensator missed (TR-4).
R="$(newroot)"
printf '\n````\nstray quad pair that wraps no triple fence\n````\n' >> "$R/skills/pathfinder/SKILL.md"
assert_catch "$R" "quad-wrapper structure|encloses no 3-backtick" "structural guard catches a 4-backtick region with no nested triple (net-even trap)"

echo "== parser 3: check_skill_section window scanner =="
# Removing the v1 self-merge prohibition from inside the autonomous window
# must be caught (the token is required in that section).
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" '/The former \*\*conditional self-merge\*\* path is prohibited/d'
assert_catch "$R" "conditional self-merge|autonomous-mode safety" "check_skill_section catches a removed self-merge prohibition"

echo "== parser 3b: section-boundary existence guard (a heading rename fails loudly) =="
# Rename a boundary heading check_skill_section keys on; the existence guard must catch the rename
# rather than let the section window silently re-scope past the renamed stop (BE-5 fail-open).
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/execute-review.md" 's/^## Phase 7: Approval/## Phase Seven: Approval/'
assert_catch "$R" "section-boundary heading missing or renamed" "boundary-heading guard catches a renamed ## Phase 7: heading"

echo "== parser 3c: sequential Goal-pack authority guard =="
# Removing the ordered binding-hash handoff must fail instead of leaving a queue
# whose membership can drift between approval and activation.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" '/ordered binding hashes/d'
assert_catch "$R" "ordered binding hashes" "autonomous guard catches a removed ordered binding-hash contract"

echo "== parser 4a: VERSION.md 'Version:' regex (extracted from check-manifests.sh) =="
# Pull the REAL version_re out of check-manifests.sh and prove it (a) matches exactly one clean
# 'Version:' line and (b) counts two when a second is present — the >1 case the parser rejects.
version_re="$(sed -n "s/^version_re='\(.*\)'\$/\1/p" "$mansrc" | head -1)"
if [ -z "$version_re" ]; then
  bad "could not extract version_re from check-manifests.sh (parser 4a)"
else
  printf 'Version: 2.21.2\n' > "$tmp/V1"
  printf 'Version: 1.2.3\nVersion: 4.5.6\n' > "$tmp/V2"
  c1="$(grep -cE "$version_re" "$tmp/V1")"; c2="$(grep -cE "$version_re" "$tmp/V2")"
  if [ "$c1" -eq 1 ] && [ "$c2" -eq 2 ]; then
    ok "version regex matches exactly one clean line and flags a second (the reject case)"
  else
    bad "version regex miscounted (clean=$c1 expected 1, two-line=$c2 expected 2) (parser 4a)"
  fi
fi

echo "== parser 4b: 'Changes in v<version>:' changelog-heading check (pattern extracted from check-manifests.sh) =="
# Pull the REAL heading pattern out of check-manifests.sh (the `grep -qF "Changes in v$v:"` line) so
# this test tracks the source like 4a/4c, instead of re-validating a hand-copied literal that would
# keep passing if the source check changed or broke.
heading_fmt="$(sed -n 's/.*grep -qF "\(Changes in v[^"]*\)".*/\1/p' "$mansrc" | head -1)"
if [ -z "$heading_fmt" ]; then
  bad "could not extract the changelog-heading pattern from check-manifests.sh (parser 4b)"
else
  heading="$(printf '%s' "$heading_fmt" | sed 's/[$]v/2.0.0/')"   # substitute a concrete version for $v
  printf 'Changes in v2.0.0:\n- entry\n' > "$tmp/CLg"
  printf 'Release notes:\n- entry\n'      > "$tmp/CLb"
  if grep -qF "$heading" "$tmp/CLg" && ! grep -qF "$heading" "$tmp/CLb"; then
    ok "changelog-heading check (extracted pattern \"$heading_fmt\") finds a present heading and rejects a missing one"
  else
    bad "changelog-heading check failed with extracted pattern \"$heading_fmt\" (parser 4b)"
  fi
fi

echo "== parser 4c: release.yml changelog block-extractor (awk extracted from the real workflow) =="
# Extract the REAL awk program from release.yml and prove it returns ONLY the target version's
# block, stopping at the next 'Changes in v' heading — a regression in its start/stop conditions
# (e.g. dropping the terminator) would spill an adjacent block into the release notes.
awkprog="$(sed -n "s/.*\(index(\$0,hdr)==1.*g{print}\).*/\1/p" "$relsrc" | head -1)"
if [ -z "$awkprog" ]; then
  bad "could not extract the changelog-extractor awk program from release.yml (parser 4c)"
else
  cat > "$tmp/CL2" <<'EOF'
Changes in v2.0.0:
- keep this line

Changes in v1.0.0:
- OLD entry that must NOT leak into v2.0.0 notes
EOF
  notes="$(awk -v hdr="Changes in v2.0.0:" "$awkprog" "$tmp/CL2")"
  if printf '%s' "$notes" | grep -q "keep this line" && ! printf '%s' "$notes" | grep -q "OLD entry"; then
    ok "changelog extractor returns only the target block (stops at the next heading)"
  else
    bad "changelog extractor leaked an adjacent block or dropped the target (parser 4c)"
  fi
fi

echo "== policy 4d: release workflow remains manual-only, main-only, and version-confirmed =="
R="$(new_manifest_root)"
assert_manifest_pass "$R" "release workflow baseline satisfies the manual release boundary"

R="$(new_manifest_root)"
awk '{ if ($0 == "  workflow_dispatch:") print "  push: {branches: [main]}"; print }' \
  "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "release trigger must be exactly.*workflow_dispatch" \
  "release guard catches an added inline automatic push trigger"

R="$(new_manifest_root)"
awk '{
  if ($0 == "  workflow_dispatch:") {
    print "  ? push"
    print "  : {}"
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "release trigger must be exactly.*workflow_dispatch" \
  "release guard catches an explicit-key automatic push trigger"

R="$(new_manifest_root)"
awk '{
  if ($0 == "        required: true") {
    print "        required: false"
    print "        default: 3.2.0"
    next
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "must require one typed version confirmation" \
  "release input guard catches an optional defaulted version"

R="$(new_manifest_root)"
awk '{
  if ($0 == "      - name: Create release if VERSION.md declares a new version") {
    print "      - name: Unexpected write-capable step"
    print "        run: gh release create v0.0.0"
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "exactly two gated jobs and one isolated write permission" \
  "release job-shape guard catches an added write-capable step"

R="$(new_manifest_root)"
awk '
  /^  release:[[:space:]]*$/ { in_release=1 }
  in_release && $0 == "    if: github.ref == '\''refs/heads/main'\'' && needs.validate.outputs.version == inputs.version" {
    print "    if: true"
    next
  }
  { print }
' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "exactly two gated jobs and one isolated write permission" \
  "release job-shape guard catches removal of the pre-job authority gate"

R="$(new_manifest_root)"
awk '
  /^  release:[[:space:]]*$/ {
    print "  alternate-release:"
    print "    runs-on: ubuntu-latest"
    print "    permissions: {contents: write}"
    print "    steps: []"
  }
  { print }
' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "exactly two gated jobs and one isolated write permission" \
  "release permission guard catches an extra job with inline contents write"

R="$(new_manifest_root)"
awk 'BEGIN { replaced=0 } {
  if ($0 == "permissions:") {
    print "permissions: write-all"
    replaced=1
    next
  }
  if (replaced == 1 && $0 == "  contents: read") { replaced=2; next }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "exactly two gated jobs and one isolated write permission" \
  "release permission guard catches top-level write-all syntax"

R="$(new_manifest_root)"
awk '{
  if ($0 == "  release:") {
    print "  alternate: {runs-on: ubuntu-latest, permissions: write-all, steps: []}"
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "exactly two gated jobs and one isolated write permission" \
  "release job-list guard catches a compact alternate write job"

R="$(new_manifest_root)"
awk '{
  if ($0 == "  release:") {
    print "  ? alternate"
    print "  :"
    print "    runs-on: ubuntu-latest"
    print "    ? permissions"
    print "    : write-all"
    print "    steps: []"
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "exactly two gated jobs and one isolated write permission" \
  "release canonical-syntax guard catches explicit job and permission keys"

R="$(new_manifest_root)"
awk '{
  if ($0 == "    permissions:") {
    print "    \"permissions\": write-all"
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "invalid workflow YAML|exactly two gated jobs and one isolated write permission" \
  "release permission guard catches a quoted alternate permission key"

R="$(new_manifest_root)"
cat > "$R/.github/workflows/auto-release.yml" <<'YAML'
name: automatic release bypass
on:
  push:
    branches: [main]
permissions:
  contents: write
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: gh release create v0.0.0
YAML
assert_manifest_catch "$R" "release/tag authority is permitted only" \
  "repository-wide guard catches a second automatic release workflow"

R="$(new_manifest_root)"
awk '{
  if ($0 == "          if [ \"$GITHUB_REF\" != \"refs/heads/main\" ]; then") {
    print "          # if [ \"$GITHUB_REF\" != \"refs/heads/main\" ]; then"
    print "          if false; then"
    next
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "reject a non-main ref before any GitHub release call" \
  "release behavior probe catches an inert commented main-branch check"

R="$(new_manifest_root)"
awk '{
  if ($0 == "          if [ \"$REQUESTED_VERSION\" != \"$version\" ]; then") {
    print "          # if [ \"$REQUESTED_VERSION\" != \"$version\" ]; then"
    print "          if false; then"
    next
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "reject a mismatched requested version before any GitHub release call" \
  "release behavior probe catches an inert commented typed-version check"

R="$(new_manifest_root)"
awk '{
  if ($0 == "          REQUESTED_VERSION: ${{ inputs.version }}") {
    print "          # REQUESTED_VERSION: ${{ inputs.version }}"
    print "          REQUESTED_VERSION: 3.2.0"
    next
  }
  print
}' "$R/.github/workflows/release.yml" > "$R/.github/workflows/release.yml.new" \
  && mv "$R/.github/workflows/release.yml.new" "$R/.github/workflows/release.yml"
assert_manifest_catch "$R" "must bind requested and validated versions" \
  "release binding guard catches a constant input hidden behind a decoy comment"

echo "== parser 5: SHA-pin scan covers composite actions (BE-3/SEC-1) =="
# check-portability.sh must flag an unpinned uses: inside a composite action definition
# (.github/actions/<name>/action.yml), not only top-level workflows. Build a minimal fixture with an
# unpinned composite action and assert the scan fails.
P="$(mktemp -d "$tmp/port.XXXXXX")"
mkdir -p "$P/.github/actions/demo"
cat > "$P/.github/actions/demo/action.yml" <<'YAML'
runs:
  using: composite
  steps:
    - uses: some/unpinned-action@v1
YAML
if bash "$here/scripts/check-portability.sh" "$P" >/dev/null 2>&1; then
  bad "SHA-pin scan MISSED an unpinned composite action under .github/actions/ (parser 5)"
else
  ok "SHA-pin scan catches an unpinned composite action (parser 5)"
fi

echo "== parser 5b: GNU-only in-place sed scan =="
# check-portability.sh must reject GNU's argument-less in-place form, which
# fails on BSD sed. Keep the literal inside printf so this meta-test does not
# itself look like a sed command to the scanner.
P="$(mktemp -d "$tmp/port.XXXXXX")"
mkdir -p "$P/scripts"
printf '%s\n' '#!/usr/bin/env bash' "sed -"'i '\''s/old/new/'\'' fixture.md' > "$P/scripts/unportable.sh"
port_out="$(bash "$here/scripts/check-portability.sh" "$P" 2>&1)"; port_ec=$?
if [ "$port_ec" -ne 0 ] && printf '%s' "$port_out" | grep -Eq 'sed.*in-place|sed -i'; then
  ok "portability guard catches GNU-only argument-less in-place sed"
else
  bad "portability guard MISSED GNU-only argument-less in-place sed (exit=$port_ec)"
fi

echo "== parser 5c: ShellCheck wrapper discovers and rejects a warning =="
S="$(mktemp -d "$tmp/shellcheck.XXXXXX")"
mkdir -p "$S/scripts"
printf '%s\n' '#!/usr/bin/env bash' 'unused="dead assignment"' > "$S/scripts/unused.sh"
shell_out="$(bash "$here/scripts/check-shell.sh" "$S" 2>&1)"; shell_ec=$?
if [ "$shell_ec" -ne 0 ] && printf '%s' "$shell_out" | grep -q 'SC2034'; then
  ok "ShellCheck wrapper discovers Bash files and rejects warning-level findings"
else
  bad "ShellCheck wrapper missed an unused assignment (exit=$shell_ec)"
fi

echo "== parser 5d: Chocolatey tools cross Windows workflow step boundaries =="
P="$(mktemp -d "$tmp/port.XXXXXX")"
mkdir -p "$P/.github/workflows"
printf '%s\n' \
  'jobs:' \
  '  check:' \
  '    steps:' \
  '      - shell: pwsh' \
  '        run: choco install jq shellcheck --yes' > "$P/.github/workflows/check.yml"
port_out="$(bash "$here/scripts/check-portability.sh" "$P" 2>&1)"; port_ec=$?
if [ "$port_ec" -ne 0 ] && printf '%s' "$port_out" | grep -Eq 'ChocolateyInstall/bin|GITHUB_PATH'; then
  ok "portability guard catches a Chocolatey ShellCheck install hidden from later Git-Bash steps"
else
  bad "portability guard missed a Chocolatey ShellCheck install without a cross-step PATH export (exit=$port_ec)"
fi

echo "== parser 6: orphan-reference guard (TR-5) =="
# check-skill-consistency.sh must flag a references/*.md that exists on disk but is not a required
# (cited + expected) reference. Drop an uncited orphan into a fixture and assert the guard fails.
R="$(newroot)"
printf '# orphan reference\nnot cited by SKILL.md and not in expected_refs\n' > "$R/skills/pathfinder/references/orphan.md"
assert_catch "$R" "orphan reference file" "orphan-reference guard catches an uncited references/*.md"

echo "== parser 7: Explore-level universal-escape guard (C5/FE-1,FE-2) =="
# Drop the canonical 'describe your own' escape from the L1 Domain screen; the guard must catch that an
# Explore level lost a universal escape the funnel rules require at every level. [^ ]* matches the
# em-dash separator so no multibyte literal is embedded in this script.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/explore-drilldown.md" 's/None of these: describe your own [^ ]* the area you care about/None of these: the area you care about/'
assert_catch "$R" "Explore level|universal escape|describe your own" "Explore-escape guard catches a level that dropped 'describe your own'"

echo "== parser 7b: skipped scout domains do not create placeholder artifacts =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/discovery.md" \
  's/Create briefs only for selected domains; do not create files for skipped domains\./Write a short `not selected: <reason>` placeholder for skipped domains./'
assert_catch "$R" "scout-artifact invariant|placeholder files for skipped scout" "scout-artifact guard catches skipped-domain placeholder regression"

echo "== parser 7c: verification artifacts follow lifecycle state =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/synthesis.md" \
  's/Do not create `03b-verification\.md` before Phase 4b starts\./Create `03b-verification.md` before Phase 4b starts./'
assert_catch "$R" "lifecycle artifact invariant|unused lifecycle placeholder" "lifecycle guard catches pre-created verification artifact regression"

echo "== parser 7d: progress updates stay semantic rather than per-file =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/SKILL.md" \
  's/Do not send a progress update for each file, search, invariant, scout, verifier, controller call, or artifact write\./Send a progress update for each file, search, invariant, scout, verifier, controller call, or artifact write./'
assert_catch "$R" "user-facing progress invariant|progress update for each file" "progress guard catches per-file narration regression"

echo "== parser 7e: durable refresh stays separate from chat progress =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/SKILL.md" \
  's/Durable state refresh and user-facing progress are separate concerns\./Durable state refresh and user-facing progress are the same concern./'
assert_catch "$R" "user-facing progress invariant|Durable state refresh" "progress guard catches persistence/chat conflation"

echo "== parser 8: intent/eligibility separation guard (C3) =="
# Conflate item eligibility back into intent state in only the first definition;
# the coherence guard must catch the missing execution_eligibility boundary.
R="$(newroot)"
rewrite "$R/skills/pathfinder/SKILL.md" \
  -e 's/from per-item `execution_eligibility`/from per-item eligibility/' \
  -e 's/a separate `execution_eligibility` record/a separate eligibility record/'
assert_catch "$R" "intent-clarity definition|execution_eligibility" "intent-clarity guard catches a conflated item-eligibility boundary"

echo "== parser 9: doctrine-gated autonomy invariants =="
# Full Autonomous Mission Mode depends on canonical, schema-validated Project Doctrine. Dropping the
# schema path from the autonomous route must fail the mirror/section guard rather than leaving
# `.pathfinder/doctrine.json` as unvalidated local state.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's#schemas/intent/doctrine.schema.json#schemas/intent/doctrine.schema.old#'
assert_catch "$R" "doctrine|doctrine.schema.json" "canonical doctrine schema removal is caught"

echo "== parser 9b: generated intent views cannot become runtime state =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/Never parse/Parse/'
assert_catch "$R" "canonical-intent|Never parse|Markdown" "canonical-intent guard catches a generated-view parse grant"

echo "== parser 9c: controller-less installs cannot author Markdown intent =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/intent-refresh.md" 's/Never write authoritative Markdown as a fallback/Write authoritative Markdown as a fallback/'
assert_catch "$R" "intent-refresh controller invariant|authoritative Markdown" "manual-install fallback guard catches authoritative Markdown writes"

echo "== parser 9d: monorepo intent namespaces never inherit or fall back =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/SKILL.md" 's/Never inherit or fall back across intent namespaces/Inherit root intent when scoped intent is missing/'
assert_catch "$R" "monorepo intent isolation|inherit|fall back" "intent namespace guard catches cross-product fallback"

# ---- Production Markdown-authority guard ----
markdownsrc="$here/scripts/check-markdown-authority.sh"
new_markdown_root() {
  local d
  d="$(mktemp -d "$tmp/markdown.XXXXXX")"
  mkdir -p "$d/scripts"
  cp -r "$here/pathfinder_core" "$d/pathfinder_core"
  cp "$markdownsrc" "$d/scripts/check-markdown-authority.sh"
  printf '%s' "$d"
}
markdown_check() { bash "$markdownsrc" "$1" 2>&1; }

echo "== parser 10: current renderer replacement and legacy migration allowlist =="
R="$(new_markdown_root)"
if markdown_check "$R" >/dev/null; then
  ok "exact legacy-migration and generated-view replacement readers are allowed"
else
  bad "clean production Markdown-reader allowlist was rejected"
fi

echo "== parser 10b: seeded production Markdown state reader =="
R="$(new_markdown_root)"
printf '%s\n' 'def load_state():' '    with open("07-run-log.md", "r", encoding="utf-8") as stream:' '        return stream.read()' > "$R/pathfinder_core/forbidden_reader.py"
out="$(markdown_check "$R")"; ec=$?
if [ "$ec" -ne 0 ] && printf '%s' "$out" | grep -Eq 'Markdown parser allowlist drift|forbidden_reader'; then
  ok "Markdown-authority guard catches a new production view reader"
else
  bad "Markdown-authority guard missed a new production view reader (exit=$ec)"
fi

echo "== parser 10c: renderer allowlist is function-scoped =="
R="$(new_markdown_root)"
printf '%s\n' '' 'def parse_rendered_status(markdown: str):' '    return markdown.split("state:", 1)' >> "$R/pathfinder_core/rendering.py"
out="$(markdown_check "$R")"; ec=$?
if [ "$ec" -ne 0 ] && printf '%s' "$out" | grep -Eq 'Markdown parser allowlist drift|parse_rendered_status'; then
  ok "renderer module cannot add a second Markdown state parser"
else
  bad "renderer function allowlist accepted a new Markdown state parser (exit=$ec)"
fi

# ---- Behavioral invariant harness (check-skill-behavior.sh) ----
skillbeh="$here/scripts/check-skill-behavior.sh"
csb() { MSYS_NO_PATHCONV=1 bash "$skillbeh" "$1" 2>&1; }
assert_pass_b() {  # <root> <label>
  local out ec
  out="$(csb "$1")"; ec=$?
  if [ "$ec" -eq 0 ]; then ok "$2"; else bad "$2 (exit=$ec, expected 0)"; printf '%s\n' "$out" | tail -4; fi
}
assert_catch_b() {  # <root> <regex> <label>
  local out ec
  out="$(csb "$1")"; ec=$?
  if [ "$ec" -ne 0 ] && printf '%s' "$out" | grep -Eq "$2"; then
    ok "$3"
  else
    bad "$3 (exit=$ec; expected non-zero output matching /$2/)"
  fi
}

echo "== behavior baseline: a clean copy passes check-skill-behavior =="
assert_pass_b "$(newroot)" "baseline: clean tree passes check-skill-behavior"

echo "== behavior 1: self-merge must carry a gating qualifier (the loosened-gate class) =="
# Drop the v1 prohibition while keeping the self-merge token. The same-line
# safety-direction guard must catch the loosened grant.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/There is no self-merge in v1;/Self-merge is available in v1;/'
assert_catch_b "$R" "self-merge|governing qualifier|loosened gate" "self-merge polarity: dropping the qualifier (token intact) is caught"

echo "== behavior 2: 'unattended' must carry a negation =="
# Remove the sole negation attached to an 'unattended' mention; the line then permits what it forbade.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/A Doctrine `Never unattended` category/A Doctrine always-unattended category/'
assert_catch_b "$R" "unattended|governing qualifier" "unattended inversion: removing the negation is caught"

echo "== behavior 3: a decision screen must carry its 'None of these' escape =="
# Delete the gap-driven-clarification screen's own "None of these" escape line, orphaning that
# non-exempt decision screen from its escape. (Anchored on the exact escape line rather than the
# first substring match: SKILL.md's prompt-to-goal routing prose now mentions "None of these"
# descriptively — in an exempt fixed-menu screen with no "Agent recommends:" line at all — before
# the real escape line, so a bare first-match would orphan nothing.)
R="$(newroot)"
awk 'BEGIN{d=0} /^None of these, let me describe it\.$/ && d==0 {d=1; next} {print}' \
  "$R/skills/pathfinder/references/routes/prompt-to-goal.md" > "$R/skills/pathfinder/references/routes/prompt-to-goal.md.new" \
  && mv "$R/skills/pathfinder/references/routes/prompt-to-goal.md.new" "$R/skills/pathfinder/references/routes/prompt-to-goal.md"
assert_catch_b "$R" "screen-escape|None of these|allowlist" "screen-escape: dropping a screen's escape is caught"

echo "== behavior 4: renaming a Family-A window boundary heading fails closed (C1/TR-B6) =="
# Rename the '## Autonomous mode' window-start heading check_direction keys on. Without the existence
# guard the four Family-A direction checks would pass VACUOUSLY (insec never sets); the guard must
# catch the rename instead of letting the safety window fail open.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/^## Autonomous mode (doctrine-gated full mission)/## Autonomous section (doctrine-gated full mission)/'
assert_catch_b "$R" "Family-A window boundary|missing or renamed" "boundary-existence guard catches a renamed ## Autonomous mode heading (fail-open closed)"

echo "== behavior 5: dropping the Stop-conditions irreversible/external carve-out is caught (C1/SEC-1) =="
# The carve-out sits outside the Family-A window, so check_direction never sees it. Drop its
# validator token; the dedicated carve-out guard must catch it.
R="$(newroot)"
rewrite "$R/skills/pathfinder/SKILL.md" 's/irreversible\/external hard-stop carve-out/irreversible external stop floor/g'
assert_catch_b "$R" "carve-out|irreversible/external" "carve-out guard catches a dropped irreversible/external hard-stop carve-out"

echo "== behavior 6: an unconditional self-merge grant is caught though the whole-line check passes (C2/TR-B1) =="
# Invert an in-window self-merge clause to grant it unconditionally while leaving the line's other
# qualifier ("default-deny") intact — check_direction still passes, so only the forbidden-inversion
# guard can catch it. Targets line 1301's unique context so the Stop-conditions carve-out stays intact.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/\*\*conditional self-merge\*\*/\*\*unconditional self-merge\*\*/'
assert_catch_b "$R" "unconditional self-merge|default-deny inverted" "self-merge inversion caught: unconditional grant survives the whole-line qualifier check"

echo "== behavior 7: a benign self-merge reword preserving direction still passes (C2 false-red guard) =="
# Reword the same bold-wrapped self-merge phrase without inverting meaning (still conditional). The
# forbidden-inversion guard must NOT fire — proving it does not block legitimate future rewordings.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/\*\*conditional self-merge\*\*/\*\*self-merge remains prohibited\*\*/'
assert_pass_b "$R" "benign self-merge reword (still conditional) does not false-red"

echo "== behavior 8: protected-area work stays eligible only with doctrine proof =="
# The new stronger autonomy model deliberately makes protected code areas eligible, but only under
# doctrine proof + scoped verification. Reverting the clause to blanket exclusion must fail.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" \
       -e 's/Protected code areas are eligible with doctrine proof/Protected code areas are excluded/' \
       -e 's/protected code areas are eligible with doctrine proof/protected code areas are excluded/'
assert_catch_b "$R" "protected code areas|doctrine proof|eligible" "protected-area eligibility proof guard catches blanket exclusion"

echo "== behavior 9: irreversible/external hard stops keep the force-push boundary =="
# The hard floor is narrowed to irreversible/external actions; force-pushes must remain in that floor.
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/, force-pushes//'
assert_catch_b "$R" "irreversible/external hard stops|force-push" "hard-stop guard catches dropped force-push boundary"

echo "== behavior 10: autonomous mode must create a mission worktree before edits =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" 's/create a mission worktree before edits/may edit in the current checkout/'
assert_catch_b "$R" "mission worktree|before edits" "mission-worktree guard catches current-checkout edits"

echo "== behavior 11: absent branch protection remains awaiting-review, not self-merge =="
R="$(newroot)"
rewrite "$R/skills/pathfinder/references/routes/autonomous.md" \
       -e 's/Absent branch protection produces awaiting-review/Absent branch protection may self-merge/' \
       -e 's/absent branch protection produces awaiting-review/absent branch protection may self-merge/'
assert_catch_b "$R" "absent branch protection|awaiting-review|self-merge" "branch-protection guard catches absent-protection self-merge"

if [ "$fail" -eq 0 ]; then
  echo "test-validators: all parser meta-tests pass"
fi
# The net-even quad trap (a symmetric 4->3 goal-pack downgrade + a stray even quad pair) is CAUGHT by
# the structural quad-wrapper assertion, exercised by parser 2b above — closing the v2.21.3 TR-4 follow-up.
exit "$fail"
