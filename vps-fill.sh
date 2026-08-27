#!/bin/bash
# Run this ON THE VPS after mac-relay.sh is open on the Mac.
#
# Usage:
#   bash vps-fill.sh <any MCL link or ci si> [workers]
#
# Example (4 sessions, 8 workers each):
#   bash vps-fill.sh 014 113989 8
#   BLAZE_PROXY="socks5://127.0.0.1:11080" python3 mcl_filler.py --url '<link>'

cd ~/mcl-filler
PROXY="${BLAZE_PROXY:-socks5://127.0.0.1:11080}"

# health check: is the Mac relay reachable?
if ! curl -s --max-time 10 -x "$PROXY" -o /dev/null https://example.com; then
  echo "❌ Relay not reachable via $PROXY."
  echo "   Open mac-relay.sh in Terminal.app on the Mac first, then retry."
  exit 1
fi
echo "✅ Relay up ($PROXY) — egressing through home IP"

CI="$1"; SI="$2"; W="${3:-8}"
exec env BLAZE_PROXY="$PROXY" .venv/bin/python blaze2.py "$CI" "$SI" "$W"
