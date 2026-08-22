#!/usr/bin/env python3
"""
MCL Cinema Seat Filler — BLAZE engine (pure HTTP, no browser rendering).

Usage:
  python3 mcl_filler.py --url '<any mcl link>' [workers]
  python3 mcl_filler.py --ci 017 --si 127637 [workers]

Accepts desktop, mobile, or seat-plan MCL links. Fills every available
seat using parallel HTTP workers. Benchmarks: full 81-seat house in 39s,
peak 378 seats/min with 16 workers.
"""
import argparse, asyncio, os, re, sys

def parse_mcl_url(url):
    """Extract (ci, si) from any MCL link format."""
    for pat in (r'[?&]cinemaCodeID=(\d+)[^]*?[?&]sessionID=(\d+)',
                r'[?&]cinemaCode=(\d+)[^]*?[?&]filmSessionId=(\d+)',
                r'[?&]ci=(\d+)&si=(\d+)'):
        m = re.search(pat, url)
        if m:
            return m.group(1), m.group(2)
    # fallback: independent params
    ci = re.search(r'(?:cinemaCodeID|cinemaCode|ci)=(\d+)', url)
    si = re.search(r'(?:sessionID|filmSessionId|si)=(\d+)', url)
    if ci and si:
        return ci.group(1), si.group(1)
    return None, None

async def run(ci, si, workers):
    import blaze2
    # reuse blaze2's engine
    sys_argv = sys.argv
    sys.argv = ["blaze2", ci, si, str(workers)]
    try:
        await blaze2.main()
    finally:
        sys.argv = sys_argv

async def main():
    p = argparse.ArgumentParser(description="MCL rapid seat filler (pure HTTP)")
    p.add_argument("--url", help="Any MCL link (desktop/mobile/seat-plan)")
    p.add_argument("--ci", help="Cinema code")
    p.add_argument("--si", help="Session ID")
    p.add_argument("workers", nargs="?", type=int,
                   default=int(os.environ.get("BLAZE_WORKERS", "12")),
                   help="Parallel workers (default 12)")
    args = p.parse_args()

    if args.url:
        ci, si = parse_mcl_url(args.url)
        if not ci:
            print(f"❌ Could not parse cinema/session from: {args.url[:100]}")
            return
    elif args.ci and args.si:
        ci, si = args.ci, args.si
    else:
        p.print_help()
        return

    print(f"🎯 target: ci={ci} si={si} workers={args.workers}")
    await run(ci, si, args.workers)

if __name__ == "__main__":
    asyncio.run(main())