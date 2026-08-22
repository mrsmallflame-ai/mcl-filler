#!/usr/bin/env python3
"""
MCL Cinema Rapid Seat Filler.

Usage:
  python3 mcl_filler.py --ci 021 --si 37011          # fill a session
  python3 mcl_filler.py --ci 021 --discover            # list sessions
  python3 mcl_filler.py --url "https://m.mclcinema.com/..."  # paste mobile URL
"""

import asyncio, json, sys, time, re, argparse
from playwright.async_api import async_playwright

CINEMA_CODES = {"THE ONE":"021","CITYGATE":"018","MOVIE TOWN":"014",
    "K11 ART HOUSE":"002","GRAND WINDSOR":"003","STAR":"004"}
CINEMA_NAMES = {v:k for k,v in CINEMA_CODES.items()}

def make_seat_objects(batch):
    return [{"AreaCode":"0000000001","AreaNumber":"1",
             "RowIndex":str(ri),"ColumnIndex":str(ci),"SeatName":sn}
            for sn,ri,ci in batch]

async def sleep_ms(n): await asyncio.sleep(n/1000)

# ── Session Discovery ─────────────────────────────────────────────────────

async def discover_sessions(page, ci):
    await page.goto("https://www.mclcinema.com/NowShowing.aspx?visLang=2",
                    wait_until="domcontentloaded", timeout=30000)
    await sleep_ms(2000)
    try:
        await page.click("a:has-text('By date'), a:has-text('date & Cinema')", timeout=3000)
        await sleep_ms(3000)
    except: pass
    return json.loads(await page.evaluate(f"""
        (function() {{
            var links = document.querySelectorAll('a[href*="ci={ci}"][href*="si="]');
            var result = [], seen = {{}};
            links.forEach(function(a) {{
                var href = a.getAttribute('href') || '';
                var m = href.match(/si=(\\d+)/);
                if (m && !seen[m[1]]) {{
                    seen[m[1]] = true;
                    var ctx = '', p = a.parentElement;
                    for (var i=0; i<5 && p; i++) {{
                        ctx = (p.textContent||'').trim().substring(0,100) + ' | ' + ctx;
                        p = p.parentElement;
                    }}
                    result.push({{si:m[1], context:ctx.substring(0,150)}});
                }}
            }});
            return JSON.stringify(result);
        }})()
    """))

# ── Core Booking Flow ─────────────────────────────────────────────────────

