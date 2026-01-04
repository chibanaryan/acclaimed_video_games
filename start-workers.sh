#!/bin/bash
# Opens VS Code workspace and starts Claude workers with beads integration
#
# Each worker:
#   - Has BD_ACTOR set to identify itself in beads
#   - Runs Claude Code with permissions skipped
#   - Can claim tasks with: bd update <id> --claim
#
# Workflow:
#   1. Create tasks: bd create "Task description"
#   2. Workers check: bd ready --unassigned
#   3. Worker claims: bd update <id> --claim
#   4. Worker completes: bd close <id>

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
BD_PATH="$HOME/.local/bin/bd"

# Start beads daemon for shared coordination (if available)
if [ -x "$BD_PATH" ]; then
  "$BD_PATH" daemon --start 2>/dev/null || true
  echo "Beads daemon started"
fi

# Open VS Code workspace
code "$PARENT_DIR/acclaimedgames-workers.code-workspace"

# Start each worker in its own Terminal with Claude
for i in {1..8}; do
  WORKER_DIR="$PARENT_DIR/acclaimedgames-worker-$i"
  if [ -d "$WORKER_DIR" ]; then
    osascript -e "
      tell application \"Terminal\"
        do script \"cd '$WORKER_DIR' && export BD_ACTOR=worker-$i && echo 'Worker $i ready. Run: bd ready --unassigned' && claude --dangerously-skip-permissions\"
      end tell
    "
  else
    echo "Warning: $WORKER_DIR does not exist"
  fi
done

echo ""
echo "Workers started with beads integration."
echo ""
echo "Quick reference:"
echo "  bd ready --unassigned    # See available tasks"
echo "  bd update <id> --claim   # Claim a task"
echo "  bd close <id>            # Complete a task"
echo "  bd activity --follow     # Watch all activity"
