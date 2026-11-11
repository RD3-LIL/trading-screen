# Trading Screen

Institutional-style morning screen for FX, commodities, macro and rates, built from free data only. Same process as College Ratings: a Python fetcher, a static site generator, GitHub Pages.

Not for trading. This is a learning exercise to see what a hedge fund analyst screen can look like when the only inputs are free public data.

## What is on it

- Cross-asset snapshot: DXY, S and P 500, Nasdaq, VIX, US yields
- FX board, G10 majors and crosses: spot, 1D / 1W / 1M / YTD, 52 week range position, 50D / 200D averages, RSI 14, trend
- Commodities: Energy (WTI, Brent, NatGas), Metals (Gold, Silver, Copper, Platinum), Agriculture (Corn, Wheat, Soybeans, Coffee, Sugar)
- Macro and rates: Yahoo yields (13 week, 5Y, 10Y, 30Y), curve slopes, FRED series where fetchable, driver notes (paired moves, not causality)
- Positioning: CFTC Commitments of Traders, non-commercial net, when the file loads
- Signals: biggest 1 day movers, RSI extremes, near 52 week edge

## Sources, all free

- Yahoo Finance chart API, no key, 1 year daily history. Primary source. Unofficial and indicative, not execution grade.
- ECB daily euro reference rates, no key.
- FRED fredgraph.csv, attempted with a 12 second timeout. It timed out twice from this VM on Nov 11, 2026, so Yahoo yields are the primary rates source. A free FRED API key would make this reliable.
- CFTC Commitments of Traders, free weekly text file. Tuesday positions, released Friday.

## Refresh

```bash
cd ~/workspace/trading-screen
python3 fetch.py
python3 build_page.py
```

Then open `index.html`, or push it to GitHub Pages.

Daily update: `daily_update.sh` runs the same two steps at 6:00 AM Chicago time, matching the College Ratings pattern. The push step is left manual, it waits for Ron to approve a push.

## Honest limits

- Yahoo is unofficial and indicative, not execution grade. No tick data, no order book, no options volatility surface.
- No OTC FX forwards or swaps, no credit spreads at institutional depth.
- Futures are front month only. Full curve shape needs exchange data, not free here.
- COT is weekly and lagged. FRED is daily and lagged.
- Carry (policy rate differentials) is not in the free Yahoo feed, so no carry column is shown. A 2Y yield is not in the free Yahoo feed either, so the 2Y/10Y spread is not shown.
- If a fetch fails, the last good value is kept and labeled stale, or the panel says unavailable. No numbers are invented.

## Files

- `fetch.py`: pulls Yahoo, ECB, FRED (short timeout), CFTC, writes `data/prices.json`
- `build_page.py`: reads `data/prices.json`, writes `index.html`
- `daily_update.sh`: 6:00 AM Chicago refresh, fetch plus rebuild, push manual
- `DESIGN.md`: original design note
- `data/prices.json`: last fetched snapshot, with per-ticker status
