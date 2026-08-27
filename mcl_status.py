#!/usr/bin/env python3
"""mcl_status.py — one-shot status of all running/recent fillers.

Reads ~/mcl-filler/logs/fill-*.log + live tmux session names. No network.

Output modes:
  human (default): readable summary
  --json:          machine-readable (for the cron ping loop / chat replies)

Exit code 0 always; "active" tells the caller whether any filler still runs.
"""
import glob, json, os, re, subprocess, sys, time

LOGDIR = os.path.expanduser("~/mcl-filler/logs")
RE_BOOKED = re.compile(r"W\d+: ✅ \[([A-Z0-9,\s]+)\] BOOKED")
RE_REJECT = re.compile(r"W\d+: ❌")
RE_FULL = re.compile(r"house currently full")
RE_ROUND = re.compile(r"\[round (\d+)\]")
RE_TOTAL = re.compile(r"total (\d+) \|")


def live_tms():
    try:
        out = subprocess.run(["tmux", "ls"], capture_output=True, text=True, timeout=5).stdout
        return {l.split(":")[0] for l in out.splitlines() if l.startswith("fill-")}
    except Exception:
        return set()


def parse_log(path):
    st = {"log": os.path.basename(path), "booked_seats": [], "rejects": 0,
          "house_full_seen": False, "last_round": 0, "running_total": 0,
          "mtime": os.path.getmtime(path), "last_line": "", "proxy": None}
    try:
        with open(path, errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return st
    st["last_line"] = lines[-1][:120] if lines else ""
    for ln in lines[:3]:
        mp = re.search(r"proxy=(\S+)", ln)
        if mp:
            st["proxy"] = mp.group(1)
    for ln in lines:
        mb = RE_BOOKED.search(ln)
        if mb:
            st["booked_seats"] += [s.strip() for s in mb.group(1).split(",")]
        if RE_REJECT.search(ln):
            st["rejects"] += 1
        if RE_FULL.search(ln):
            st["house_full_seen"] = True
        mr = RE_ROUND.search(ln)
        if mr:
            st["last_round"] = int(mr.group(1))
    # 'total N' appears on progress lines; take max seen
    for ln in reversed(lines):
        mt = RE_TOTAL.search(ln)
        if mt:
            st["running_total"] = int(mt.group(1))
            break
    return st


def main():
    as_json = "--json" in sys.argv
    tms = live_tms()
    logs = sorted(glob.glob(os.path.join(LOGDIR, "fill-*.log")))
    reports = []
    seen_names = {os.path.basename(p)[: -len(".log")] for p in logs}
    for name in tms - seen_names:  # tmux alive but no log yet (just started)
        reports.append({"session": name, "si": name.replace("fill-", ""),
                        "alive": True, "booked_seats": [], "rejects": 0,
                        "house_full_seen": False, "last_round": 0,
                        "running_total": 0, "mtime": time.time(),
                        "last_line": "(no log yet)", "proxy": None})
    for p in logs:
        name = os.path.basename(p)[: -len(".log")]
        st = parse_log(p)
        st["session"] = name
        st["si"] = name.replace("fill-", "")
        st["alive"] = name in tms
        reports.append(st)

    active = sum(1 for r in reports if r["alive"])
    total_booked = sum(len(r["booked_seats"]) for r in reports)
    full_houses = [r["si"] for r in reports if r["house_full_seen"]]

    if as_json:
        print(json.dumps({
            "active_fillers": active,
            "sessions_tracked": len(reports),
            "seats_claimed_total": total_booked,
            "houses_ever_full": full_houses,
            "all_stopped": active == 0,
            "fillers": [{k: r[k] for k in ("session", "si", "alive", "last_round",
                                           "running_total", "rejects",
                                           "house_full_seen", "proxy")} |
                         {"seats": r["booked_seats"]} for r in reports],
            "generated_at": time.time(),
        }, indent=2))
        return

    print(f"🎬 MCL filler status — {active} active / {len(reports)} tracked | "
          f"seats claimed total: {total_booked}")
    if not reports:
        print("   (no fillers have run yet)")
    for r in sorted(reports, key=lambda x: -x["mtime"]):
        flag = "🟢 running" if r["alive"] else ("⚪ stopped" if r["last_round"] else "⚪ fresh")
        full = " 🏠FULL" if r["house_full_seen"] else ""
        px = f" proxy={r['proxy']}" if r.get("proxy") else ""
        print(f"  {flag}{full} si={r['si']} round={r['last_round']} "
              f"claimed={len(r['booked_seats'])} rejects={r['rejects']}{px}")
        if r["booked_seats"]:
            print(f"     seats: {', '.join(r['booked_seats'][-12:])}"
                  + (" …" if len(r["booked_seats"]) > 12 else ""))
        elif r["last_line"]:
            print(f"     last: {r['last_line']}")


if __name__ == "__main__":
    main()
