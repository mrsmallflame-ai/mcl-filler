#!/bin/bash
# MCL filler — Mac residential relay
# Paste this ENTIRE block into Terminal.app on your Mac.
#
# What it does: runs a tiny SOCKS5 proxy on your Mac and tunnels it to the VPS,
# so fillers running on the VPS egress through your home IP (MCL blocks
# datacenter + WARP IPs but never residential ones).
#
# Prereq: `ssh ubuntu@43.134.182.181` already works passwordless from this Mac.
#
# Keep this window open while filling. Ctrl+C to stop everything cleanly.

set -e
VPS="ubuntu@43.134.182.181"

# 1) copy the tiny stdlib-only SOCKS server to the Mac (if not already here)
mkdir -p ~/.mcl-relay
if [ ! -f ~/.mcl-relay/mcl_socks.py ]; then
  scp -q "$VPS:~/mcl-filler/mcl_socks.py" ~/.mcl-relay/mcl_socks.py
fi

# 2) start the local SOCKS server on 127.0.0.1:1081
pkill -f "mcl_socks.py 1081" 2>/dev/null || true
nohup python3 ~/.mcl-relay/mcl_socks.py 1081 127.0.0.1 > ~/.mcl-relay/socks.log 2>&1 &
echo "✅ SOCKS server on Mac 127.0.0.1:1081 (pid $!)"

# 3) reverse-tunnel it to the VPS as 127.0.0.1:11080
#    (ServerAlive keeps NAT alive; -N = no shell, just the tunnel)
echo "🔌 Opening reverse tunnel Mac:1081 -> VPS:11080 ..."
ssh -N -R 11080:127.0.0.1:1081 \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
    "$VPS"
