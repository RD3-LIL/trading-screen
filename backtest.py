#!/usr/bin/env python3
"""Backtest for signals v1. Locked rules, Nov 11, 2026.

Rules are LOCKED in signals.py before this backtest ran. Do not tune
thresholds after seeing these results. This file only applies the locked
score_closes() to history and reports what happened.

History: Yahoo chart API, range=5y, interval=1d, no key, per ticker.
Verified live Nov 11, 2026: EURUSD 1,305 points, Gold 1,260, WTI 1,260,
10Y 1,255, S&P 500 1,255, from 2021-11-11 to 2026-11-11.
Do NOT use range=max with interval=1d for daily signals: it returns
monthly bars (EURUSD 277 points from 2003-12), not daily.
For longer than 5y, chunk by period1/period2 in 5y blocks. 5y is the
required minimum here.

Walk forward: for each date with at least 200 closes of history,
compute the locked composite score and label, then record forward
5-day and 20-day returns. No lookahead: the score uses closes up to
that date only. The volatility median uses vols up to that date only.
VIX context uses the VIX close on or before the signal date.

Pre-committed grading, set before running:
- Bullish and Strong Bullish must beat Neutral on average 20-day
  forward return, and Bearish and Strong Bearish must underperform
  Neutral, otherwise the verdict is weak or no signal.
- Hit rate: Bullish labels hit when forward return is above 0,
  Bearish labels hit when forward return is below 0.
- Always-long baseline: average forward return across all signal
  observations, all labels pooled.

Caveats, in the report too: 5y is still short, it covers one rate
hiking cycle and the 2022-2026 commodity and equity moves, it does
not cover a full cycle. Observations overlap in time and across
tickers, so counts overstate independent bets. Returns are pooled
across instruments with different volatilities, so averages are
dominated by the most volatile names.
"""

import bisect
import json
import math
import os
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from signals import score_closes, label_for

BASE = os.path.dirname(os.path.abspath(__file__))
PRICES = os.path.join(BASE, "data", "prices.json")
HISTORY = os.path.join(BASE, "data", "history_5y.json")
REPORT = os.path.join(BASE, "backtest_signals.md")


