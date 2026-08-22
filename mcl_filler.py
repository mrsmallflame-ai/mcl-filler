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

# ── Pre-computed Seat Batches ──────────────────────────────────────────────

# THE ONE House 5 (ci=021) — 16 batches, 96 normal seats
# RowIndex: A=10 B=9 C=8 D=7 E=6 F=5 G=4 H=3 I=2 J=1
# Right cols 7-14, Left cols 1-4, Aisle cols 5-6
BATCHES_H5 = [
    [("C5",8,7),("C6",8,8),("C8",8,10),("C10",8,12),("C12",8,14),("C4",8,4)],
    [("B5",9,7),("B6",9,8),("B8",9,10),("B10",9,12),("B12",9,14),("B2",9,2)],
    [("J3",1,9),("J4",1,10),("J5",1,11),("J6",1,12),("J7",1,13),("J8",1,14)],
    [("G7",4,10),("G8",4,11),("G9",4,12),("G10",4,13),("G11",4,14),("G3",4,4)],
    [("D5",7,7),("D6",7,8),("D7",7,9),("D8",7,10),("D9",7,11),("D10",7,12)],
    [("A5",10,9),("A6",10,10),("A7",10,11),("A8",10,12),("A9",10,13),("A10",10,14)],
    [("F6",5,9),("F7",5,10),("F8",5,11),("F9",5,12),("F10",5,13),("F11",5,14)],
    [("H8",3,11),("H9",3,12),("H10",3,13),("H11",3,14),("H3",3,4),("H1",3,2)],
    [("D1",7,1),("D2",7,2),("D3",7,3),("D4",7,4),("D11",7,13),("D12",7,14)],
    [("E4",6,7),("E5",6,8),("E6",6,9),("E7",6,10),("E9",6,12),("E11",6,14)],
    [("C2",8,2),("C3",8,3),("C7",8,9),("C9",8,11),("C11",8,13),("G2",4,3)],
    [("B1",9,1),("B3",9,3),("B4",9,4),("B7",9,9),("B9",9,11),("B11",9,13)],
    [("A1",10,1),("A2",10,2),("A3",10,3),("A4",10,4),("I4",2,7),("I5",2,8)],
    [("I6",2,9),("I7",2,10),("I8",2,11),("I9",2,12),("I10",2,13),("I11",2,14)],
    [("F1",5,2),("F2",5,3),("F3",5,4),("E1",6,2),("E2",6,3),("E3",6,4)],
    [("H2",3,3),("E8",6,11),("E10",6,13),("J1",1,7),("J2",1,8),("G1",4,2)],
]

# K11 ART HOUSE House 7 (mobile code 017, H7) — 14 batches, 84 normal seats
# RowIndex: A=7 B=6 C=5 D=4 E=3 F=2 G=1
# Right cols 11-5, Left cols 16-15, Aisle cols 14-12
BATCHES_H7 = [
    [("C5",5,11),("C6",5,10),("C7",5,9),("C8",5,8),("C9",5,7),("C10",5,6)],
    [("C1",5,16),("C2",5,15),("C11",5,5),("C12",5,4),("C13",5,3),("C14",5,2)],
    [("D5",4,11),("D6",4,10),("D7",4,9),("D8",4,8),("D9",4,7),("D10",4,6)],
    [("D1",4,16),("D2",4,15),("D11",4,5),("D12",4,4),("D13",4,3),("D14",4,2)],
    [("E5",3,11),("E6",3,10),("E7",3,9),("E8",3,8),("E9",3,7),("E10",3,6)],
    [("E1",3,16),("E2",3,15),("E11",3,5),("E12",3,4),("E13",3,3),("E14",3,2)],
    [("B5",6,11),("B6",6,10),("B7",6,9),("B8",6,8),("B9",6,7),("B10",6,6)],
    [("B1",6,16),("B2",6,15),("B11",6,5),("B12",6,4),("B13",6,3),("B14",6,2)],
    [("F5",2,11),("F9",2,7),("F10",2,6),("F11",2,5),("F12",2,4),("F13",2,3)],
    [("A5",7,11),("A6",7,10),("A7",7,9),("A8",7,8),("A9",7,7),("A10",7,6)],
    [("A1",7,16),("A2",7,15),("A13",7,3),("A14",7,2),("G5",1,11),("G6",1,10)],
    [("G1",1,15),("G2",1,14),("G3",1,13),("G4",1,12),("G7",1,9),("G8",1,8)],
    [("G9",1,7),("G10",1,6),("G11",1,5),("G12",1,4),("G13",1,3),("G14",1,2)],
    [("F1",2,16),("F2",2,15),("F14",2,2),("F15",2,1),("F1",2,16),("F2",2,15)],
]

