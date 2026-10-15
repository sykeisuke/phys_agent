#!/bin/zsh
# Run one archived task: scripts/run_task.sh docs/tasks/<file>.txt [model]
# Logs to notes/run_<task>_<date>.log and prints the [usage] line.
set -e
cd "$(dirname "$0")/.."
TASK_FILE="$1"; MODEL="${2:-claude-sonnet-5}"
[ -f "$TASK_FILE" ] || { echo "usage: $0 docs/tasks/<task>.txt [model]"; exit 1; }
source scripts/env.sh
: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY (never paste it into a file)}"
mkdir -p notes
LOG="notes/run_$(basename "$TASK_FILE" .txt)_$(date +%Y%m%d_%H%M).log"
echo "model=$MODEL  task=$TASK_FILE  log=$LOG"
python -u -m agent "$(cat "$TASK_FILE")" --review ai --model "$MODEL" 2>&1 | tee "$LOG"
grep '^\[usage\]' "$LOG" || echo "no [usage] line — run did not finish"
