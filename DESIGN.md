# Trading Screen v1 - Design (approved scope: FX + commodities + macro and rates, built Nov 11, 2026)

Built Nov 11, 2026 in this folder, on disk only, no push yet. Ron created public repo RD3-LIL/trading-screen on github.com (created 17:39 UTC Nov 11, default branch main), so the next step is push plus Pages enable, not repo creation.
Verified run Nov 11, 11:39 AM Chicago: Yahoo 30 of 30 tickers ok, ECB ok (EUR/USD 1.1127), FRED all 7 series unavailable (timeout), CFTC COT unavailable (HTTP 403 Forbidden). Spot values in that run: EUR/USD 1.1095, Gold 4,010.60, WTI 86.99, Brent 93.05, DXY 102.91, S and P 500 7,634.17, Nasdaq 25,618.08, VIX 17.72, US 10Y 5.00%.

## Goal
Institutional-level morning screen for FX and commodities, built from free data only. Not for trading. Same process as College Ratings: Python fetcher, static site, GitHub Pages, daily refresh.

## Verified live Nov 11, 2026
- Yahoo Finance chart API, no key: EURUSD 1.1095 (-0.64%), Gold Dec 4011.7, WTI 86.96 (+1.07%)
- ECB daily FX reference rates, no key: EURUSD 1.1127 on Nov 11
- FRED fredgraph.csv: timed out Nov 11 in two tests, retry pending. API is free with signup key.
- Stooq CSV and CFTC COT: documented free, no key, live pull pending (test running Nov 11)

## Panels (v1)
1. Cross-asset snapshot: DXY, S&P 500, Nasdaq, VIX, US 2Y / 10Y
2. FX board, G10: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD, plus EURGBP, EURJPY, GBPJPY. Columns: spot, 1D / 1W / 1M / YTD, 52-week range position, 50D / 200D averages, RSI 14, carry (rate differential)
3. Commodities board:
   - Energy: WTI (CL=F), Brent (BZ=F), NatGas (NG=F)
   - Metals: Gold (GC=F), Silver (SI=F), Copper (HG=F), Platinum (PL=F)
   - Ags: Corn (ZC=F), Wheat (ZW=F), Soybeans (ZS=F), Coffee (KC=F), Sugar (SB=F)
   Columns: spot / front month, 1D / 1W / 1M / YTD, 52-week position, 50D / 200D, RSI 14, curve shape where available
4. Positioning: CFTC COT managed money net, with z-score vs 3-year history. Weekly, Tuesday positions, released Friday.
5. Signals: biggest movers, overbought / oversold (RSI), 52-week breaks

## If Ron picks macro + rates option, add:
6. Macro / rates: FRED DGS2, DGS10, DGS30, T10YIE (breakeven), CPIAUCSL, FEDFUNDS, 2Y/10Y spread, real 10Y (DFII10). Plus Gold vs real yields and Oil vs DXY driver notes.

## Honest limits
- Yahoo is unofficial and indicative, not execution grade. Delayed, no tick data, no order book, no options vol surface.
- Futures curve limited to front contracts via Yahoo. Full curve needs exchange data, not free.
- COT is weekly and lagged.
- FRED is daily lagged, not real time.
- No OTC FX forwards, no swaps, no credit spreads free at institutional depth.

## Build plan (once scope is picked)
- `~/workspace/trading-screen/fetch.py`: Yahoo + ECB + FRED + CFTC, writes `data/prices.json` and `data/history.csv`
- `build_page.py`: static `index.html`, dark terminal style, tables sortable, stale-data label if fetch fails (same safeguard as Chicago Pulse crime map)
- `daily_update.sh`: 6:00 AM Chicago, fetch + rebuild, push waits for Ron approval (same as College Ratings)
- Repo: Ron creates on github.com (Muse cannot create repos, 403). Suggested name: Trading-Screen. Pages: https://rd3-lil.github.io/Trading-Screen/

## Open decisions
- Scope: FX + commodities only, or FX + commodities + macro/rates
- Repo name confirmation
- Daily update time (default 6:00 AM Chicago, same as College Ratings)