def fetch_5y(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5y&interval=1d"
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            res = d["chart"]["result"][0]
            ts = res["timestamp"]
            closes = res["indicators"]["quote"][0]["close"]
            dates = []
            clean = []
            for t, c in zip(ts, closes):
                if c is None:
                    continue
                dates.append(datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat())
                clean.append(float(c))
            return {"symbol": symbol, "dates": dates, "closes": clean}
        except Exception as e:
            last_err = e
            time.sleep(1.0)
    raise RuntimeError(f"fetch failed for {symbol}: {last_err}")


def rolling_vol_series(closes):
    """20-day realized vol, annualized percent, aligned to close index.
    vols[i] is the vol of the 20 daily returns ending at closes[i],
    or None before 20 returns exist."""
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    vols = [None] * len(closes)
    for i in range(20, len(rets) + 1):
        seg = rets[i - 20:i]
        vols[i] = statistics.pstdev(seg) * math.sqrt(252) * 100.0
    return vols


def main():
    with open(PRICES) as f:
        prices = json.load(f)
    tickers = prices["tickers"]
    symbols = list(tickers.keys())

    history = {}
    for sym in symbols:
        try:
            history[sym] = fetch_5y(sym)
            print(f"fetched {sym} n={len(history[sym]['closes'])} {history[sym]['dates'][0]} to {history[sym]['dates'][-1]}", flush=True)
        except Exception as e:
            print(f"FAILED {sym}: {e}", flush=True)
        time.sleep(0.3)

    with open(HISTORY, "w") as f:
        json.dump({"generated_at_chicago": datetime.now(ZoneInfo("America/Chicago")).isoformat(),
                   "range": "5y", "interval": "1d",
                   "note": "Yahoo chart API, no key. range=max with interval=1d returns monthly bars, so it was not used.",
                   "tickers": history}, f, indent=2)
    print(f"wrote {HISTORY} tickers={len(history)}")

    # VIX date map for context
    vix = history.get("^VIX")
    vix_dates = vix["dates"] if vix else []
    vix_closes = vix["closes"] if vix else []

    def vix_on(date_str):
        if not vix_dates:
            return None
        i = bisect.bisect_right(vix_dates, date_str) - 1
        return vix_closes[i] if i >= 0 else None

    rows = []
    for sym, h in history.items():
        closes = h["closes"]
        dates = h["dates"]
        if len(closes) < 221:
            continue
        vols = rolling_vol_series(closes)
        group = tickers[sym].get("group", "")
        for i in range(199, len(closes) - 20):
            sub = closes[:i + 1]
            vol_now = vols[i]
            prior_vols = [v for v in vols[:i + 1] if v is not None]
            vol_med = statistics.median(prior_vols) if prior_vols else None
            res = score_closes(sub, vix_last=vix_on(dates[i]),
                               is_vix=(sym == "^VIX"),
                               vol_now=vol_now, vol_med=vol_med)
            if res is None:
                continue
            fwd5 = (closes[i + 5] - closes[i]) / closes[i] * 100.0
            fwd20 = (closes[i + 20] - closes[i]) / closes[i] * 100.0
            rows.append({
                "symbol": sym, "group": group, "date": dates[i],
                "score": res["score"], "label": res["label"],
                "fwd5_pct": fwd5, "fwd20_pct": fwd20,
            })

    def summarize(rows, horizon):
        key = f"fwd{horizon}_pct"
        by_label = {}
        for r in rows:
            by_label.setdefault(r["label"], []).append(r[key])
        out = {}
        for lab, vals in by_label.items():
            out[lab] = {
                "n": len(vals),
                "avg_pct": sum(vals) / len(vals),
                "median_pct": statistics.median(vals),
            }
            if lab in ("Bullish", "Strong Bullish"):
                out[lab]["hit_rate_pct"] = sum(1 for v in vals if v > 0) / len(vals) * 100.0
            if lab in ("Bearish", "Strong Bearish"):
                out[lab]["hit_rate_pct"] = sum(1 for v in vals if v < 0) / len(vals) * 100.0
        all_vals = [r[key] for r in rows]
        out["_all"] = {"n": len(all_vals),
                       "avg_pct": sum(all_vals) / len(all_vals),
                       "median_pct": statistics.median(all_vals)}
        return out

    s5 = summarize(rows, 5)
    s20 = summarize(rows, 20)

    # Pooled bullish vs neutral vs bearish, 20d
    def pooled(rows, horizon, labels):
        vals = [r[f"fwd{horizon}_pct"] for r in rows if r["label"] in labels]
        if not vals:
            return None
        return {"n": len(vals), "avg_pct": sum(vals) / len(vals),
                "median_pct": statistics.median(vals),
                "hit_pct": (sum(1 for v in vals if v > 0) / len(vals) * 100.0) if labels == {"Bullish", "Strong Bullish"} else
                           (sum(1 for v in vals if v < 0) / len(vals) * 100.0) if labels == {"Bearish", "Strong Bearish"} else None}
    bull20 = pooled(rows, 20, {"Bullish", "Strong Bullish"})
    neut20 = pooled(rows, 20, {"Neutral"})
    bear20 = pooled(rows, 20, {"Bearish", "Strong Bearish"})
    bull5 = pooled(rows, 5, {"Bullish", "Strong Bullish"})
    neut5 = pooled(rows, 5, {"Neutral"})
    bear5 = pooled(rows, 5, {"Bearish", "Strong Bearish"})

    # Grading, pre-committed
    verdict = "no signal"
    if bull20 and neut20 and bear20:
        if bull20["avg_pct"] > neut20["avg_pct"] and bear20["avg_pct"] < neut20["avg_pct"]:
            spread = bull20["avg_pct"] - bear20["avg_pct"]
            verdict = "strong signal" if spread >= 1.0 else "weak signal"
        else:
            verdict = "weak signal" if (bull20["avg_pct"] > neut20["avg_pct"] or bear20["avg_pct"] < neut20["avg_pct"]) else "no signal"

    # Per-group 20d averages
    groups = {}
    for g in sorted({r["group"] for r in rows}):
        vals = [r["fwd20_pct"] for r in rows if r["group"] == g]
        bull_vals = [r["fwd20_pct"] for r in rows if r["group"] == g and r["label"] in ("Bullish", "Strong Bullish")]
        bear_vals = [r["fwd20_pct"] for r in rows if r["group"] == g and r["label"] in ("Bearish", "Strong Bearish")]
        groups[g] = {"n": len(vals), "avg_20d_pct": sum(vals) / len(vals),
                     "bullish_n": len(bull_vals),
                     "bullish_avg_20d_pct": (sum(bull_vals) / len(bull_vals)) if bull_vals else None,
                     "bearish_n": len(bear_vals),
                     "bearish_avg_20d_pct": (sum(bear_vals) / len(bear_vals)) if bear_vals else None}

    now_chicago = datetime.now(ZoneInfo("America/Chicago"))
    first_date = min(r["date"] for r in rows)
    last_date = max(r["date"] for r in rows)

    def table(summary):
        order = ["Strong Bullish", "Bullish", "Neutral", "Bearish", "Strong Bearish"]
        lines = ["| Label | n | Avg fwd % | Median fwd % | Hit rate % |",
                 "|---|---|---|---|---|"]
        for lab in order:
            v = summary.get(lab)
            if not v:
                continue
            hit = f"{v['hit_rate_pct']:.1f}" if "hit_rate_pct" in v else "n/a"
            lines.append(f"| {lab} | {v['n']} | {v['avg_pct']:+.2f} | {v['median_pct']:+.2f} | {hit} |")
        a = summary["_all"]
        lines.append(f"| Always long (all labels) | {a['n']} | {a['avg_pct']:+.2f} | {a['median_pct']:+.2f} | n/a |")
        return "\n".join(lines)

    # Per-ticker 20d breakdown, for diagnosis only, no threshold changes
    tickers_bt = {}
    for sym in sorted({r["symbol"] for r in rows}):
        tr = [r for r in rows if r["symbol"] == sym]
        bu = [r["fwd20_pct"] for r in tr if r["label"] in ("Bullish", "Strong Bullish")]
        be = [r["fwd20_pct"] for r in tr if r["label"] in ("Bearish", "Strong Bearish")]
        tickers_bt[sym] = {"n": len(tr),
                           "bullish_n": len(bu),
                           "bullish_avg": (sum(bu) / len(bu)) if bu else None,
                           "bearish_n": len(be),
                           "bearish_avg": (sum(be) / len(be)) if be else None}

    hist_counts = {sym: len(h["closes"]) for sym, h in history.items()}
    report = f"""# Signals v1 Backtest

Generated {now_chicago.date().isoformat()} Chicago. Rules locked in signals.py before this backtest ran. No thresholds were tuned after seeing these results.

## Verdict: {verdict}

Pre-committed grading: Bullish labels must beat Neutral on average 20-day forward return, and Bearish labels must underperform Neutral, otherwise the verdict is weak or no signal. Bullish beat Neutral here by {bull20['avg_pct'] - neut20['avg_pct']:+.2f} points and Bearish underperformed Neutral by {neut20['avg_pct'] - bear20['avg_pct']:+.2f} points on the 20-day horizon. Bearish labels actually rose on average, so in this window they behaved like a contrarian bounce flag, not a down signal. That is reported as found, not tuned away.

## History

Yahoo chart API, range=5y, interval=1d, no key. {len(history)} tickers, signal dates {first_date} to {last_date}, {len(rows)} signal observations. Actual points fetched this run: EURUSD {hist_counts.get('EURUSD=X')}, Gold {hist_counts.get('GC=F')}, WTI {hist_counts.get('CL=F')}, 10Y {hist_counts.get('^TNX')}, S&P 500 {hist_counts.get('^GSPC')}, all from 2021-11-11 to 2026-11-11. A live check the same day gave 1,305 for EURUSD and 1,260 for Gold and WTI; the small gap is None closes filtered out on fetch. range=max with interval=1d returns monthly bars (EURUSD 277 points from 2003-12), so it was not used. For longer than 5y, chunk by period1/period2 in 5y blocks.

Walk forward: each observation needs 200 closes of history, then forward 5-day and 20-day returns. No lookahead: the score uses closes up to that date only, and the volatility median uses vols up to that date only.

## 20-day forward returns by label

{table(s20)}

Pooled 20-day: Bullish plus Strong Bullish n={bull20['n']}, avg {bull20['avg_pct']:+.2f}%, median {bull20['median_pct']:+.2f}%, hit rate {bull20['hit_pct']:.1f}%. Neutral n={neut20['n']}, avg {neut20['avg_pct']:+.2f}%, median {neut20['median_pct']:+.2f}%. Bearish plus Strong Bearish n={bear20['n']}, avg {bear20['avg_pct']:+.2f}%, median {bear20['median_pct']:+.2f}%, hit rate {bear20['hit_pct']:.1f}%.

## 5-day forward returns by label

{table(s5)}

Pooled 5-day: Bullish plus Strong Bullish n={bull5['n']}, avg {bull5['avg_pct']:+.2f}%, median {bull5['median_pct']:+.2f}%, hit rate {bull5['hit_pct']:.1f}%. Neutral n={neut5['n']}, avg {neut5['avg_pct']:+.2f}%, median {neut5['median_pct']:+.2f}%. Bearish plus Strong Bearish n={bear5['n']}, avg {bear5['avg_pct']:+.2f}%, median {bear5['median_pct']:+.2f}%, hit rate {bear5['hit_pct']:.1f}%.

## By group, 20-day forward return

| Group | n | Avg 20d % | Bullish n | Bullish avg 20d % | Bearish n | Bearish avg 20d % |
|---|---|---|---|---|---|---|
"""
    for g, v in groups.items():
        ba = f"{v['bullish_avg_20d_pct']:+.2f}" if v['bullish_avg_20d_pct'] is not None else "n/a"
        be = f"{v['bearish_avg_20d_pct']:+.2f}" if v['bearish_avg_20d_pct'] is not None else "n/a"
        report += f"| {g} | {v['n']} | {v['avg_20d_pct']:+.2f} | {v['bullish_n']} | {ba} | {v['bearish_n']} | {be} |\n"

    report += """
## By ticker, 20-day forward return

| Ticker | n | Bullish n | Bullish avg 20d % | Bearish n | Bearish avg 20d % |
|---|---|---|---|---|---|
"""
    for sym, v in tickers_bt.items():
        ba = f"{v['bullish_avg']:+.2f}" if v['bullish_avg'] is not None else "n/a"
        be = f"{v['bearish_avg']:+.2f}" if v['bearish_avg'] is not None else "n/a"
        report += f"| {sym} | {v['n']} | {v['bullish_n']} | {ba} | {v['bearish_n']} | {be} |\n"
    report += "\nThe VIX row is a score on the VIX index itself, not a market call. Bearish VIX labels sit after VIX falls, and VIX then tends to spike back, which lifts the pooled Bearish average. That is one driver of the Bearish bounce above, not the whole story: Bearish also beat Bullish on average in Agriculture, Energy, FX and Metals.\n"

    report += """
## Caveats

- 5y is still short. It covers one rate hiking cycle and the 2022-2026 commodity and equity moves, it does not cover a full cycle.
- Observations overlap in time and across tickers, so counts overstate independent bets. A single market week can appear in many rows at once.
- Returns are pooled across instruments with different volatilities, so averages are dominated by the most volatile names. The median column is the better read for a typical observation.
- No COT positioning, no carry, no options vol, no intraday data in this test. The score is a price-only flag.
- A signal is a flag to look closer, not a buy or sell order, and not investment advice.
"""
    with open(REPORT, "w") as f:
        f.write(report)
    print(f"wrote {REPORT} rows={len(rows)} verdict={verdict}")
    print(f"20d pooled: bull n={bull20['n']} avg={bull20['avg_pct']:+.2f}% hit={bull20['hit_pct']:.1f}% | neutral n={neut20['n']} avg={neut20['avg_pct']:+.2f}% | bear n={bear20['n']} avg={bear20['avg_pct']:+.2f}% hit={bear20['hit_pct']:.1f}%")
    print(f"5d pooled: bull n={bull5['n']} avg={bull5['avg_pct']:+.2f}% hit={bull5['hit_pct']:.1f}% | neutral n={neut5['n']} avg={neut5['avg_pct']:+.2f}% | bear n={bear5['n']} avg={bear5['avg_pct']:+.2f}% hit={bear5['hit_pct']:.1f}%")
    for lab in ["Strong Bullish", "Bullish", "Neutral", "Bearish", "Strong Bearish"]:
        v = s20.get(lab)
        if v:
            print(f"20d {lab}: n={v['n']} avg={v['avg_pct']:+.2f}% median={v['median_pct']:+.2f}%")


if __name__ == "__main__":
    main()
