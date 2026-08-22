#!/usr/bin/env python3
"""Find upcoming MCL sessions via pure HTTP."""
import asyncio, re, sys
import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

async def main():
    want_ci = sys.argv[1] if len(sys.argv) > 1 else None
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as c:
        c.headers.update({"User-Agent": UA})
        r = await c.get("https://www.mclcinema.com/NowShowing.aspx", params={"visLang": "2"})
        # list view link -> click through
        m = re.search(r'href="([^"]*TicketingByDate[^"]*|[^"]*List[^"]*)"', r.text)
        # try known list view URL patterns
        for url in ["https://www.mclcinema.com/TicketingByDateCinema.aspx?visLang=2",
                    "https://www.mclcinema.com/NowShowing.aspx?visLang=2&mode=list"]:
            r2 = await c.get(url)
            if r2.status_code == 200 and "si=" in r2.text:
                r = r2
                break
        seen = []
        for mm in re.finditer(r'MCLSelectSeat\.aspx\?visLang=2&(?:amp;)?ci=(\d+)&(?:amp;)?si=(\d+)', r.text):
            ci, si = mm.group(1), mm.group(2)
            if (ci, si) not in seen:
                seen.append((ci, si))
        # grab context around each link for date/time
        out = []
        for ci, si in seen[:60]:
            idx = r.text.find(f"ci={ci}&si={si}")
            ctx = re.sub(r'<[^>]+>', ' ', r.text[max(0,idx-400):idx+100])
            ctx = re.sub(r'\s+', ' ', ctx).strip()
            out.append((ci, si, ctx[-160:]))
        for ci, si, ctx in out:
            if want_ci and ci != want_ci:
                continue
            print(f"ci={ci} si={si} | {ctx}")

asyncio.run(main())