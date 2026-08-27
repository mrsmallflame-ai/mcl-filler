#!/bin/bash
# mcl_botfill.sh — resolve a movie by name, launch fillers in tmux per session.
#
# Usage:
#   bash mcl_botfill.sh "<movie>" [cinema] [date] [workers]
#   bash mcl_botfill.sh "kung fu soccer" "movie town" aug28 8
#
# Each matched session gets its own tmux: fill-<si> running vps-fill.sh.
# Logs land in ~/mcl-filler/logs/fill-<si>.log.
#
# Env: BLAZE_PROXY passes through to mcl_find.py + vps-fill.sh automatically.
# Set BLAZE_FIND_DRY=1 to list what would launch without launching.

set -u
cd ~/mcl-filler
MOVIE="${1:?usage: mcl_botfill.sh \"<movie>\" [cinema] [date] [workers]}"
CINEMA="${2:-}"
DATE="${3:-}"
WORKERS="${4:-8}"
mkdir -p logs

echo "🔎 resolving sessions for: $MOVIE ${CINEMA} ${DATE}"

# one python pass turns finder JSON into clean "ci si time ctx" lines
ROWS=$(.venv/bin/python mcl_find.py --movie "$MOVIE" \
        ${CINEMA:+--cinema "$CINEMA"} ${DATE:+--date "$DATE"} --json 2>/dev/null | \
       .venv/bin/python -c '
import sys, json
try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
for r in rows:
    print(r["ci"], r["si"], r.get("time", "-"))')

if [ -z "$ROWS" ]; then
  echo "❌ no sessions found for '$MOVIE'. Try different keywords/cinema/date."
  exit 1
fi

echo "✅ matched:"
echo "$ROWS"
[ "${BLAZE_FIND_DRY:-0}" = "1" ] && { echo "(dry run — nothing launched)"; exit 0; }

LAUNCHED=0
while read -r CI SI TTIME; do
  [ -z "$SI" ] && continue
  if tmux has-session -t "fill-$SI" 2>/dev/null; then
    echo "  ↷ si=$SI already running (tmux: fill-$SI)"
    continue
  fi
  tmux new-session -d -s "fill-$SI" \
    "BLAZE_PROXY=\"${BLAZE_PROXY:-}\" bash $(pwd)/vps-fill.sh $CI $SI $WORKERS >> logs/fill-$SI.log 2>&1"
  echo "  🚀 ci=$CI si=$SI ($TTIME) -> tmux: fill-$SI"
  LAUNCHED=$((LAUNCHED+1))
done <<< "$ROWS"

echo
echo "🟢 $LAUNCHED new filler(s) launched."
echo "   monitor : grep -h 'BOOKED\\|full' logs/fill-*.log | tail -20"
echo "   attach  : tmux attach -t fill-<si>"
echo "   stop all: for s in \$(tmux ls | grep '^fill-' | cut -d: -f1); do tmux kill-session -t \$s; done"
