#!/usr/bin/env python3
"""Trace every request in the booking flow to replicate in pure HTTP."""
import asyncio, json
from playwright.async_api import async_playwright

CI, SI = "017", "127646"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
        page = await ctx.new_page()

        trace = []
        seq = [0]
        def log_req(req):
            if any(x in req.url for x in ["google-analytics", "googletagmanager", ".png", ".jpg", ".css", ".js?", "font", ".ico", ".gif"]):
                return
            seq[0] += 1
            trace.append({"n": seq[0], "phase": "req", "method": req.method, "url": req.url[:150],
                          "post": (req.post_data or "")[:200]})
        page.on("request", log_req)
        resp_log = []
        async def log_resp(resp):
            if any(x in resp.url for x in ["google-analytics", "googletagmanager", ".png", ".jpg", ".css", ".js?", "font", ".ico", ".gif"]):
                return
            try:
                body = ""
                if resp.request.method == "POST" or "Ticketing" in resp.url:
                    body = (await resp.text())[:300]
            except: pass
            resp_log.append({"url": resp.url[-60:], "status": resp.status, "body": body})
        page.on("response", log_resp)

        # Full flow
        await page.goto(f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={CI}&si={SI}",
                        wait_until="domcontentloaded", timeout=30000)
        st = await page.evaluate("(function(){var l=document.querySelectorAll('a');for(var i=0;i<l.length;i++){var t=l[i].textContent.trim();if(t.match(/^\\d{1,2}:\\d{2}[AP]M$/))return t;}return '';})()")
        print(f"showtime: {st}")
        await page.evaluate(f"(function(){{var l=document.querySelectorAll('a');for(var i=0;i<l.length;i++){{if(l[i].textContent.trim()==='{st}'){{l[i].click();return true;}}}}return false;}})()")
        for _ in range(15):
            await asyncio.sleep(0.3)
            src = await page.evaluate("(function(){var f=document.querySelector('iframe');return f?f.src:'';})()")
            if src: break
        print(f"IFRAME SRC: {src[:200]}")
        await page.goto(src, wait_until="domcontentloaded", timeout=30000)
        try:
            async with page.expect_navigation(timeout=8000):
                await page.evaluate("document.getElementById('nonMemberNextButton')?.click()")
        except: pass
        print(f"AFTER NONMEMBER: {page.url[:150]}")
        try:
            async with page.expect_navigation(timeout=8000):
                await page.evaluate("""
                    var s=document.querySelector('select[id="inputGroupSelectTicket"]');
                    s.value='6';s.dispatchEvent(new Event('change',{bubbles:true}));
                    var b=document.querySelector('input[tickettypesubmit]');if(b)b.disabled=false;
                    document.querySelector('form').submit();""")
        except Exception as e:
            print(f"ticket exc: {str(e)[:80]}")
        print(f"AFTER TICKET: {page.url[:150]}")

        seats = [("B18","8","18"),("B17","8","17"),("B16","8","16"),("B15","8","15"),("B14","8","14"),("B13","8","13")]
        sj = json.dumps([{"AreaCode":"0000000001","AreaNumber":"1","RowIndex":r,"ColumnIndex":c,"SeatName":s} for s,r,c in seats])
        trace.clear()
        await page.evaluate(f"SubmitSeatPlan({{selectedSeats:{sj},languageCulture:'en-US',platform:'DesktopWeb'}});")
        for _ in range(24):
            await asyncio.sleep(0.25)
            if "Payment" in page.url: break
        print(f"AFTER SUBMIT: {page.url[:100]} {'✅' if 'Payment' in page.url else ''}")

        print("\n===== REQUEST TRACE =====")
        for t in trace:
            print(f"[{t['n']}] {t['method']} {t['url']}")
            if t['post']: print(f"      POST: {t['post'][:180]}")

        print("\n===== KEY RESPONSES =====")
        for r in resp_log:
            if r['body']:
                print(f"{r['status']} ...{r['url']}")
                print(f"   {r['body'][:250]}")

        await browser.close()

asyncio.run(main())