# K11 ART HOUSE House 8 (mobile code 017, H8) — 159 seats, 155 normal
# RowIndex: A=10 B=9 C=8 D=7 E=6 F=5 G=4 H=3 J=2 K=1
# Each row B-J: left cols 19-16 (A4-A7), gap cols 15-13, right cols 12-1 (A11-A22)
# Row A has 14 seats, Row K has 17 seats
def make_h8_batches():
    rows_bj = ["B","C","D","E","F","G","H","J"]
    bj_ri = {"B":9,"C":8,"D":7,"E":6,"F":5,"G":4,"H":3,"J":2}
    batches = []
    # Right side of each row B-J: cols 12-1 = 12 seats (B11-B22)
    for row in rows_bj:
        ri = bj_ri[row]
        # Right side in 6-seat chunks: cols 12-7, 6-1
        batches.append([(f"{row}11",ri,12),(f"{row}12",ri,11),(f"{row}13",ri,10),
                        (f"{row}14",ri,9),(f"{row}15",ri,8),(f"{row}16",ri,7)])
        batches.append([(f"{row}17",ri,6),(f"{row}18",ri,5),(f"{row}19",ri,4),
                        (f"{row}20",ri,3),(f"{row}21",ri,2),(f"{row}22",ri,1)])
        # Left side: cols 19-16 = 4 seats (B4-B7) — combine with next row's left
    # Left sides in pairs (4+4=8 seats → pack into 6+2 batches with right side extras)
    for i in range(0, len(rows_bj), 2):
        r1, r2 = rows_bj[i], rows_bj[i+1]
        ri1, ri2 = bj_ri[r1], bj_ri[r2]
        batches.append([(f"{r1}4",ri1,19),(f"{r1}5",ri1,18),(f"{r1}6",ri1,17),
                        (f"{r1}7",ri1,16),(f"{r2}4",ri2,19),(f"{r2}5",ri2,18)])
        batches.append([(f"{r2}6",ri2,17),(f"{r2}7",ri2,16),
                        # Pad with extra right side seats
                        (f"{r1}11",ri1,12),(f"{r1}12",ri1,11),(f"{r1}13",ri1,10),(f"{r1}14",ri1,9)])
    # Row A (ri=10): A4(19),A5(18),A6(17),A7(16),A11(12)...A20(3) — 14 seats
    batches.append([("A4",10,19),("A5",10,18),("A6",10,17),("A7",10,16),("A11",10,12),("A12",10,11)])
    batches.append([("A13",10,10),("A14",10,9),("A15",10,8),("A16",10,7),("A17",10,6),("A18",10,5)])
    batches.append([("A19",10,4),("A20",10,3),("B4",9,19),("B5",9,18),("B6",9,17),("B7",9,16)])
    # Row K (ri=1): K5(18)...K21(2) — 17 seats
    batches.append([("K5",1,18),("K6",1,17),("K7",1,16),("K8",1,15),("K9",1,14),("K10",1,13)])
    batches.append([("K11",1,12),("K12",1,11),("K13",1,10),("K14",1,9),("K15",1,8),("K16",1,7)])
    batches.append([("K17",1,6),("K18",1,5),("K19",1,4),("K20",1,3),("K21",1,2),("B11",9,12)])
    return batches

