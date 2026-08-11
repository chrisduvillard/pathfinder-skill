#!/usr/bin/env bash
# Credential-free install and skill-discovery smoke tests for Codex and Claude Code.

set -euo pipefail

root="${1:-.}"
root="$(cd "$root" && pwd)"

jq_bin="${JQ:-}"
if [ -z "$jq_bin" ]; then
  if command -v jq >/dev/null 2>&1; then
    jq_bin="jq"
  elif command -v jq.exe >/dev/null 2>&1; then
    jq_bin="jq.exe"
  else
    echo "::error::jq is required for host install smoke tests"
    exit 1
  fi
fi

codex_bin="${PATHFINDER_CODEX_BIN:-codex}"
claude_bin="${PATHFINDER_CLAUDE_BIN:-claude}"
for host_bin in "$codex_bin" "$claude_bin"; do
  if ! command -v "$host_bin" >/dev/null 2>&1; then
    echo "::error::$host_bin is required for host install smoke tests"
    exit 1
  fi
done

version="$(awk '/^Version:[[:space:]]+[0-9]+\.[0-9]+\.[0-9]+[[:space:]]*$/ { print $2; exit }' "$root/VERSION.md" | tr -d '\r')"
if [ -z "$version" ]; then
  echo "::error::host install smoke could not resolve VERSION.md"
  exit 1
fi

probe_root="$(mktemp -d)"
probe_root="$(cd "$probe_root" && pwd -P)"
cleanup() {
  rm -rf -- "$probe_root"
}
trap cleanup EXIT

