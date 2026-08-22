#!/usr/bin/env python3
"""Capture the exact SubmitSelectedTicketType request the browser sends."""
import asyncio, json
from playwright.async_api import async_playwright

CI, SI = "017", "127646"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
        page = await ctx.new_page()
        caps = []
        async def on_req(req):
            if "SubmitSelectedTicketType" in req.url or "SubmitSelectedSeat" in req.url:
                caps.append({"url": req.url, "method": req.method, "post": req.post_data,
                             "headers": {k: v for k, v in req.headers.items()
                                         if k.lower() in ("content-type", "referer", "x-requested-with", "cookie", "accept")}})
        page.on("request", on_req)

        await page.goto(f"https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci={CI}&si={SI}", wait_until="domcontentloaded")
        st = await page.evaluate("(function(){var l=document.querySelectorAll('a');for(var i=0;i<l.length;i++){var t=l[i].textContent.trim();if(t.match(/^\\d{1,2}:\\d{2}[AP]M$/))return t;}return '';})()")
        await page.evaluate(f"(function(){{var l=document.querySelectorAll('a');for(var i=0;i<l.length;i++){{if(l[i].textContent.trim()==='{st}'){{l[i].click();return true;}}}}return false;}})()")
        for _ in range(15):
            await asyncio.sleep(0.3)
            src = await page.evaluate("(function(){var f=document.querySelector('iframe');return f?f.src:'';})()")
            if src: break
        await page.goto(src, wait_until="domcontentloaded")
        try:
            async with page.expect_navigation(timeout=8000):
                await page.evaluate("document.getElementById('nonMemberNextButton')?.click()")
        except: pass
        # on TicketType now — set qty and trigger change
        await page.evaluate("""
            var s = document.querySelector('select[id="inputGroupSelectTicket"]');
            s.value = '6';
            s.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        await asyncio.sleep(2)
        print(f"captured {len(caps)}:")
        for c in caps:
            print(f"\n{c['method']} {c['url']}")
            print(f"  content-type: {c['headers'].get('content-type')}")
            print(f"  x-requested-with: {c['headers'].get('x-requested-with')}")
            print(f"  POST: {c['post']}")
        await browser.close()

asyncio.run(main())