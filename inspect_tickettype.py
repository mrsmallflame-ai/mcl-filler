#!/usr/bin/env python3
"""Inspect the TicketType page structure via pure HTTP."""
import httpx, asyncio, re

async def t():
    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(8.0, connect=5.0)) as c:
        c.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                          'Accept-Language': 'en-US'})
        r0 = await c.get('https://www.mclcinema.com/MCLSelectSeat.aspx', params={'visLang': '2', 'ci': '017', 'si': '127646'})
        mset = re.search(r'MovieSetId.{0,3}?(\d+)', r0.text) or re.search(r'V-(\d+)\.(?:jpg|png)', r0.text)
        print('MovieSetId:', mset.group(1) if mset else 'NONE')
        r = await c.get('https://www.mclcinema.com/GetPurchaseIFrameURL.aspx',
                        params={'CinemaCodeID': '017', 'FilmSessionId': '127646',
                                'MovieSetId': mset.group(1), 'Language': 'en-US'},
                        headers={'Referer': 'https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci=017&si=127646'})
        turl = re.search(r'https://www4\.mclcinema\.com/MCL\.Front\.Ticketing\?[^"\']+', r.text).group(0).replace('&amp;', '&')
        r = await c.get(turl)
        open('/tmp/entry.html', 'w').write(r.text)
        print('entry page saved, len:', len(r.text))
        forms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>(.*?)</form>', r.text, re.S)
        print('forms found:', len(forms))
        for action, body in forms:
            print(f'  form action={action[:60]} has_nonmember={"nonMember" in body}')
            if 'nonmember' not in body.lower():
                continue
            fields = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"', body))
            try:
                r2 = await c.post('https://www4.mclcinema.com' + action.replace('&amp;', '&'), data=fields)
                print(f'  POST done: {r2.status_code} len={len(r2.text)}')
            except Exception as e:
                import traceback; traceback.print_exc()
                return
            html = r2.text
            open('/tmp/tickettype.html', 'w').write(html)
            print('tickettype page saved, len:', len(html))
            for m in re.finditer(r'<select[^>]*>', html):
                print('SELECT:', m.group(0)[:160])
            allforms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>(.*?)</form>', html, re.S)
            for a2, b2 in allforms:
                print('FORM action:', a2[:90])
                print('  input names:', re.findall(r'name="([^"]*)"', b2)[:15])
            break
asyncio.run(t())