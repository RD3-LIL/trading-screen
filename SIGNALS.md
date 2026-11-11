# Trading Screen Signals v1 - Design (draft, Nov 11, 2026)

## Goal
Same shape as KenPom and the Stock Evaluator: data plus deterministic math first, detectors in code, then plain-English reasons. No LLM score, no invented numbers. A signal is a systematic flag, not a trade call and not investment advice.

## How it fits Ron's 4-layer thesis (Nov 10)
1. Data plus deterministic math: Yahoo 1y daily closes, already in data/prices.json
2. Detector layer in code, not LLM: rules below, each with a fixed threshold, computed in signals.py
3. AI reasoning grounded only on detector output plus exact rows: the page lists the exact trigger values for each flag
4. Verification plus feedback: lock the rules first, then backtest on the history we already have, report hit rate honestly, Ron rates findings

## Signal families (v1)
- Trend: last vs 50D and 200D averages, 50D crossing 200D (golden/death cross), 200D slope over 20 days
- Momentum: 1M and 3M return, RSI 14, position in 52-week range
- Mean reversion: RSI below 30 (oversold) or above 70 (overbought), distance from 200D average in percent, Bollinger position if std dev is available from closes
- Breakout: close at or above 52-week high, or at or below 52-week low, plus 20-day high/low break
- Volatility regime: VIX level and 14-day ATR (from Yahoo high/low), used as context, not as a buy/sell trigger on its own
- Cross-asset: Gold vs 10Y yield move, WTI vs DXY move, Copper vs S&P move, same window, paired moves only, not causality

## Composite
Per instrument, a 0-100 score, same discipline as the Stock Evaluator:
- Trend 40 points
- Momentum 30 points
- Mean reversion 15 points (scored toward neutral when stretched, not toward chasing)
- Volatility / positioning context 15 points
Labels: Strong Bullish 75+, Bullish 60-74, Neutral 40-59, Bearish 25-39, Strong Bearish below 25. Each label lists its top 3 trigger reasons with exact numbers.

## Backtest (v1 plus backtest option)
Lock the rules above, then test on 5y daily history, not the 1y snapshot. Verified live Nov 11: Yahoo chart API range=5y interval=1d returns EURUSD 1,305 points (2021-11-11 to 2026-11-11), Gold 1,260, WTI 1,260, 10Y 1,255, S&P 1,255. That gives about 1,000 signal dates after the 200-day warmup, versus about 50 with 1y. Caveat: range=max with interval=1d returns monthly bars, not daily (EURUSD 277 points from 2003-12), so do not use max for daily signals. For longer than 5y, chunk by period1/period2 in 5y blocks. For each signal date, forward 5-day and 20-day return, hit rate, average return, and comparison to always-long. Report honestly, including that even 5y is one regime window and that a signal that worked in 2021-2026 may not work in a ranging year. Do not tune thresholds to the backtest after seeing it.

## Honest limits
- 1y of daily data is short for backtesting, especially for commodities cycles.
- No COT positioning yet (CFTC 403), no carry (no policy rates in Yahoo feed), no options vol, no intraday data.
- A signal is a flag to look closer, not a buy or sell order. The page will say that on every signal panel.

## Files (planned)
- signals.py: detectors, composite score, backtest.py if backtest option is picked
- build_page.py: new Signals section at the top, with per-instrument reasons
- data/signals.json: detector output, so the page and any AI read are grounded on the same file

## Status, built Nov 11, 2026
- signals.py and backtest.py built and run for real. No push yet.
- Current signals (Nov 11 data): Strong Bullish 4, Bullish 10, Neutral 8, Bearish 7, Strong Bearish 1. DXY 82 Strong Bullish, USDJPY 80 Strong Bullish, USDCHF 81 Strong Bullish, S&P 500 61 Bullish, WTI 54 Neutral, Gold 28 Bearish, EUR/USD 27 Bearish, Coffee 18 Strong Bearish.
- Backtest verdict: no signal. 31,561 observations, 5y history. 20-day pooled: Bullish avg +0.35% (hit 52.9%), Neutral +0.38%, Bearish avg +1.65% (hit 42.8%). Bullish did not beat Neutral, Bearish rose on average instead of falling. Bearish beat Bullish on average in 28 of 30 tickers. VIX is the most extreme case (Bullish VIX -6.88%, Bearish VIX +6.74%) but not the whole story. Full numbers in backtest_signals.md. No thresholds were tuned after seeing this.
- RSI note: signals.py computes RSI 14 as a simple 14-day average gain/loss, not Wilder smoothing, so it can differ a few points from the stored RSI in prices.json (EUR/USD 37.4 vs 36.7, Gold 46.4 vs 43.0). Same method is used in the backtest, so the test is consistent.
- No ATR: prices.json has closes only, no high/low series, so ATR is unavailable and is not scored.
- Integration left for parent: add a Signals section to build_page.py reading data/signals.json, plus a backtest summary, then push signals.py, backtest.py, data/signals.json, data/history_5y.json, backtest_signals.md and SIGNALS.md to GitHub. Do not edit fetch.py or build_page.py in this task, the retry agent may still be working there.
