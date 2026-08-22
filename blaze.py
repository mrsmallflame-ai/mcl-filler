#!/usr/bin/env python3
"""BLAZE: pure-HTTP MCL booking client. No browser rendering.

Chain: GetPurchaseIFrameURL -> ticketing GET -> nonmember POST ->
tickettype POST -> SubmitSelectedSeat POST. ~1s per attempt.
"""
import asyncio, json, re, sys, time
import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

async def book_once(ci, si, seats, debug=False):
    """One full booking attempt with a fresh cookie jar. Returns (ok, detail)."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as c:
        c.headers.update({"User-Agent": UA,
                          "Accept-Language": "en-US,en;q=0.9"})

        # 0. prime session on the main site
        r = await c.get(f"https://www.mclcinema.com/MCLSelectSeat.aspx",
                        params={"visLang": "2", "ci": ci, "si": si},
                        headers={"Referer": "https://www.mclcinema.com/NowShowing.aspx?visLang=2"})
        if debug: print(f"  primed session: {r.status_code}")

        # 1. parse MovieSetId from the page, then get ticketing URL w/ Properties token
        mset = re.search(r'MovieSetId["\'=]+(\d+)', r.text) or re.search(r'V-(\d+)\.(?:jpg|png)', r.text)
        if not mset:
            return False, "no MovieSetId on page"
        r = await c.get("https://www.mclcinema.com/GetPurchaseIFrameURL.aspx",
                        params={"CinemaCodeID": ci, "FilmSessionId": si, "MovieSetId": mset.group(1), "Language": "en-US"},
                        headers={"Referer": f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={ci}&si={si}",
                                 "X-Requested-With": "XMLHttpRequest"})
        m = re.search(r'https://www4\.mclcinema\.com/MCL\.Front\.Ticketing\?[^"\']+', r.text)
        if not m:
            return False, f"no iframe url: {r.text[:120]}"
        turl = m.group(0).replace("&amp;", "&")

        # 2. GET ticketing entry page (sets www4 session)
        r = await c.get(turl)
        if r.status_code != 200:
            return False, f"entry {r.status_code}"
        # find the non-member form/button
        html = r.text

        # 3. POST non-member selection — inspect form fields
        forms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>(.*?)</form>', html, re.S)
        target, fields = None, {}
        for action, body in forms:
            if "nonMemberNextButton" in body or "MemberType" in action or "NonMember" in action:
                target = action
                for name, val in re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"', body):
                    fields[name] = val
                break
        if target is None:
            # fallback: look for any form post-ing onward
            if forms:
                target = forms[0][0]
                for name, val in re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"', forms[0][1]):
                    fields[name] = val
            else:
                return False, f"no form found; html head: {html[:200]}"

        import html as _h
        target = _h.unescape(target)

        if debug: print(f"  non-member form action={target[:80]} fields={list(fields)}")
        action_url = target if target.startswith("http") else f"https://www4.mclcinema.com{target}"
        r = await c.post(action_url, data=fields)
        if debug: print(f"  after nonmember POST: {r.url} ({r.status_code})")

        # 4. TicketType page → AJAX POST selectedValues (site-ticket-type.js behavior)
        html = r.text
        m_stt = re.search(r'var\s+submitTicketTypes\s*=\s*["\']([^"\']+)', html)
        if not m_stt:
            return False, "no submitTicketTypes endpoint"
        # parse first ticket select options
        sel = re.search(r'<select[^>]*>(.*?)</select>', html, re.S)
        if not sel:
            return False, "no ticket select"
        opt = None
        for om in re.finditer(r'<option[^>]*>', sel.group(1)):
            tag = om.group(0)
            code = re.search(r'code="([0-9A-Za-z]+)"', tag)
            val = re.search(r'value="(\d+)"', tag)
            name = re.search(r'ticketTypeName="([^"]*)"', tag)
            price = re.search(r'price="([\d.]+)"', tag)
            if code and val and val.group(1) == "6":
                import html as _h2
                opt = {"code": code.group(1), "qty": "6",
                       "name": _h2.unescape(name.group(1)) if name else "",
                       "price": int(float(price.group(1))) if price else 0}
                break
        if not opt:
            return False, "no qty-6 option found"
        total = opt["price"] * 6
        payload = {"selectedValues": json.dumps({
            "Tickets": [{"TicketTypeCode": opt["code"], "TicketTypeName": opt["name"],
                          "Quantity": 6, "Price": opt["price"]}],
            "Vouchers": [], "Concessions": [],
            "TotalBookingFee": 0, "TotalPrice": total,
            "TotalOccupySeatAmount": 6, "TotalOccupyTwoSeatAmount": 0})}
        stt_url = m_stt.group(1)
        stt_url = stt_url if stt_url.startswith("http") else f"https://www4.mclcinema.com{stt_url}"
        r = await c.post(stt_url, data=payload,
                         headers={"X-Requested-With": "XMLHttpRequest",
                                  "Referer": str(r.url)})
        if debug: print(f"  after SubmitSelectedTicketType: {r.status_code} {r.text[:100]}")

        # 5. POST the PickSeats form (antiforgery token only) — button was type=submit
        forms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>(.*?)</form>', html, re.S)
        target, tok = None, ""
        for a2, b2 in forms:
            if "/PickSeats" in a2:
                import html as _h3
                target = _h3.unescape(a2)
                tm = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]*)"', b2)
                tok = tm.group(1) if tm else ""
                break
        if not target:
            return False, "no PickSeats form"
        action_url = target if target.startswith("http") else f"https://www4.mclcinema.com{target}"
        r = await c.post(action_url, data={"__RequestVerificationToken": tok},
                         headers={"Referer": stt_url})
        pickseats_html = r.text
        if debug:
            n_seats = len(re.findall(r'seatnum="([A-Z]+\d+)"', pickseats_html))
            print(f"  PickSeats form POST: {r.status_code} | SubmitSeatPlan={'SubmitSeatPlan' in pickseats_html} | seat imgs={n_seats}")

        # 6. Submit seats
        data = {}
        for i, (sn, row, col) in enumerate(seats):
            data[f"selectedSeats[{i}][AreaCode]"] = "0000000001"
            data[f"selectedSeats[{i}][AreaNumber]"] = "1"
            data[f"selectedSeats[{i}][RowIndex]"] = str(row)
            data[f"selectedSeats[{i}][ColumnIndex]"] = str(col)
            data[f"selectedSeats[{i}][SeatName]"] = sn
        data["languageCulture"] = "en-US"
        data["platform"] = "DesktopWeb"
        r = await c.post("https://www4.mclcinema.com/MCL.Front.Ticketing/PickSeats/SubmitSelectedSeat",
                         data=data,
                         headers={"X-Requested-With": "XMLHttpRequest",
                                  "Referer": "https://www4.mclcinema.com/MCL.Front.Ticketing/PickSeats?language=en-US&source=DesktopWeb"})
        if debug: print(f"  seat submit status: {r.status_code} ct={r.headers.get('content-type','')[:40]} body={r.text[:150] if 'json' in r.headers.get('content-type','') else ''}")
        if r.status_code == 204:
            # success → click #pickSeatSubmitButton = submit its form to Payment
            forms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>(.*?)</form>', pickseats_html, re.S)
            for a3, b3 in forms:
                if "pickSeatSubmitButton" in b3:
                    import html as _h4
                    t3 = _h4.unescape(a3)
                    f3 = {}
                    for inp in re.findall(r'<input[^>]*>', b3):
                        nm = re.search(r'name="([^"]*)"', inp)
                        vl = re.search(r'value="([^"]*)"', inp)
                        if nm:
                            f3[_h4.unescape(nm.group(1))] = _h4.unescape(vl.group(1)) if vl else ""
                    u3 = t3 if t3.startswith("http") else f"https://www4.mclcinema.com{t3}"
                    r = await c.post(u3, data=f3)
                    if debug: print(f"  payment form POST: {r.status_code} -> {str(r.url)[:80]}")
                    if "Payment" in str(r.url) or "payment" in r.text[:3000].lower():
                        return True, f"PAYMENT reached ({str(r.url)[:60]})"
                    return False, f"post-payment unexpected: {str(r.url)[:80]}"
            return False, "no pickSeatSubmitButton form"
        try:
            j = r.json()
            if isinstance(j, list) and j and isinstance(j[0], dict):
                return False, f"{j[0].get('title','?')}: {j[0].get('content','')[:60]}"
            return False, f"unexpected json {str(j)[:100]}"
        except Exception:
            return False, f"non-json: {r.text[:120]}"

async def fetch_live_seats(ci, si, retries=5):
    """Fetch available seats via pure HTTP."""
    import asyncio as _a
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as c:
        c.headers.update({"User-Agent": UA})
        for attempt in range(retries):
            r = await c.get("https://info.mclcinema.com/RealSeatPlan/SeatPlan",
                            params={"cinemaCode": ci, "filmSessionId": si, "language": "en-US",
                                    "seatCount": 6, "twoSeatCount": 0},
                            headers={"Referer": f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={ci}&si={si}"})
            if "server busy" not in r.text.lower():
                seats = []
                for m in re.finditer(r'<img[^>]*seatnum="([A-Z]+\d+)"[^>]*>', r.text):
                    tag = m.group(0)
                    if 'status="Normal"' not in tag and "status='Normal'" not in tag:
                        continue
                    row = re.search(r'\srow="(\d+)"', tag)
                    col = re.search(r'\scolumn="(\d+)"', tag)
                    if row and col:
                        seats.append((m.group(1), row.group(1), col.group(1)))
                return seats
            print(f"  busy (attempt {attempt+1}/{retries}), backing off...")
            await _a.sleep(4 * attempt + 2)
        return None

async def main():
    import sys, time as _t
    ci = sys.argv[1] if len(sys.argv) > 1 else "017"
    si = sys.argv[2] if len(sys.argv) > 2 else "127646"
    debug = "--debug" in sys.argv

    print("fetching live seats...")
    seats = await fetch_live_seats(ci, si)
    if seats is None:
        print("server busy on seat plan")
        return
    print(f"{len(seats)} normal seats; taking first 6: {seats[:6]}")

    t0 = _t.time()
    ok, detail = await book_once(ci, si, seats[:6], debug=debug)
    dt = _t.time() - t0
    print(f"\n{'✅' if ok else '❌'} in {dt:.2f}s | {detail}")

asyncio.run(main())