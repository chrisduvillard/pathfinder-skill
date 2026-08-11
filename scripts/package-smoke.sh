#!/usr/bin/env bash
set -euo pipefail

root="${1:-.}"
root="$(cd "$root" && pwd)"
version="${2:-}"
source_mode="${3:-worktree}"
if [ -z "$version" ]; then
  version="$(awk '/^Version:[[:space:]]+[0-9]+\.[0-9]+\.[0-9]+[[:space:]]*$/ { print $2; exit }' "$root/VERSION.md" | tr -d '\r')"
fi
if [ -z "$version" ]; then
  echo "::error::package smoke could not resolve VERSION.md"
  exit 1
fi

archive_dir="$(mktemp -d)"
trap 'rm -rf "$archive_dir"' EXIT
archive="$archive_dir/pathfinder-v$version.tar"
package="$archive_dir/package"
mkdir -p "$package"

if [ "$source_mode" = "git" ]; then
  git -C "$root" archive --format=tar --output="$archive" HEAD
elif [ "$source_mode" = "worktree" ]; then
  tar -cf "$archive" --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=.pathfinder --exclude=.agent-work -C "$root" .
else
  echo "::error::package source mode must be worktree or git"
  exit 1
fi
tar -xf "$archive" -C "$package"

if [ -x "$root/.venv/bin/python" ]; then
  smoke_python="$root/.venv/bin/python"
elif [ -x "$root/.venv/Scripts/python.exe" ]; then
  smoke_python="$root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  smoke_python="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  smoke_python="$(command -v python)"
else
  echo "::error::Python 3.11 is required for package smoke"
  exit 1
fi

if [ "$(jq -r '.version' "$package/.codex-plugin/plugin.json")" != "$version" ]; then
  echo "::error::packaged Codex manifest version mismatch"
  exit 1
fi
if [ "$(jq -r '.plugins[] | select(.name == "pathfinder") | .source.ref' "$package/.agents/plugins/marketplace.json")" != "v$version" ]; then
  echo "::error::packaged stable marketplace is not pinned to v$version"
  exit 1
fi
if [ "$(jq -r '.plugins[] | select(.name == "pathfinder") | .source.ref' "$package/.claude-plugin/marketplace.json")" != "v$version" ]; then
  echo "::error::packaged Claude marketplace is not pinned to v$version"
  exit 1
fi

bash "$package/scripts/check-manifests.sh" "$package"
bash "$package/scripts/check-skill-consistency.sh" "$package"
bash "$package/scripts/check-skill-behavior.sh" "$package"
bash "$package/scripts/check-shell.sh" "$package"
PATHFINDER_DOCS_PYTHON="$smoke_python" bash "$package/scripts/check-generated-docs.sh" "$package"
PATHFINDER_EVAL_PYTHON="$smoke_python" bash "$package/scripts/check-evals.sh" "$package"
PATHFINDER_EVAL_PYTHON="$smoke_python" bash "$package/scripts/check-replay-evals.sh" "$package"
PATHFINDER_CONTROLLER_PYTHON="$smoke_python" bash "$package/scripts/check-controller.sh" "$package"
(
  cd "$archive_dir"
  PATHFINDER_PYTHON="$smoke_python" \
    bash "$package/scripts/pathfinder-controller.sh" doctor --json >/dev/null
)

echo "package-smoke: archive for v$version passes"
