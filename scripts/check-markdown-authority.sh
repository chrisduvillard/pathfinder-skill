#!/usr/bin/env bash
# Reject new production Markdown-to-state readers while preserving narrow compatibility/view repair.

set -uo pipefail

root="${1:-.}"
production="$root/pathfinder_core"

if [ ! -d "$production" ]; then
  echo "::error::missing production package: $production"
  exit 1
fi

scan_file() {
  local file="$1" relative="$2"
  awk -v relative="$relative" '
    function emit() {
      if (function_name != "" && markdown_signal && parser_signal) {
        print relative ":" function_name
      }
    }
    /^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\(/ {
      emit()
      function_name = $0
      sub(/^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+/, "", function_name)
      sub(/[[:space:]]*\(.*/, "", function_name)
      markdown_signal = 0
      parser_signal = 0
    }
    function_name != "" {
      if ($0 ~ /[Mm]arkdown|\.md|INTENT_FILES|_GENERATED_(MARKER|PREFIX)|pathfinder:(charter|roadmap|doctrine|generated)|(^|[^A-Za-z_])(intent_clarity|completion|clarity):/) {
        markdown_signal = 1
      }
      if ($0 ~ /\.read_(text|bytes)[[:space:]]*\(|\.read[[:space:]]*\(|\.open[[:space:]]*\([[:space:]]*([)]|["\047]r)|(^|[^A-Za-z0-9_.])open[[:space:]]*\([^,)]*([)]|,[[:space:]]*["\047]r)|re\.(search|match|findall|finditer|compile)[[:space:]]*\(|\.(split|partition|find|finditer|count)[[:space:]]*\(|_replace_generated_region[[:space:]]*\(/) {
        parser_signal = 1
      }
    }
    END { emit() }
  ' "$file"
}

actual="$({
  for file in "$production"/*.py; do
    [ -f "$file" ] || continue
    relative="${file#"$root"/}"
    scan_file "$file" "$relative"
  done
} | sort -u)"

# Exact production exceptions: legacy intent conversion and generated-block view replacement.
expected="$(printf '%s\n' \
  'pathfinder_core/migrations.py:_migrate_intent_text' \
  'pathfinder_core/migrations.py:migrate_intent' \
  'pathfinder_core/rendering.py:_replace_generated_region' \
  'pathfinder_core/rendering.py:repair_candidates_markdown' \
  'pathfinder_core/rendering.py:repair_verification_markdown' \
  | sort -u)"

if [ "$actual" != "$expected" ]; then
  echo "::error::production Markdown parser allowlist drift"
  echo "Expected only:"
  printf '%s\n' "$expected"
  echo "Found:"
  printf '%s\n' "${actual:-<none>}"
  exit 1
fi

echo "markdown authority: production readers are limited to legacy migration and generated-view replacement"
