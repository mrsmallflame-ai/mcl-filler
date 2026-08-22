#!/usr/bin/env python3
"""Profile one booking batch: measure every step's duration."""
import asyncio, json, time
from playwright.async_api import async_playwright

CI, SI = "017", "127646"

async def main():
    async with async_playwright() as pw:
        t0 = time.time()
        browser = await pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"])
        print(f"launch browser:      {time.time()-t0:6.2f}s")

        t0 = time.time()
        ctx = await browser.new_context(
            viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
        page = await ctx.new_page()
        print(f"new context+page:    {time.time()-t0:6.2f}s")

        t0 = time.time()
        await page.goto(f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={CI}&si={SI}",
                        wait_until="domcontentloaded", timeout=30000)
        print(f"goto MCLSelectSeat:  {time.time()-t0:6.2f}s")

        t0 = time.time()
        # find showtime link
        st = await page.evaluate("""
            (function(){
                var links = document.querySelectorAll('a');
                for (var i=0;i<links.length;i++){
                    var t = links[i].textContent.trim();
                    if (t.match(/^\\d{1,2}:\\d{2}[AP]M$/)) return t;
                }
                return '';
            })()
        """)
        print(f"find showtime '{st}': {time.time()-t0:6.2f}s")

        t0 = time.time()
        ok = await page.evaluate(f"""
            (function(){{
                var links = document.querySelectorAll('a');
                for (var i=0;i<links.length;i++){{
                    var t = links[i].textContent.trim();
                    if (t === '{st}') {{
                        var d = document.querySelectorAll('.dialog-container,.modal,.popup');
                        d.forEach(function(x){{x.style.display='none';}});
                        links[i].click(); return true;
                    }}
                }}
                return false;
            }})()
        """)
        print(f"click matched: {ok}")
        # wait for iframe to appear
        for _ in range(15):
            await asyncio.sleep(0.3)
            src = await page.evaluate("(function(){var f=document.querySelector('iframe');return f?f.src:'';})()")
            if src: break
        print(f"click showtime+iframe: {time.time()-t0:6.2f}s")

        t0 = time.time()
        await page.goto(src, wait_until="domcontentloaded", timeout=30000)
        print(f"goto www4 ticketing: {time.time()-t0:6.2f}s")

        t0 = time.time()
        try:
            async with page.expect_navigation(timeout=8000):
                await page.evaluate("document.getElementById('nonMemberNextButton')?.click()")
        except Exception as e:
            print(f"  nav exc: {str(e)[:60]}")
        print(f"non-member click:    {time.time()-t0:6.2f}s  url~{page.url[-30:]}")

        t0 = time.time()
        try:
            async with page.expect_navigation(timeout=8000):
                await page.evaluate("""
                    var s = document.querySelector('select[id=\"inputGroupSelectTicket\"]');
                    s.value='6';
                    s.dispatchEvent(new Event('change',{bubbles:true}));
                    var b = document.querySelector('input[tickettypesubmit]');
                    if (b) b.disabled=false;
                    document.querySelector('form').submit();
                """)
        except Exception as e:
            print(f"  nav exc: {str(e)[:60]}")
        print(f"ticket submit:       {time.time()-t0:6.2f}s  url~{page.url[-30:]}")

        t0 = time.time()
        has = await page.evaluate("typeof SubmitSeatPlan === 'function'")
        print(f"check fn exists:     {time.time()-t0:6.2f}s  has_fn={has}")

        if has:
            seats = [("A1","10","12"),("A2","10","11"),("A3","10","10"),("A4","10","9"),("A5","10","8"),("A6","10","7")]
            sj = json.dumps([{"AreaCode":"0000000001","AreaNumber":"1","RowIndex":r,"ColumnIndex":c,"SeatName":s} for s,r,c in seats])
            t0 = time.time()
            await page.evaluate(f"SubmitSeatPlan({{selectedSeats:{sj},languageCulture:'en-US',platform:'DesktopWeb'}});")
            for _ in range(20):
                await asyncio.sleep(0.25)
                if "Payment" in page.url: break
            print(f"SubmitSeatPlan:      {time.time()-t0:6.2f}s  -> {'PAYMENT ✅' if 'Payment' in page.url else page.url[-40:]}")

        total = time.time() - start_all
        print(f"\nTOTAL BATCH TIME:    {total:6.2f}s")
        await ctx.close()

start_all = time.time()
asyncio.run(main())