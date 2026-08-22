# MCL Seat Filler — Status

## Usage

Run against any desktop, mobile, or RealSeatPlan MCL link:

```bash
python3 mcl_filler.py --url '<any mcl link>' --parallel 3
```

- The cinema/session IDs are parsed from the URL.
- The live Normal-seat map is fetched and grouped into batches of 6 automatically.
- Three Chromium workers run batches round-robin by default (`--parallel N`).
- Brim mode is enabled by default: after the initial pass it re-fetches the seat map and books fresh 6-seat batches until full or two consecutive rounds have no successes. Use `--no-brim` to disable it; `--brim` remains accepted for compatibility.
- `--headless`, `--batch-start`, and `--batch-end` remain available.

## ✅ Round 1: App scaffold + correct batch data
- [x] `mcl_filler.py` with Playwright-based 9-step booking flow
- [x] Dynamic seat-plan detection replaces all hardcoded house/batch tables

## 🔄 Round 2: Claude Code review (in progress)
Review error handling, SubmitSeatPlan flow, and popup handling.
