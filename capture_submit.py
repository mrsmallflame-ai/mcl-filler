#!/usr/bin/env python3
"""Capture the exact HTTP request SubmitSeatPlan makes."""
import asyncio, json, time
from playwright.async_api import async_playwright

CI, SI = "017", "127646"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
        page = await ctx.new_page()

        captured = []
        async def on_request(req):
            if "submit" in req.url.lower() or "seatplan" in req.url.lower() or "ticketing" in req.url.lower():
                captured.append({
                    "url": req.url,
                    "method": req.method,
                    "headers": dict(req.headers),
                    "post": req.post_data,
                })
        page.on("request", on_request)

        # navigate flow
        await page.goto(f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={CI}&si={SI}",
                        wait_until="domcontentloaded", timeout=30000)
        st = await page.evaluate("(function(){var l=document.querySelectorAll('a');for(var i=0;i<l.length;i++){var t=l[i].textContent.trim();if(t.match(/^\\d{1,2}:\\d{2}[AP]M$/))return t;}return '';})()")
        await page.evaluate(f"(function(){{var l=document.querySelectorAll('a');for(var i=0;i<l.length;i++){{if(l[i].textContent.trim()==='{st}'){{l[i].click();return true;}}}}return false;}})()")
        for _ in range(15):
            await asyncio.sleep(0.3)
            src = await page.evaluate("(function(){var f=document.querySelector('iframe');return f?f.src:'';})()")
            if src: break
        await page.goto(src, wait_until="domcontentloaded", timeout=30000)
        try:
            async with page.expect_navigation(timeout=8000):
                await page.evaluate("document.getElementById('nonMemberNextButton')?.click()")
        except: pass
        try:
            async with page.expect_navigation(timeout=8000):
                await page.evaluate("""
                    var s=document.querySelector('select[id="inputGroupSelectTicket"]');
                    s.value='6';s.dispatchEvent(new Event('change',{bubbles:true}));
                    var b=document.querySelector('input[tickettypesubmit]');if(b)b.disabled=false;
                    document.querySelector('form').submit();""")
        except: pass

        captured.clear()  # only capture the SubmitSeatPlan call
        seats = [("B18","8","18"),("B17","8","17"),("B16","8","16"),("B15","8","15"),("B14","8","14"),("B13","8","13")]
        sj = json.dumps([{"AreaCode":"0000000001","AreaNumber":"1","RowIndex":r,"ColumnIndex":c,"SeatName":s} for s,r,c in seats])
        await page.evaluate(f"SubmitSeatPlan({{selectedSeats:{sj},languageCulture:'en-US',platform:'DesktopWeb'}});")
        for _ in range(24):
            await asyncio.sleep(0.25)
            if "Payment" in page.url: break

        print(f"captured {len(captured)} requests:")
        for c in captured:
            print(f"\n=== {c['method']} {c['url'][:120]}")
            print(f"POST: {c['post'][:500] if c['post'] else None}")
            interesting = {k:v for k,v in c['headers'].items() if k.lower() in ['content-type','referer','cookie','x-requested-with','origin']}
            for k,v in interesting.items():
                print(f"{k}: {v[:200] if isinstance(v,str) else v}")

        # dump cookies for later httpx reproduction
        cookies = await ctx.cookies()
        print(f"\nCOOKIES ({len(cookies)}):")
        for ck in cookies:
            print(f"  {ck['domain']} {ck['name']}={ck['value'][:30]}...")

        await browser.close()

asyncio.run(main())