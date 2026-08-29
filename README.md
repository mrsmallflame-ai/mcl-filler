# 🎬 MCL Cinema Seat Filler

Grab **every empty seat** in an MCL Cinema (Hong Kong) showtime — automatically — so nobody else can take them. Pure HTTP, no browser needed.

> 🏠 Full 113-seat house in **41 seconds** · peak **514 seats/min** · 3 houses at once.

---

## 🚀 THE 3-STEP GUIDE (if you can paste text, you can do this)

### Step 1 — Put this in your Terminal and press Enter

**Mac / Linux:**
```bash
git clone https://github.com/mrsmallflame-ai/mcl-filler.git && cd mcl-filler && bash run-mcl.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/mrsmallflame-ai/mcl-filler.git; cd mcl-filler; powershell -ExecutionPolicy Bypass -File run-mcl.ps1
```

It asks you to **paste one link**. That's it. (First run takes ~1 minute to set up — after that it's instant.)

> No Terminal experience? Open Terminal: Mac → press `Cmd+Space`, type `Terminal`, press Enter. Windows → press `Win key`, type `PowerShell`, press Enter.

### Step 2 — Get your link (60 seconds on the MCL website)

1. Go to **[mclcinema.com](https://www.mclcinema.com)** → pick your movie
2. Click the **showtime** you want (the button with the time, like `7:30 PM`)
3. When the seat map opens, **copy the link at the top of your browser** — it looks like:

```
https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci=017&si=127637
```

### Step 3 — Paste that link, press Enter, done ✅

The filler grabs seats in bursts of 6 (MCL's **hard maximum per transaction** — asking for more than 6 at once is what causes the `max 6 seats/transaction` error, and the tool now auto-clamps so it can never happen).

**To stop it:** click the Terminal and press `Ctrl+C`.

That's the whole thing. Everything below is optional detail.

---

## ⚡ One-liners (for people who hate reading)

Mac/Linux — clone and go, zero flags:
```bash
git clone https://github.com/mrsmallflame-ai/mcl-filler.git && cd mcl-filler
python3 mcl_filler.py            # asks you to paste the link — that's all
```

Or classic style:
```bash
python3 mcl_filler.py --url "PASTE_ANY_MCL_LINK_HERE" 12
```

The **12** is how many workers to send (more = faster; 8–16 is the sweet spot).

---

## 🖥️ Running it on a VPS (Tencent HK etc.)

MCL **blocks datacenter IPs** (Tencent, AWS, WARP…). A VPS cannot reach MCL directly — your own home Mac can. Two ways:

### A) Mac relay (recommended)
1. On your **Mac**: `bash mac-relay.sh` (keep the window open)
2. On the **VPS**:
```bash
export BLAZE_PROXY=socks5://127.0.0.1:11080
python3 mcl_filler.py --url "<your MCL link>" 12
```

### B) Skip the VPS — run on the Mac
Your home IP always works. Just run it locally (Step 1 above).

If the seat plan is unreachable you'll see a 💡 hint telling you exactly this — it's the network, not the tool.

---

## 📖 What the tool actually does (plain words)

1. Looks at the real seat map and finds every free seat
2. Splits them into groups of **6** (one group = one transaction — MCL's limit)
3. Sends **one worker per group**, all at the same time — each worker does the whole human journey: open page → choose tickets → pick seats → reach the payment page
4. Stops there. **Nothing is ever paid.** Unpaid holds expire after ~10 minutes — and the tool notices the second they do, and grabs them again (verified: 18 seats re-grabbed within 8 seconds)
5. Runs until **you** press `Ctrl+C`

## 🎛️ All the knobs (you never need these)

| Flag / Env | Default | Meaning |
|---|---|---|
| `--url "<link>"` | – | Any MCL link: desktop, mobile, or seat-plan format |
| `--ci 017 --si 127637` | – | Or give the numbers straight from the link |
| *(no arguments at all)* | – | Interactive: it asks you to paste the link |
| workers (last number) | `12` | Parallel booking workers |
| `BLAZE_SEATS` | `6` | Seats per worker — **max 6, auto-clamped** (MCL limit) |
| `BLAZE_IDLE_POLL` | `20` | Seconds between re-scans when the house is full |
| `BLAZE_ROUNDS` | ∞ | Cap rounds (set a number for testing) |
| `BLAZE_PROXY` | – | `socks5://127.0.0.1:11080` when MCL blocks your IP |

## 🎬 Bonus: "just tell me the movie"

```bash
python3 mcl_find.py --movie "kung fu soccer" --cinema "movie town" --date aug28
```
→ finds matching showtimes and prints ready-to-run fill commands.

Or the whole pipeline in one shot (one tmux window per showtime, logs in `logs/`):
```bash
bash mcl_botfill.sh "kung fu soccer" "movie town" aug28 8
```

Check on everything that's running:
```bash
python3 mcl_status.py
```

## 🧰 Files

| File | What it is |
|---|---|
| `mcl_filler.py` | **Start here** — accepts any MCL link (or none: it asks) |
| `blaze2.py` | The engine: seat-plan fetcher + parallel booking chain |
| `mcl_find.py` | Movie name → showtime finder |
| `mcl_botfill.sh` | One command → fills every matching showtime |
| `mcl_status.py` | Dashboard of everything claimed/running |
| `run-mcl.sh` / `run-mcl.ps1` | One-line setup+run for Mac/Linux and Windows |
| `mac-relay.sh` + `mcl_socks.py` | Home-IP relay so a VPS can book too |

## ⚠️ The fine print

- Bookings stop at the **payment page** — you must pay within ~10 min or the seats release.
- MCL rate-limits heavy IPs; the tool backs off and recovers automatically.
- Requires Python 3.10+ and `httpx` (the launchers install it for you).
- For personal/testing use — don't disrupt real screenings for actual customers.

## 🧾 License

MIT
