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
fail=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ok()  { echo "ok: $*"; }
bad() { echo "::error::$*"; fail=1; }

# Fresh fixture root = a copy of the surfaces check-skill-consistency.sh reads.
newroot() {
  local d
  d="$(mktemp -d "$tmp/root.XXXXXX")"
  cp -r "$here/skills" "$d/skills"
  cp "$here/CONTRIBUTING.md" "$d/CONTRIBUTING.md"
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
  "$R/skills/pathfinder/SKILL.md" > "$R/skills/pathfinder/SKILL.md.new" \
  && mv "$R/skills/pathfinder/SKILL.md.new" "$R/skills/pathfinder/SKILL.md"
assert_catch "$R" "4-backtick|goal-pack|fence" "quad compensator catches an odd 4-backtick count (removed one goal-pack fence)"

echo "== parser 2b: structural quad-wrapper assertion (the net-even trap) =="
# Append a stray 4-backtick pair that wraps NO triple fence. The count guard still passes (count is
# even and >= 2), so only the STRUCTURAL guard can catch a 4-backtick region enclosing no nested
# triple — the exact blind spot the count-only compensator missed (TR-4).
R="$(newroot)"
printf '\n````\nstray quad pair that wraps no triple fence\n````\n' >> "$R/skills/pathfinder/SKILL.md"
assert_catch "$R" "quad-wrapper structure|encloses no 3-backtick" "structural guard catches a 4-backtick region with no nested triple (net-even trap)"

echo "== parser 3: check_skill_section window scanner =="
# Removing a guarded autonomous-safety token from inside the '## Autonomous mode'..'## Phase 7:'
# window must be caught (the token is required IN that section).
R="$(newroot)"
sed -i '/never self-merge/d' "$R/skills/pathfinder/SKILL.md"
assert_catch "$R" "never self-merge|autonomous-mode safety" "check_skill_section catches a safety token removed from its section"

echo "== parser 3b: section-boundary existence guard (a heading rename fails loudly) =="
# Rename a boundary heading check_skill_section keys on; the existence guard must catch the rename
# rather than let the section window silently re-scope past the renamed stop (BE-5 fail-open).
R="$(newroot)"
sed -i 's/^## Phase 7: Approval/## Phase Seven: Approval/' "$R/skills/pathfinder/SKILL.md"
assert_catch "$R" "section-boundary heading missing or renamed" "boundary-heading guard catches a renamed ## Phase 7: heading"

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

echo "== parser 6: orphan-reference guard (TR-5) =="
# check-skill-consistency.sh must flag a references/*.md that exists on disk but is not a required
# (cited + expected) reference. Drop an uncited orphan into a fixture and assert the guard fails.
R="$(newroot)"
printf '# orphan reference\nnot cited by SKILL.md and not in expected_refs\n' > "$R/skills/pathfinder/references/orphan.md"
assert_catch "$R" "orphan reference file" "orphan-reference guard catches an uncited references/*.md"

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
# Drop the qualifier from the core authorization grant while keeping the token. This is TR-1's
# literal acceptance test: a safety-token-preserving-but-logic-inverting change must be caught.
R="$(newroot)"
sed -i 's/and a conditional self-merge/and a self-merge/' "$R/skills/pathfinder/SKILL.md"
assert_catch_b "$R" "self-merge|governing qualifier|loosened gate" "self-merge polarity: dropping the qualifier (token intact) is caught"

echo "== behavior 2: 'unattended' must carry a negation =="
# Remove the sole negation attached to an 'unattended' mention; the line then permits what it forbade.
R="$(newroot)"
sed -i 's/a charter `Never unattended` category/a charter always-unattended category/' "$R/skills/pathfinder/SKILL.md"
assert_catch_b "$R" "unattended|governing qualifier" "unattended inversion: removing the negation is caught"

if [ "$fail" -eq 0 ]; then
  echo "test-validators: all parser meta-tests pass"
fi
# The net-even quad trap (a symmetric 4->3 goal-pack downgrade + a stray even quad pair) is CAUGHT by
# the structural quad-wrapper assertion, exercised by parser 2b above — closing the v2.21.3 TR-4 follow-up.
exit "$fail"
