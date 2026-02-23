#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/.vscode.template"
TARGET_DIR="$REPO_ROOT/.vscode"

mkdir -p "$TARGET_DIR"

for file in tasks.json settings.json launch.json extensions.json; do
  src="$TEMPLATE_DIR/$file"
  dst="$TARGET_DIR/$file"
  if [[ -f "$dst" ]]; then
    echo "Keeping existing $dst"
    continue
  fi
  cp "$src" "$dst"
  echo "Created $dst"
done

echo "VS Code local config initialized from .vscode.template."
