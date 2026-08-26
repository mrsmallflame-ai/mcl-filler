#!/bin/bash
# MCL Filler — one-shot setup + run for macOS
#
# First run:  ./run-mcl.sh "https://www.mclcinema.com/MCLSelectSeat.aspx?ci=014&si=113882&visLang=2" 16
# Later runs: same command — it reuses the venv.
#
# Usage: ./run-mcl.sh "<mcl url>" [workers] [seats] [idle_poll] [rounds]
#        rounds 0 = infinite (default)

set -e

URL="$1"
WORKERS="${2:-12}"
SEATS="${3:-6}"
IDLE_POLL="${4:-20}"
ROUNDS="${5:-0}"

if [ -z "$URL" ]; then
    echo "usage: $0 \"<mcl url>\" [workers] [seats] [idle_poll] [rounds]"
    exit 1
fi

# --- go to repo dir (clone if missing) ---
if [ ! -f "./mcl_filler.py" ]; then
    if [ ! -d "./mcl-filler" ]; then
        echo "[*] cloning repo..."
        git clone https://github.com/mrsmallflame-ai/mcl-filler.git
    fi
    cd mcl-filler
fi

# --- python check (3.10+) ---
if command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    echo "python3 not found. Install from https://python.org or: brew install python"
    exit 1
fi
echo "[*] using $($PY --version)"

# --- venv ---
if [ ! -d ".venv" ]; then
    echo "[*] creating virtualenv..."
    $PY -m venv .venv
fi
VPY=".venv/bin/python"

# --- deps ---
echo "[*] ensuring httpx installed..."
"$VPY" -m pip install --quiet --disable-pip-version-check httpx

# --- env knobs ---
export BLAZE_SEATS="$SEATS"
export BLAZE_IDLE_POLL="$IDLE_POLL"
if [ "$ROUNDS" -gt 0 ] 2>/dev/null; then export BLAZE_ROUNDS="$ROUNDS"; else unset BLAZE_ROUNDS; fi

# --- go ---
echo "[*] launching filler: workers=$WORKERS seats=$SEATS"
"$VPY" mcl_filler.py --url "$URL" "$WORKERS"

echo ""
echo "👋 done."