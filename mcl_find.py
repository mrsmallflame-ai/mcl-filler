#!/usr/bin/env python3
"""MCL session finder: movie/cinema/date -> ci/si pairs, filler-ready.

Usage:
  python3 mcl_find.py --movie "kung fu soccer" [--cinema "movie town"|014] [--date aug28] [--json]

Routes through BLAZE_PROXY (same env var as blaze2.py) because every MCL
booking domain blocks datacenter/WARP IPs. Add --debug to dump raw HTML.
"""
import argparse, asyncio, json, os, re, sys, time
import html as H
import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PROXY = os.environ.get("BLAZE_PROXY") or None

MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}

CINEMAS = {  # known short names -> codes (extendable)
    "movie town": "014", "movietown": "014",
    "citygate": "017", "mcl citygate": "017",
    "cyberport": "016", "the one": "021",
    "k11": "020", "star house": "003", "apm": "007",
}


def parse_date_token(tok):
    """'aug28'/'28aug'/'aug 28'/None -> (month, day) or None."""
    if not tok:
        return None
    t = tok.lower().replace(" ", "")
    m = re.match(r"([a-z]{3})(\d{1,2})", t) or re.match(r"(\d{1,2})([a-z]{3})", t)
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    if a.isdigit():
        return MONTHS.get(b), int(a)
    return MONTHS.get(a), int(b)


async def fetch(c, url, params=None, referer=None):
    """GET with busy-page retry/backoff (MCL serves 'server busy' under load)."""
    for attempt in range(1, 7):
        try:
            r = await c.get(url, params=params,
                            headers={"Referer": referer} if referer else None)
            if r.status_code == 200 and "server busy" not in r.text.lower():
                return r.text
        except Exception as e:
            if attempt == 6:
                return ""   # unreachable — network blocked; let the caller show a friendly error
        await asyncio.sleep(min(3 * attempt + (attempt % 3), 20))
    return ""


def extract_sessions(page_html, base="https://www.mclcinema.com/"):
    """Pull (ci, si, ctx) triples from any MCL page."""
    out, seen = [], set()
    for m in re.finditer(r'MCLSelectSeat\.aspx\?visLang=\d&(?:amp;)?ci=(\d+)&(?:amp;)?si=(\d+)', page_html):
        ci, si = m.group(1), m.group(2)
        if (ci, si) in seen:
            continue
        seen.add((ci, si))
        idx = m.start()
        raw = page_html[max(0, idx - 500):idx + 250]
        txt = H.unescape(re.sub(r"<[^>]+>", " ", raw))
        txt = re.sub(r"\s+", " ", txt).strip()
        out.append({"ci": ci, "si": si, "ctx": txt[-220:]})
    return out


def score(session, words, cinema, dtoken, today):
    s = session["ctx"].lower()
    sc = 0
    whits = sum(1 for w in words if w in s)
    sc += 10 * whits
    session["_whits"] = whits   # MUST be >0 or the session is a different film
    if cinema:
        cin = CINEMAS.get(cinema, cinema)
        if cin in (session["ci"], s):
            sc += 25
    if dtoken:
        mon, day = dtoken
        # accept several common formats: Aug 28, 28 Aug, 2026-08-28, 28/8...
        needles = [f"{mon}/{day}", f"{mon}-{day}", f"0{mon}/{day}",
                   f"{day} aug", f"{day} august" if mon == 8 else "",
                   f"aug {day}" if mon == 8 else "", f"{mon}/{day:02d}"]
        monname = next((k for k, v in MONTHS.items() if v == mon), "")
        full = {"jan":"january","feb":"february","mar":"march","apr":"april",
                "may":"may","jun":"june","jul":"july","aug":"august",
                "sep":"september","oct":"october","nov":"november","dec":"december"}
        if monname:
            needles += [f"{day} {monname}", f"{monname} {day}",
                        f"{day}{monname}", f"{monname[:3]}{day}"]
        if any(n and n in s for n in needles):
            sc += 30
    tm = re.findall(r"\d{1,2}:\d{2}[AP]M", session["ctx"].upper())
    if tm:
        session["time"] = tm[0]
        sc += 5
    session["_score"] = sc
    return sc


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--movie", required=True, help="film name keywords")
    ap.add_argument("--cinema", default="", help='"movie town" or code like 014')
    ap.add_argument("--date", default="", help='e.g. aug28')
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    words = [w for w in a.movie.lower().split() if len(w) > 2]
    cinema = a.cinema.strip().lower()
    dtoken = parse_date_token(a.date)

    async with httpx.AsyncClient(follow_redirects=True,
                                 timeout=httpx.Timeout(15, connect=8),
                                 proxy=PROXY) as c:
        c.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        pages, htmls = [], {}
        for url in ("https://www.mclcinema.com/TicketingByDateCinema.aspx?visLang=2",
                    "https://www.mclcinema.com/NowShowing.aspx?visLang=2&mode=list"):
            h = await fetch(c, url)
            if h and "MCLSelectSeat" in h:
                htmls[url] = h
                if a.debug:
                    open(f"/tmp/mcl-find-{len(htmls)}.html", "w").write(h)

    if not htmls:
        print("❌ MCL not reachable" + (" through proxy " + PROXY if PROXY else " (this IP may be blocked)") + ".")
        print("   Fixes:") 
        print("   • Run the Mac relay first (mac-relay.sh on your Mac), then: export BLAZE_PROXY=socks5://127.0.0.1:11080")
        print("   • Or run the finder from your Mac: python3 mcl_find.py ...")
        print("   • Or retry later — MCL temporarily bans heavy IPs for minutes at a time.")
        if a.json:
            print("[]")
        sys.exit(2)

    sessions = []
    seen = set()
    for _, h in htmls.items():
        for s in extract_sessions(h):
            k = (s["ci"], s["si"])
            if k not in seen:
                seen.add(k)
                sessions.append(s)

    for s in sessions:
        score(s, words, cinema, dtoken, None)

    hits = sorted((s for s in sessions
                   if s["_whits"] > 0 and s["_score"] >= max(10, (15 if cinema else 0))),
                  key=lambda x: -x["_score"])

    if a.json:
        print(json.dumps([{k: v for k, v in s.items() if k != "_score"} for s in hits], indent=2))
    elif hits:
        print(f"🎬 '{a.movie}'" + (f" @ {a.cinema or ''} {a.date or ''}" if (a.cinema or a.date) else "") +
              f" — {len(hits)} session(s):\n")
        for i, s in enumerate(hits, 1):
            print(f"  [{i}] ci={s['ci']} si={s['si']} {s.get('time','')}")
            print(f"      {s['ctx'][:150]}\n")
        print("Fill commands:")
        for s in hits:
            print(f"  bash ~/mcl-filler/vps-fill.sh {s['ci']} {s['si']} 8")
    else:
        print(json.dumps([]) if a.json else
              f"No sessions matched '{a.movie}'. Found {len(sessions)} total sessions "
              "(try --debug and fewer keywords).")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
