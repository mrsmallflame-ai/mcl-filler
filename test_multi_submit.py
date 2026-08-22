#!/usr/bin/env python3
"""Test: multiple SubmitSeatPlan calls on the SAME page (no re-navigation)."""
import asyncio, json, time
from playwright.async_api import async_playwright

CI, SI = "017", "127646"

def seats_payload(seats):
    return json.dumps([{"AreaCode":"0000000001","AreaNumber":"1",
        "RowIndex":r,"ColumnIndex":c,"SeatName":s} for s,r,c in seats])

async def get_to_pickseats(browser):
    ctx = await browser.new_context(
        viewport={"width":1280,"height":900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    page = await ctx.new_page()
    await page.goto(f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={CI}&si={SI}",
                    wait_until="domcontentloaded", timeout=30000)
    st = await page.evaluate("""
        (function(){var l=document.querySelectorAll('a');
        for(var i=0;i<l.length;i++){var t=l[i].textContent.trim();
        if(t.match(/^\\d{1,2}:\\d{2}[AP]M$/))return t;}return '';})()""")
    await page.evaluate(f"""
        (function(){{var l=document.querySelectorAll('a');
        for(var i=0;i<l.length;i++){{if(l[i].textContent.trim()==='{st}'){{
            document.querySelectorAll('.dialog-container,.modal,.popup').forEach(function(x){{x.style.display='none';}});
            l[i].click();return true;}}}}return false;}})()""")
    for _ in range(15):
        await asyncio.sleep(0.3)
        src = await page.evaluate("(function(){var f=document.querySelector('iframe');return f?f.src:'';})()")
        if src: break
    await page.goto(src, wait_until="domcontentloaded", timeout=30000)
    print(f"  [setup] after iframe goto: {page.url[-40:]}")
    try:
        async with page.expect_navigation(timeout=8000):
            await page.evaluate("document.getElementById('nonMemberNextButton')?.click()")
        print(f"  [setup] non-member nav OK: {page.url[-40:]}")
    except Exception as e:
        print(f"  [setup] non-member exc: {str(e)[:50]} | url: {page.url[-40:]}")
    try:
        async with page.expect_navigation(timeout=8000):
            await page.evaluate("""
                var s=document.querySelector('select[id="inputGroupSelectTicket"]');
                s.value='6';s.dispatchEvent(new Event('change',{bubbles:true}));
                var b=document.querySelector('input[tickettypesubmit]');if(b)b.disabled=false;
                document.querySelector('form').submit();""")
        print(f"  [setup] ticket nav OK: {page.url[-40:]}")
    except Exception as e:
        print(f"  [setup] ticket exc: {str(e)[:50]} | url: {page.url[-40:]}")
    return ctx, page

async def try_submit(page, seats, label):
    t0 = time.time()
    await page.evaluate(f"SubmitSeatPlan({{selectedSeats:{seats_payload(seats)},languageCulture:'en-US',platform:'DesktopWeb'}});")
    for _ in range(24):
        await asyncio.sleep(0.25)
        if "Payment" in page.url:
            return f"{label}: ✅ PAYMENT in {time.time()-t0:.2f}s"
    # check for popup content
    popup = await page.evaluate("""
        (function(){
            var els = document.querySelectorAll('.dialog-container,.modal,.popup,[class*="dialog"]');
            var texts = [];
            els.forEach(function(e){ if(e.offsetParent!==null && e.textContent.trim()) texts.push(e.textContent.trim().substring(0,80)); });
            return texts.join(' || ') || 'no visible popup';
        })()
    """)
    return f"{label}: ❌ no payment in {time.time()-t0:.2f}s | popup: {popup[:120]}"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        t0 = time.time()
        ctx, page = await get_to_pickseats(browser)
        print(f"setup to PickSeats: {time.time()-t0:.2f}s | on PickSeats: {'PickSeats' in page.url or 'ckSeats' in page.url}")

        # Attempt multiple submits with DIFFERENT seats on the same page
        attempts = [
            ([("B18","8","18"),("B17","8","17"),("B16","8","16"),("B15","8","15"),("B14","8","14"),("B13","8","13")], "try1 B18-B13"),
            ([("B12","8","12"),("B11","8","11"),("B10","8","10"),("B9","8","9"),("B8","8","8"),("B4","8","4")], "try2 B12-B4"),
            ([("C18","7","18"),("C17","7","17"),("C16","7","16"),("C15","7","15"),("C14","7","14"),("C13","7","13")], "try3 C18-C13"),
            ([("D18","6","18"),("D17","6","17"),("D16","6","16"),("D15","6","15"),("D14","6","14"),("D13","6","13")], "try4 D18-D13"),
            ([("E18","5","18"),("E17","5","17"),("E16","5","16"),("E15","5","15"),("E14","5","14"),("E13","5","13")], "try5 E18-E13"),
        ]
        for seats, label in attempts:
            if "Payment" in page.url:
                print(f"{label}: SKIP - already on payment")
                break
            print(await try_submit(page, seats, label))

        await ctx.close()
        await browser.close()

asyncio.run(main())