# GRAND WINDSOR House 1 (ci=019) — 170 normal seats, 1 wheelchair
# RowIndex: A=12 B=11 C=10 D=9 E=8 F=7 G=6 H=5 J=4 K=3 L=2 M=1
# 3 sections per row: right(cols 20-18), middle(cols 16-7), left(cols 5-1)
# Aisle gaps at col 17 and col 6
BATCHES_H1 = []
def make_h1():
    rows = {"D":9,"E":8,"F":7,"G":6,"H":5}
    for row, ri in rows.items():
        # Middle section: 16,15,14,13,12,11,10,9,8,7 = 10 seats
        BATCHES_H1.append([(f"{row}7",ri,13),(f"{row}8",ri,12),(f"{row}9",ri,11),
                           (f"{row}10",ri,10),(f"{row}11",ri,9),(f"{row}12",ri,8)])
        BATCHES_H1.append([(f"{row}13",ri,7),(f"{row}14",ri,5),(f"{row}15",ri,4),
                           (f"{row}16",ri,3),(f"{row}17",ri,2),(f"{row}18",ri,1)])
        # Right side: 20,19,18 = 3 seats + left side: 5,4,3,2,1 = 5 seats
        BATCHES_H1.append([(f"{row}1",ri,20),(f"{row}2",ri,19),(f"{row}3",ri,18),
                           (f"{row}4",ri,16),(f"{row}5",ri,15),(f"{row}6",ri,14)])
    # Row C (ri=10): C1-C18 = 18 seats, same pattern
    for row, ri in [("C",10)]:
        BATCHES_H1.append([("C1",10,20),("C2",10,19),("C3",10,18),("C4",10,16),("C5",10,15),("C6",10,14)])
        BATCHES_H1.append([("C7",10,13),("C8",10,12),("C9",10,11),("C10",10,10),("C11",10,9),("C12",10,8)])
        BATCHES_H1.append([("C13",10,7),("C14",10,5),("C15",10,4),("C16",10,3),("C17",10,2),("C18",10,1)])
    # Row B (ri=11): B1-B16, B17 wheelchair
    BATCHES_H1.append([("B1",11,20),("B2",11,19),("B3",11,18),("B4",11,16),("B5",11,15),("B6",11,14)])
    BATCHES_H1.append([("B7",11,13),("B8",11,12),("B9",11,11),("B10",11,10),("B11",11,9),("B12",11,8)])
    BATCHES_H1.append([("B13",11,7),("B14",11,5),("B15",11,4),("B16",11,3),("J1",4,20),("J2",4,19)])
    # Row J (ri=4): J1-J17
    BATCHES_H1.append([("J3",4,18),("J4",4,16),("J5",4,15),("J6",4,14),("J7",4,13),("J8",4,12)])
    BATCHES_H1.append([("J9",4,11),("J10",4,10),("J11",4,9),("J12",4,8),("J14",4,5),("J15",4,4)])
    BATCHES_H1.append([("J16",4,3),("J17",4,2),("K1",3,20),("K2",3,19),("K3",3,18),("K14",3,5)])
    # Row K (ri=3): K1-K3, K14-K17
    BATCHES_H1.append([("K15",3,4),("K16",3,3),("K17",3,2),("L1",2,20),("L2",2,19),("L3",2,18)])
    # Row L (ri=2): L1-L3, L14-L17
    BATCHES_H1.append([("L14",2,5),("L15",2,4),("L16",2,3),("L17",2,2),("M1",1,20),("M2",1,19)])
    # Row A (ri=12): A2-A15
    BATCHES_H1.append([("A2",12,19),("A3",12,18),("A4",12,16),("A5",12,15),("A6",12,14),("A7",12,13)])
    BATCHES_H1.append([("A8",12,12),("A9",12,11),("A10",12,10),("A11",12,9),("A12",12,8),("A13",12,7)])
    BATCHES_H1.append([("A14",12,5),("A15",12,4),("D4",9,16),("D5",9,15),("D6",9,14),("D7",9,13)])
make_h1()

BATCHES = {
    "021": BATCHES_H5,       # THE ONE House 5
    "017": BATCHES_H7,       # K11 House 7 (mobile code 017)
    "017_H8": make_h8_batches(),  # K11 House 8
    "019": BATCHES_H1,       # GRAND WINDSOR House 1
}

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

