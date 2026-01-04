#!/bin/bash
# Opens VS Code workspace and Terminal windows for all workers

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

code "$PARENT_DIR/acclaimedgames-workers.code-workspace"

for i in {1..8}; do
  open -a Terminal "$PARENT_DIR/acclaimedgames-worker-$i"
done

echo "Run 'claude --dangerously-skip-permissions' in each terminal"