snapshot="$probe_root/package"
mkdir -p "$snapshot"
if git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1 &&
   [ "$(git -C "$root" rev-parse --show-toplevel)" = "$root" ]; then
  file_list="$probe_root/worktree-files"
  archive="$probe_root/worktree.tar"
  git -C "$root" ls-files --cached --others --exclude-standard -z |
    while IFS= read -r -d '' path; do
      case "$path" in
        */__pycache__/*) continue ;;
      esac
      if [ -e "$root/$path" ] || [ -L "$root/$path" ]; then
        printf '%s\0' "$path"
      fi
    done > "$file_list"
  (
    cd "$root"
    tar -cf "$archive" --null -T "$file_list"
  )
  tar -xf "$archive" -C "$snapshot"
else
  (
    cd "$root"
    tar -cf - .
  ) | tar -xf - -C "$snapshot"
fi

codex_source="$probe_root/codex-source"
codex_marketplace="$probe_root/codex-marketplace"
codex_root="$probe_root/codex-root"
codex_target="$probe_root/codex-target"
mkdir -p "$codex_source" "$codex_marketplace/.agents/plugins" "$codex_root" "$codex_target"
cp -R "$snapshot/." "$codex_source/"
git -C "$codex_source" init -q
git -C "$codex_source" -c core.autocrlf=false add -A
git -C "$codex_source" \
  -c user.name=Pathfinder \
  -c user.email=pathfinder@example.invalid \
  -c commit.gpgSign=false \
  commit -qm snapshot
codex_ref="$(git -C "$codex_source" rev-parse HEAD)"
case "$(uname -s)" in
  CYGWIN*|MINGW*|MSYS*) codex_source_url="file:///$(cygpath -m "$codex_source")" ;;
  *) codex_source_url="file://$codex_source" ;;
esac
"$jq_bin" \
  --arg source_url "$codex_source_url" \
  --arg source_ref "$codex_ref" \
  '.plugins[0].source = {"source":"url","url":$source_url,"ref":$source_ref}' \
  "$snapshot/.agents/plugins/marketplace.json" \
  > "$codex_marketplace/.agents/plugins/marketplace.json"

env CODEX_HOME="$codex_root" "$codex_bin" plugin marketplace add "$codex_marketplace" --json \
  > "$probe_root/codex-marketplace.json"
env CODEX_HOME="$codex_root" "$codex_bin" plugin add pathfinder@pathfinder --json \
  > "$probe_root/codex-install.json"
env CODEX_HOME="$codex_root" "$codex_bin" plugin list --json \
  > "$probe_root/codex-list.json"

"$jq_bin" -e --arg version "$version" '
  .installed == [(.installed[0] | select(
    .pluginId == "pathfinder@pathfinder" and
    .version == $version and
    .installed == true and
    .enabled == true
  ))]
' "$probe_root/codex-list.json" >/dev/null
codex_install_path="$("$jq_bin" -r '.installedPath' "$probe_root/codex-install.json")"
case "$codex_install_path" in
  "$codex_root"/*) ;;
  *) echo "::error::Codex installed outside the isolated probe root"; exit 1 ;;
esac
codex_skill_path="$codex_install_path/skills/pathfinder/SKILL.md"
if [ ! -f "$codex_skill_path" ]; then
  echo "::error::Codex install is missing skills/pathfinder/SKILL.md"
  exit 1
fi

git -C "$codex_target" init -q
codex_prompt='$pathfinder:pathfinder Show Pathfinder status only.'
env CODEX_HOME="$codex_root" "$codex_bin" -C "$codex_target" debug prompt-input "$codex_prompt" \
  > "$probe_root/codex-prompt.json"
"$jq_bin" -e --arg locator "$codex_skill_path" --arg prompt "$codex_prompt" '
  ([.. | strings] | any(contains("- pathfinder:pathfinder:"))) and
  ([.. | strings] | any(contains($locator))) and
  ([.. | strings] | any(. == $prompt))
' "$probe_root/codex-prompt.json" >/dev/null

codex_manual_root="$probe_root/codex-manual-root"
codex_manual_target="$probe_root/codex-manual-target"
mkdir -p "$codex_manual_root" "$codex_manual_target/.agents/skills"
cp -R "$snapshot/skills/pathfinder" "$codex_manual_target/.agents/skills/pathfinder"
git -C "$codex_manual_target" init -q
manual_prompt='$pathfinder Show Pathfinder status only.'
env CODEX_HOME="$codex_manual_root" "$codex_bin" -C "$codex_manual_target" debug prompt-input "$manual_prompt" \
  > "$probe_root/codex-manual-prompt.json"
manual_skill_path="$codex_manual_target/.agents/skills/pathfinder/SKILL.md"
"$jq_bin" -e --arg locator "$manual_skill_path" --arg prompt "$manual_prompt" '
  ([.. | strings] | any(contains("- pathfinder: Use when"))) and
  ([.. | strings] | any(contains($locator))) and
  ([.. | strings] | any(. == $prompt))
' "$probe_root/codex-manual-prompt.json" >/dev/null

claude_marketplace="$probe_root/claude-marketplace"
claude_root="$probe_root/claude-root"
mkdir -p "$claude_marketplace/plugin" "$claude_marketplace/.claude-plugin" "$claude_root"
cp -R "$snapshot/." "$claude_marketplace/plugin/"
"$jq_bin" --arg version "$version" '
  .plugins[0].source = "./plugin" |
  .plugins[0].version = $version
' "$snapshot/.claude-plugin/marketplace.json" \
  > "$claude_marketplace/.claude-plugin/marketplace.json"

env CLAUDE_CONFIG_DIR="$claude_root" "$claude_bin" plugin validate --strict "$claude_marketplace" \
  > "$probe_root/claude-validate.txt"
env CLAUDE_CONFIG_DIR="$claude_root" "$claude_bin" plugin marketplace add "$claude_marketplace" \
  > "$probe_root/claude-marketplace.txt"
env CLAUDE_CONFIG_DIR="$claude_root" "$claude_bin" plugin install pathfinder@pathfinder \
  > "$probe_root/claude-install.txt"
env CLAUDE_CONFIG_DIR="$claude_root" "$claude_bin" plugin list --json \
  > "$probe_root/claude-list.json"
env CLAUDE_CONFIG_DIR="$claude_root" "$claude_bin" plugin details pathfinder@pathfinder \
  > "$probe_root/claude-details.txt"

"$jq_bin" -e --arg version "$version" '
  length == 1 and
  .[0].id == "pathfinder@pathfinder" and
  .[0].version == $version and
  .[0].enabled == true
' "$probe_root/claude-list.json" >/dev/null
claude_install_path="$("$jq_bin" -r '.[0].installPath' "$probe_root/claude-list.json")"
case "$claude_install_path" in
  "$claude_root"/*) ;;
  *) echo "::error::Claude installed outside the isolated probe root"; exit 1 ;;
esac
if [ ! -f "$claude_install_path/skills/pathfinder/SKILL.md" ]; then
  echo "::error::Claude install is missing skills/pathfinder/SKILL.md"
  exit 1
fi
if ! grep -qF 'Source: pathfinder@pathfinder' "$probe_root/claude-details.txt" ||
   ! grep -Eq 'Skills \(1\).*pathfinder' "$probe_root/claude-details.txt" ||
   ! grep -qF 'On-invoke cost is paid each time a skill or agent fires.' "$probe_root/claude-details.txt"; then
  echo "::error::Claude did not load the installed Pathfinder skill inventory"
  exit 1
fi

echo "ok: $($codex_bin --version) installed plugin and exposed namespaced + manual Pathfinder skills"
echo "ok: $($claude_bin --version) installed and loaded the Pathfinder skill inventory"
echo "host-installs: credential-free Codex and Claude Code smoke tests pass at v$version"