async def book_batch(browser, ci, si, batch_num, batch, showtime_text):
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
            print(f"  [B{batch_num}] ⚠️ session expired", flush=True)
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
            print(f"  [B{batch_num}] ❌ showtime '{showtime_text}' not found", flush=True)
            return False
        await sleep_ms(1500)

        src = await page.evaluate("(function(){var f=document.querySelector('iframe');return f?f.src:'';})()")
        if not src:
            print(f"  [B{batch_num}] ❌ no iframe", flush=True)
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
            print(f"  [B{batch_num}] ❌ non-member failed ({page.url[:50]})", flush=True)
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
            print(f"  [B{batch_num}] ❌ ticket submit failed", flush=True)
            return False
        if "Payment" in page.url:
            print(f"  [B{batch_num}] ✅ Payment ({seats_str})", flush=True)
            return True

        sj = json.dumps(make_seat_objects(batch))
        for _ in range(3):
            has_fn = await page.evaluate("typeof SubmitSeatPlan === 'function'")
            if not has_fn:
                print(f"  [B{batch_num}] ⚠️ no SubmitSeatPlan fn", flush=True)
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
                    print(f"  [B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                    return True
                break

            await page.evaluate(f"""
                SubmitSeatPlan({{selectedSeats:{sj},languageCulture:'en-US',platform:'DesktopWeb'}});
            """)
            await sleep_ms(3000)

            if "Payment" in page.url:
                print(f"  [B{batch_num}] ✅ Payment ({seats_str})", flush=True)
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
                print(f"  [B{batch_num}] ⚠️ closed {closed} popups", flush=True)
                await sleep_ms(1000)
                # Retry SubmitSeatPlan after closing popups
                await page.evaluate(f"""
                    SubmitSeatPlan({{selectedSeats:{sj},languageCulture:'en-US',platform:'DesktopWeb'}});
                """)
                await sleep_ms(2500)
                if "Payment" in page.url:
                    print(f"  [B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                    return True

            # Try clicking the submit button
            await page.evaluate("document.getElementById('pickSeatSubmitButton')?.click()")
            await sleep_ms(2000)
            if "Payment" in page.url:
                print(f"  [B{batch_num}] ✅ Payment ({seats_str})", flush=True)
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
                print(f"  [B{batch_num}] ✅ Payment ({seats_str})", flush=True)
                return True

        print(f"  [B{batch_num}] ❌ {seats_str}", flush=True)
        return False
    except Exception as e:
        print(f"  [B{batch_num}] 💥 {e}", flush=True)
        return False
    finally:
        if ctx:
            try: await ctx.close()
            except: pass

async def fill_session(browser, ci, si, showtime_text, batches, label):
    ok = fail = 0
    for i, batch in enumerate(batches, 1):
        seats_str = ", ".join(s[0] for s in batch)
        print(f"  [{label}] Batch {i}: {seats_str}", flush=True)
        r = await book_batch(browser, ci, si, i, batch, showtime_text)
        if r: ok += 1
        else: fail += 1
        await sleep_ms(500)
    return ok, fail

# ── CLI ───────────────────────────────────────────────────────────────────

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ci", help="Cinema code")
    p.add_argument("--si", help="Session ID")
    p.add_argument("--url", help="Mobile URL")
    p.add_argument("--house", type=int, help="House number")
    p.add_argument("--cinema", choices=list(CINEMA_CODES.keys()), help="Cinema name")
    p.add_argument("--discover", action="store_true")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--batch-start", type=int, default=1, help="First batch (1-indexed)")
    p.add_argument("--batch-end", type=int, help="Last batch (default: all)")
    p.add_argument("--brim", action="store_true", help="After initial run, check seat plan and fill remaining empty seats")
    args = p.parse_args()

    if args.url:
        import re as _re
        ci_m = _re.search(r'cinemaCodeID=(\d+)', args.url)
        si_m = _re.search(r'sessionID=(\d+)', args.url)
        if ci_m: args.ci = ci_m.group(1)
        if si_m: args.si = si_m.group(1)
        print(f"  Parsed: ci={args.ci}, si={args.si}")

    ci = args.ci or CINEMA_CODES.get(args.cinema or "")
    if not ci:
        print(f"Cinemas: {', '.join(CINEMA_CODES.keys())}")
        return

    batch_key = ci
    if args.house == 8:
        batch_key = "017_H8"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=args.headless or True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        if args.discover:
            ctx = await browser.new_context()
            page = await ctx.new_page()
            sessions = await discover_sessions(page, ci)
            print(f"\n📋 {len(sessions)} session(s):")
            for s in sessions[:20]:
                print(f"  si={s['si']}  {s['context'][:80]}")
            await ctx.close()
            await browser.close()
            return

        if args.si:
            batches = BATCHES.get(batch_key, [])
            if not batches:
                print(f"❌ No seat data for ci={ci}" + (f" house={args.house}" if args.house else ""))
                print(f"   Supported: {list(BATCHES.keys())}")
                await browser.close()
                return

            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto(f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={ci}&si={args.si}",
                            wait_until="domcontentloaded", timeout=30000)
            await sleep_ms(2000)
            if "Index.aspx" not in page.url:
                showtime_text = await page.evaluate("""
                    (function() {
                        var links = document.querySelectorAll('a');
                        for (var i=0; i<links.length; i++) {
                            var t = links[i].textContent.trim();
                            if (t.match(/^\d{1,2}:\d{2}[AP]M$/)) return t;
                        }
                        return '10:35AM';
                    })()
                """)
            else:
                showtime_text = "10:35AM"
            await ctx.close()

            print(f"  House: {'8' if args.house == 8 else '?'}")
            print(f"  Showtime: {showtime_text}")
            print(f"  Batches: {len(batches)} ({len(batches)*6} seats)")

            # Slice batch range
            bs = max(0, args.batch_start - 1)
            be = args.batch_end or len(batches)
            sliced = batches[bs:be]
            print(f"  Running batches {bs+1}-{min(be, len(batches))} ({len(sliced)} batches)")

            ok, fail = await fill_session(browser, ci, args.si, showtime_text, sliced, "S")
            print(f"  ▶ {ok} batches succeeded, {fail} failed")

            # ── Brim mode: check remaining seats and fill them ──
            if args.brim:
                print(f"\n{'='*50}")
                print(f"  BRIM: checking remaining empty seats...")
                print(f"{'='*50}")
                brim_ok = 0
                for brim_round in range(5):  # up to 5 brim rounds
                    # Fetch seat plan
                    ctx2 = await browser.new_context()
                    p2 = await ctx2.new_page()
                    await p2.goto(f"https://info.mclcinema.com/RealSeatPlan/SeatPlan?cinemaCode={ci}&filmSessionId={args.si}&language=en-US&seatCount=6&twoSeatCount=0",
                                  wait_until="domcontentloaded", timeout=30000)
                    await sleep_ms(2000)

                    remaining = await p2.evaluate("""
                        (function() {
                            var imgs = document.querySelectorAll('img[id]');
                            var empty = [];
                            imgs.forEach(function(img) {
                                var sn = img.getAttribute('seatnum') || '';
                                var status = img.getAttribute('status') || '';
                                if (sn && status === 'Normal') {
                                    empty.push({
                                        sn: sn,
                                        row: img.getAttribute('row'),
                                        col: img.getAttribute('column'),
                                        areacode: img.getAttribute('areacode')
                                    });
                                }
                            });
                            return JSON.stringify(empty);
                        })()
                    """)
                    await ctx2.close()

                    empty_seats = json.loads(remaining)
                    if not empty_seats:
                        print(f"  BRIM: no empty seats left! Theatre is full.", flush=True)
                        break

                    print(f"  BRIM round {brim_round+1}: {len(empty_seats)} empty seats found", flush=True)

                    # Group into batches of 6
                    brim_batches = []
                    for i in range(0, len(empty_seats), 6):
                        group = empty_seats[i:i+6]
                        if len(group) == 6:
                            batch = [(s['sn'], int(s['row']), int(s['col'])) for s in group]
                            brim_batches.append(batch)

                    if not brim_batches:
                        print(f"  BRIM: less than 6 seats remaining, can't batch", flush=True)
                        break

                    print(f"  BRIM: attempting {len(brim_batches)} dynamic batches", flush=True)
                    r_ok, r_fail = await fill_session(browser, ci, args.si, showtime_text, brim_batches, "BRIM")
                    brim_ok += r_ok

                print(f"  BRIM: {brim_ok} additional batches filled", flush=True)

            await browser.close()
            return

        print("Specify --ci <code> --si <session_id> or --url <mobile_url>")
        print(f"Supported: {list(BATCHES.keys())}")

if __name__ == "__main__":
    asyncio.run(main())