# Signals v1 Backtest

Generated 2026-11-11 Chicago. Rules locked in signals.py before this backtest ran. No thresholds were tuned after seeing these results.

## Verdict: no signal

Pre-committed grading: Bullish labels must beat Neutral on average 20-day forward return, and Bearish labels must underperform Neutral, otherwise the verdict is weak or no signal. Bullish beat Neutral here by -0.03 points and Bearish underperformed Neutral by -1.26 points on the 20-day horizon. Bearish labels actually rose on average, so in this window they behaved like a contrarian bounce flag, not a down signal. That is reported as found, not tuned away.

## History

Yahoo chart API, range=5y, interval=1d, no key. 30 tickers, signal dates 2022-08-16 to 2026-10-14, 31561 signal observations. Actual points fetched this run: EURUSD 1300, Gold 1258, WTI 1257, 10Y 1255, S&P 500 1255, all from 2021-11-11 to 2026-11-11. A live check the same day gave 1,305 for EURUSD and 1,260 for Gold and WTI; the small gap is None closes filtered out on fetch. range=max with interval=1d returns monthly bars (EURUSD 277 points from 2003-12), so it was not used. For longer than 5y, chunk by period1/period2 in 5y blocks.

Walk forward: each observation needs 200 closes of history, then forward 5-day and 20-day returns. No lookahead: the score uses closes up to that date only, and the volatility median uses vols up to that date only.

## 20-day forward returns by label

| Label | n | Avg fwd % | Median fwd % | Hit rate % |
|---|---|---|---|---|
| Strong Bullish | 10862 | +0.43 | +0.25 | 53.2 |
| Bullish | 6887 | +0.24 | +0.20 | 52.4 |
| Neutral | 7619 | +0.38 | +0.32 | n/a |
| Bearish | 4388 | +1.61 | +0.54 | 44.0 |
| Strong Bearish | 1805 | +1.73 | +1.37 | 39.8 |
| Always long (all labels) | 31561 | +0.61 | +0.33 | n/a |

Pooled 20-day: Bullish plus Strong Bullish n=17749, avg +0.35%, median +0.23%, hit rate 52.9%. Neutral n=7619, avg +0.38%, median +0.32%. Bearish plus Strong Bearish n=6193, avg +1.65%, median +0.71%, hit rate 42.8%.

## 5-day forward returns by label

| Label | n | Avg fwd % | Median fwd % | Hit rate % |
|---|---|---|---|---|
| Strong Bullish | 10862 | +0.09 | +0.08 | 52.2 |
| Bullish | 6887 | -0.04 | +0.01 | 50.1 |
| Neutral | 7619 | +0.09 | +0.09 | n/a |
| Bearish | 4388 | +0.74 | +0.23 | 45.0 |
| Strong Bearish | 1805 | +0.77 | +0.46 | 44.0 |
| Always long (all labels) | 31561 | +0.19 | +0.10 | n/a |

Pooled 5-day: Bullish plus Strong Bullish n=17749, avg +0.04%, median +0.06%, hit rate 51.4%. Neutral n=7619, avg +0.09%, median +0.09%. Bearish plus Strong Bearish n=6193, avg +0.75%, median +0.28%, hit rate 44.7%.

## By group, 20-day forward return

| Group | n | Avg 20d % | Bullish n | Bullish avg 20d % | Bearish n | Bearish avg 20d % |
|---|---|---|---|---|---|---|
| Agriculture | 5189 | +0.09 | 2163 | -0.32 | 1726 | +1.02 |
| Cross-asset | 4148 | +1.16 | 2455 | -0.15 | 815 | +4.65 |
| Energy | 3116 | +0.43 | 1145 | -0.07 | 1052 | +1.98 |
| FX | 10810 | +0.15 | 6674 | -0.02 | 1410 | +0.45 |
| Metals | 4154 | +1.83 | 2732 | +1.79 | 515 | +3.36 |
| Rates | 4144 | +0.85 | 2580 | +1.00 | 675 | +0.29 |

## By ticker, 20-day forward return

| Ticker | n | Bullish n | Bullish avg 20d % | Bearish n | Bearish avg 20d % |
|---|---|---|---|---|---|
| AUDUSD=X | 1081 | 598 | -0.16 | 164 | +0.39 |
| BZ=F | 1039 | 363 | +1.62 | 354 | +2.44 |
| CL=F | 1038 | 370 | +1.78 | 368 | +2.16 |
| DX-Y.NYB | 1038 | 529 | -0.27 | 186 | +0.42 |
| EURGBP=X | 1081 | 579 | -0.10 | 135 | +0.15 |
| EURJPY=X | 1081 | 856 | +0.44 | 79 | +1.18 |
| EURUSD=X | 1081 | 660 | +0.04 | 158 | +0.32 |
| GBPJPY=X | 1081 | 820 | +0.28 | 67 | +2.21 |
| GBPUSD=X | 1081 | 724 | -0.17 | 89 | +0.63 |
| GC=F | 1039 | 791 | +1.95 | 111 | +2.26 |
| HG=F | 1039 | 683 | +0.98 | 101 | +3.38 |
| KC=F | 1039 | 527 | +0.78 | 288 | +2.44 |
| NG=F | 1039 | 412 | -3.21 | 330 | +1.28 |
| NZDUSD=X | 1081 | 522 | -0.87 | 219 | +0.45 |
| PL=F | 1038 | 586 | +1.45 | 171 | +2.78 |
| SB=F | 1039 | 410 | +0.48 | 376 | +1.55 |
| SI=F | 1038 | 672 | +2.75 | 132 | +5.01 |
| USDCAD=X | 1081 | 754 | -0.06 | 66 | +0.49 |
| USDCHF=X | 1081 | 435 | -0.21 | 308 | -0.20 |
| USDJPY=X | 1081 | 726 | +0.17 | 125 | +1.09 |
| ZC=F | 1037 | 408 | -1.12 | 336 | -0.29 |
| ZS=F | 1037 | 454 | -0.74 | 342 | +0.13 |
| ZW=F | 1037 | 364 | -1.37 | 384 | +1.40 |
| ^FVX | 1036 | 594 | +0.60 | 177 | +2.05 |
| ^GSPC | 1036 | 815 | +1.06 | 87 | +3.93 |
| ^IRX | 1036 | 533 | +2.38 | 308 | -2.03 |
| ^IXIC | 1036 | 790 | +1.44 | 105 | +4.04 |
| ^TNX | 1036 | 678 | +0.69 | 124 | +2.23 |
| ^TYX | 1036 | 775 | +0.63 | 66 | +2.79 |
| ^VIX | 1038 | 321 | -6.88 | 437 | +6.74 |

The VIX row is a score on the VIX index itself, not a market call. Bearish VIX labels sit after VIX falls, and VIX then tends to spike back, which lifts the pooled Bearish average. That is one driver of the Bearish bounce above, not the whole story: Bearish also beat Bullish on average in Agriculture, Energy, FX and Metals.

## Caveats

- 5y is still short. It covers one rate hiking cycle and the 2022-2026 commodity and equity moves, it does not cover a full cycle.
- Observations overlap in time and across tickers, so counts overstate independent bets. A single market week can appear in many rows at once.
- Returns are pooled across instruments with different volatilities, so averages are dominated by the most volatile names. The median column is the better read for a typical observation.
- No COT positioning, no carry, no options vol, no intraday data in this test. The score is a price-only flag.
- A signal is a flag to look closer, not a buy or sell order, and not investment advice.
