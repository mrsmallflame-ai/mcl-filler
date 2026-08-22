# mcl-filler

Rapid seat filler for MCL Cinema (Hong Kong). Pure-HTTP booking engine — no browser rendering. Fills every available seat in a theatre using parallel workers, then keeps running to re-claim seats as unpaid claims expire.

**Benchmarks:** full 113-seat house in 41s · peak **514 seats/min** (16 workers) · three houses filled simultaneously.

## Requirements

- Python **3.10+**
- [`httpx`](https://www.python-httpx.org/) — the only dependency

## Setup (any computer)

```bash
# 1. get the repo
git clone https://github.com/mrsmallflame-ai/mcl-filler.git
cd mcl-filler

# 2. create a virtualenv and install the one dependency
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install httpx

# 3. done — run it
python3 mcl_filler.py --url "<paste any MCL session link>" 12
```

No API keys, no config files, no browser install needed.

## Usage

Paste **any** MCL link format — desktop, mobile, or seat-plan:

```bash
# desktop link
python3 mcl_filler.py --url "https://www.mclcinema.com/MCLSelectSeat.aspx?visLang=2&ci=017&si=127637" 12

# mobile link
python3 mcl_filler.py --url "https://m.mclcinema.com/Ticketing/PreviewSeatPlan?movieSetId=14822&cinemaCodeID=017&sessionID=127522&Language=en-US" 8

# direct ci/si also works
python3 mcl_filler.py --ci 021 --si 37011 16
```

The last argument is the number of parallel workers (default 12).

### What it does

1. Fetches the live seat plan and chunks all available seats into groups of 6.
2. Each worker runs the complete MCL purchase chain over plain HTTP with its own cookie jar: entry page → non-member → ticket selection (6 × standard adult) → seat claim → payment page.
3. When the house is full, it idles and rescans every 20s — unpaid claims expire after ~10 minutes, so released seats are instantly re-claimed.
4. `Ctrl+C` stops cleanly with final stats.

### Options (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `BLAZE_SEATS` | `6` | Seats claimed per worker per round |
| `BLAZE_IDLE_POLL` | `20` | Seconds between scans when house is full |
| `BLAZE_ROUNDS` | unlimited | Cap rounds (set for testing) |

## Finding sessions

Browse [mclcinema.com](https://www.mclcinema.com) → pick movie → copy the link of the showtime you want → paste into `--url`. Cinema codes used internally: `017` K11 Art House, `019` Grand Windsor, `021` The One, `018` Citygate, etc. (any code works — it's read from your link).

## Files

- `mcl_filler.py` — CLI entry point; parses any MCL URL and calls the engine
- `blaze2.py` — the pure-HTTP engine (seat-plan fetcher, worker pool, booking chain)
- `profile_batch.py`, `trace_flow.py`, `capture_*.py` — dev tools used to reverse-engineer the chain

## Notes

- Bookings stop at the **payment page** — nothing is paid automatically. Claims expire (~10 min) if unpaid.
- MCL rate-limits its seat-plan endpoint when hammered; the engine backs off automatically and resumes.
- For personal/testing use only — be reasonable, don't disrupt real screenings for actual customers.