async def book_batch(browser, ci, si, batch_num, batch, showtime_text, label="S"):
    seats_str = ", ".join(s[0] for s in batch)
    ctx = None
    try:
        ctx = await browser.new_context(
            viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()

        await page.goto(f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={ci}&si={si}",
                        wait_until="domcontentloaded", timeout=30000)
        await sleep_ms(1500)
        if "Index.aspx" in page.url:
            print(f"[{label}][B{batch_num}] ⚠️ session expired", flush=True)
            return False

        clicked = False
        for _ in range(3):
            clicked = await page.evaluate(f"""
                (function() {{
                    var links = document.querySelectorAll('a');
                    for (var i=0; i<links.length; i++) {{
                        var t = links[i].textContent.trim();
                        if (t.indexOf('{showtime_text}')>=0 && t.match(/\\d/)) {{
                            var d = document.querySelectorAll('.dialog-container,.modal,.popup');
                            d.forEach(function(x){{x.style.display='none';}});
                            links[i].click(); return true;
                        }}
                    }}
                    return false;
                }})()
            """)
            if clicked: break
            await sleep_ms(800)
        if not clicked:
            print(f"[{label}][B{batch_num}] ❌ showtime '{showtime_text}' not found", flush=True)
            return False
        await sleep_ms(1500)

        src = await page.evaluate("(function(){var f=document.querySelector('iframe');return f?f.src:'';})()")
        if not src:
            print(f"[{label}][B{batch_num}] ❌ no iframe", flush=True)
            return False

        await page.goto(src, wait_until="domcontentloaded", timeout=30000)
        await sleep_ms(1500)

        for _ in range(3):
            try:
                async with page.expect_navigation(timeout=5000):
                    await page.evaluate("document.getElementById('nonMemberNextButton')?.click()")
                break
            except:
                await sleep_ms(1000)
        if "TicketType" not in page.url:
            print(f"[{label}][B{batch_num}] ❌ non-member failed ({page.url[:50]})", flush=True)
            return False

        for _ in range(3):
            try:
                async with page.expect_navigation(timeout=5000):
                    await page.evaluate("""
                        document.querySelector('select[id="inputGroupSelectTicket"]').value='6';
                        document.querySelector('select[id="inputGroupSelectTicket"]')
                            .dispatchEvent(new Event('change',{bubbles:true}));
                        document.querySelector('input[tickettypesubmit]').disabled=false;
                        document.querySelector('form').submit();
                    """)
                break
            except:
                await sleep_ms(1000)
        if "PickSeats" not in page.url and "Payment" not in page.url:
            print(f"[{label}][B{batch_num}] ❌ ticket submit failed", flush=True)
            return False
        if "Payment" in page.url:
            print(f"[{label}][B{batch_num}] ✅ Payment ({seats_str})", flush=True)
            return True

        sj = json.dumps(make_seat_objects(batch))
        for _ in range(3):
            has_fn = await page.evaluate("typeof SubmitSeatPlan === 'function'")
            if not has_fn:
                print(f"[{label}][B{batch_num}] ⚠️ no SubmitSeatPlan fn", flush=True)
                # Try direct form submission
                await page.evaluate("""
                    (function() {
                        var btn = document.getElementById('pickSeatSubmitButton');
                        if (btn) { btn.click(); return; }
                        var f = document.querySelector('form');
                        if (f && f.action && f.action.indexOf('Payment')>=0) { f.submit(); }
                    })()
                """)
                await sleep_ms(2000)
                if "Payment" in page.url:
                    print(f"[{label}][B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                    return True
                break

            await page.evaluate(f"""
                SubmitSeatPlan({{selectedSeats:{sj},languageCulture:'en-US',platform:'DesktopWeb'}});
            """)
            await sleep_ms(3000)

            if "Payment" in page.url:
                print(f"[{label}][B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                return True

            # Close any popups that might be blocking
            closed = await page.evaluate("""
                (function() {
                    var count = 0;
                    try { if (typeof acceptWheelchairSelect === 'function') { acceptWheelchairSelect(); count += 10; } } catch(e) {}
                    for (var i = 300; i <= 350; i++) {
                        try { CloseMessage(String(i)); count++; } catch(e) {}
                    }
                    var sel = '.dialog-container, .modal, .popup, [class*="dialog"], [class*="modal"], [class*="popup"], .ui-dialog, .msgbox, .messagebox, .overlay, .ui-widget-overlay, .blockUI';
                    document.querySelectorAll(sel).forEach(function(d) { d.style.display = 'none'; count++; });
                    document.querySelectorAll('button, input[type="button"], a').forEach(function(b) {
                        var t = (b.textContent || b.value || '').trim().toLowerCase();
                        if (['ok','close','confirm','continue','yes','accept'].includes(t)) { b.click(); count++; }
                    });
                    return count;
                })()
            """)
            if closed > 0:
                print(f"[{label}][B{batch_num}] ⚠️ closed {closed} popups", flush=True)
                await sleep_ms(1000)
                # Retry SubmitSeatPlan after closing popups
                await page.evaluate(f"""
                    SubmitSeatPlan({{selectedSeats:{sj},languageCulture:'en-US',platform:'DesktopWeb'}});
                """)
                await sleep_ms(2500)
                if "Payment" in page.url:
                    print(f"[{label}][B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                    return True

            # Try clicking the submit button
            await page.evaluate("document.getElementById('pickSeatSubmitButton')?.click()")
            await sleep_ms(2000)
            if "Payment" in page.url:
                print(f"[{label}][B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                return True

            # Try direct form submission
            await page.evaluate("""
                (function() {
                    var f = document.querySelector('form');
                    if (f && f.action && f.action.indexOf('Payment')>=0) { f.submit(); }
                })()
            """)
            await sleep_ms(2000)
            if "Payment" in page.url:
                print(f"[{label}][B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                return True

        print(f"[{label}][B{batch_num}] ❌ {seats_str}", flush=True)
        return False
    except Exception as e:
        print(f"[{label}][B{batch_num}] 💥 {e}", flush=True)
        return False
    finally:
        if ctx:
            try: await ctx.close()
            except: pass

# ── Dynamic Seat Plan ─────────────────────────────────────────────────────

SEAT_PLAN_URL = "https://info.mclcinema.com/RealSeatPlan/SeatPlan?cinemaCode={ci}&filmSessionId={si}&language=en-US"

async def fetch_seat_plan(page, ci, si, max_attempts=6):
    """Fetch the authoritative seat map and return every available Normal seat.
    MCL intermittently serves a 'server busy' page — retry with backoff."""
    import random
    for attempt in range(1, max_attempts + 1):
        await page.goto(
            SEAT_PLAN_URL.format(ci=ci, si=si),
            wait_until="domcontentloaded",
            timeout=30000,
            referer=f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={ci}&si={si}",
        )
        # wait until seat imgs render or the busy message shows
        for _ in range(8):
            await sleep_ms(1000)
            n = await page.evaluate("document.querySelectorAll('img[seatnum]').length")
            if n > 0:
                break
        raw = await page.evaluate("""
            (function() {
                var result = [];
                document.querySelectorAll('img[seatnum]').forEach(function(img) {
                    if ((img.getAttribute('status') || '') !== 'Normal') return;
                    result.push({
                        seatname: img.getAttribute('seatnum') || '',
                        row: img.getAttribute('rowindex') || img.getAttribute('row'),
                        column: img.getAttribute('columnindex') || img.getAttribute('column')
                    });
                });
                return JSON.stringify(result);
            })()
        """)
        seats = json.loads(raw)
        if seats:
            return [
                (seat["seatname"], int(seat["row"]), int(seat["column"]))
                for seat in seats
                if seat["seatname"] and seat.get("row") is not None and seat.get("column") is not None
            ]
        # empty → either genuinely full house or the busy page; distinguish
        busy = await page.evaluate("document.body.innerHTML.includes('server busy')")
        if not busy:
            return []   # rendered fine but no Normal seats = full house
        print(f"    [seatplan] server busy (attempt {attempt}/{max_attempts}), backing off...", flush=True)
        await asyncio.sleep(3 * attempt + random.random() * 2)
    return []

def batches_of_six(seats):
    """Build only full six-seat groups; the booking flow requests exactly six tickets."""
    return [seats[i:i + 6] for i in range(0, len(seats), 6) if len(seats[i:i + 6]) == 6]

def parse_mcl_url(url):
    """Extract cinema and session IDs from desktop, mobile, and RealSeatPlan links."""
    lowered = url.lower()
    ci_patterns = (
        r'(?:^|[?&#])cinemacodeid=(\d+)',
        r'(?:^|[?&#])cinemacode=(\d+)',
        r'(?:^|[?&#])ci=(\d+)',
        r'/ci(?:ne)?[=/](\d+)',
    )
    si_patterns = (
        r'(?:^|[?&#])sessionid=(\d+)',
        r'(?:^|[?&#])filmsessionid=(\d+)',
        r'(?:^|[?&#])si=(\d+)',
        r'/si(?:ssion)?[=/](\d+)',
    )
    ci = si = None
    for pattern in ci_patterns:
        match = re.search(pattern, lowered, re.I)
        if match:
            ci = match.group(1)
            break
    for pattern in si_patterns:
        match = re.search(pattern, lowered, re.I)
        if match:
            si = match.group(1)
            break
    return ci, si

# ── Parallel Orchestration ────────────────────────────────────────────────

async def run_worker(worker_id, browser, ci, si, showtime_text, batches, parallel_count):
    label = f"W{worker_id}"
    assigned = [(number, batch) for number, batch in enumerate(batches, 1)
                if (number - 1) % parallel_count == worker_id - 1]
    ok = fail = 0
    for number, batch in assigned:
        seats_str = ", ".join(seat[0] for seat in batch)
        print(f"[{label}] Batch {number}: {seats_str}", flush=True)
        success = await book_batch(browser, ci, si, number, batch, showtime_text, label)
        if success:
            ok += 1
        else:
            fail += 1
        print(f"[{label}] Batch {number} {'✅' if success else '❌'} ({ok} ok, {fail} failed)", flush=True)
        await sleep_ms(500)
    return ok, fail

# ── Showtime Detection ────────────────────────────────────────────────────

async def detect_showtime(browser, ci, si):
    ctx = await browser.new_context()
    page = await ctx.new_page()
    try:
        await page.goto(
            f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={ci}&si={si}",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await sleep_ms(2000)
        if "Index.aspx" in page.url:
            return "10:35AM"
        return await page.evaluate("""
            (function() {
                var links = document.querySelectorAll('a');
                for (var i = 0; i < links.length; i++) {
                    var t = links[i].textContent.trim();
                    if (t.match(/^\\d{1,2}:\\d{2}[AP]M$/)) return t;
                }
                return '10:35AM';
            })()
        """)
    finally:
        await ctx.close()

# ── CLI ───────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", help="Cinema code")
    parser.add_argument("--si", help="Session ID")
    parser.add_argument("--url", help="Any MCL desktop, mobile, or RealSeatPlan URL")
    parser.add_argument("--house", type=int, help="Deprecated; house layout is auto-detected")
    parser.add_argument("--cinema", choices=list(CINEMA_CODES.keys()), help="Cinema name")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--batch-start", type=int, default=1, help="First dynamic batch (1-indexed)")
    parser.add_argument("--batch-end", type=int, help="Last dynamic batch (default: all)")
    parser.add_argument("--parallel", type=int, default=3, help="Number of Chromium workers")
    parser.add_argument("--brim", action="store_true", help="Legacy no-op; brimming is now enabled by default")
    parser.add_argument("--no-brim", dest="no_brim", action="store_true", help="Disable the default brim loop")
    args = parser.parse_args()

    if args.parallel < 1:
        raise SystemExit("--parallel must be at least 1")
    if args.url:
        url_ci, url_si = parse_mcl_url(args.url)
        if url_ci:
            args.ci = url_ci
        if url_si:
            args.si = url_si
        print(f"  Parsed URL: ci={args.ci}, si={args.si}")

    ci = args.ci or CINEMA_CODES.get(args.cinema or "")
    si = args.si
    if not ci or not si:
        print("Specify --url <MCL URL> (or both --ci <code> and --si <session ID>)")
        return

    async with async_playwright() as pw:
        detection_browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        STEALTH_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

        async def stealth_ctx():
            return await detection_browser.new_context(user_agent=STEALTH_UA)

        if args.discover:
            ctx = await stealth_ctx()
            page = await ctx.new_page()
            sessions = await discover_sessions(page, ci)
            print(f"\n📋 {len(sessions)} session(s):")
            for session in sessions[:20]:
                print(f"  si={session['si']}  {session['context'][:80]}")
            await ctx.close()
            await detection_browser.close()
            return

        try:
            ctx = await stealth_ctx()
            page = await ctx.new_page()
            initial_seats = await fetch_seat_plan(page, ci, si)
            await ctx.close()
            if not initial_seats:
                print("❌ No available Normal seats found in the live seat plan")
                return

            batches = batches_of_six(initial_seats)
            bs = max(0, args.batch_start - 1)
            be = args.batch_end or len(batches)
            selected_batches = batches[bs:be]
            if not selected_batches:
                print("❌ The requested batch range contains no complete six-seat batches")
                return

            showtime_text = await detect_showtime(detection_browser, ci, si)
            print(f"  Seat plan: {len(initial_seats)} Normal seats / {len(batches)} batches of 6")
            print(f"  Running batches {bs + 1}-{min(be, len(batches))} ({len(selected_batches)} batches)")
            print(f"  Parallel workers: {args.parallel}")
            print(f"  Showtime: {showtime_text}")
            print(f"  Brim: {'disabled' if args.no_brim else 'enabled'}")

            browsers = []
            for _ in range(args.parallel):
                browsers.append(await pw.chromium.launch(
                    headless=args.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                ))

            tasks = [
                asyncio.create_task(run_worker(
                    worker_id, browser, ci, si, showtime_text,
                    selected_batches, args.parallel
                ))
                for worker_id, browser in enumerate(browsers[:args.parallel], 1)
            ]
            results = await asyncio.gather(*tasks)
            total_ok = sum(result[0] for result in results)
            total_fail = sum(result[1] for result in results)
            print(f"\n▶ Initial run: {total_ok} batches succeeded, {total_fail} failed")

            if not args.no_brim:
                zero_success_rounds = 0
                brim_ok_total = 0
                round_number = 0
                while zero_success_rounds < 2:
                    round_number += 1
                    ctx = await stealth_ctx()
                    page = await ctx.new_page()
                    remaining_seats = await fetch_seat_plan(page, ci, si)
                    await ctx.close()

                    if not remaining_seats:
                        print("BRIM: theatre is full")
                        break

                    brim_batches = batches_of_six(remaining_seats)
                    print(f"BRIM round {round_number}: {len(remaining_seats)} seats / "
                          f"{len(brim_batches)} fresh batches")
                    if not brim_batches:
                        print("BRIM: fewer than six seats remain; cannot build a booking batch")
                        zero_success_rounds += 1
                        continue

                    tasks = [
                        asyncio.create_task(run_worker(
                            worker_id, browser, ci, si, showtime_text,
                            brim_batches, args.parallel
                        ))
                        for worker_id, browser in enumerate(browsers[:args.parallel], 1)
                    ]
                    results = await asyncio.gather(*tasks)
                    round_ok = sum(result[0] for result in results)
                    round_fail = sum(result[1] for result in results)
                    brim_ok_total += round_ok
                    print(f"BRIM round {round_number}: {round_ok} succeeded, {round_fail} failed")
                    zero_success_rounds = 0 if round_ok else zero_success_rounds + 1

                if brim_ok_total:
                    print(f"BRIM total: {brim_ok_total} additional batches filled")

        finally:
            for browser in locals().get("browsers", []):
                try:
                    await browser.close()
                except Exception:
                    pass
            await detection_browser.close()

if __name__ == "__main__":
    asyncio.run(main())
