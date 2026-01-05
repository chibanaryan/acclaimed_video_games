#!/bin/bash
# Opens VS Code workspace and starts Claude workers in git worktrees

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Open VS Code workspace
code "$PARENT_DIR/acclaimedgames-workers.code-workspace"

# Start each worker in its own Terminal with Claude
for i in {1..8}; do
  WORKER_DIR="$PARENT_DIR/acclaimedgames-worker-$i"
  if [ -d "$WORKER_DIR" ]; then
    osascript -e "
      tell application \"Terminal\"
        do script \"cd '$WORKER_DIR' && echo 'Worker $i ready.' && claude --dangerously-skip-permissions\"
      end tell
    "
  else
    echo "Warning: $WORKER_DIR does not exist"
  fi
done

echo ""
echo "Workers started."
