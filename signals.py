#!/usr/bin/env python3
"""Signals v1 for the trading screen. Locked rules, Nov 11, 2026.

Deterministic detectors only, stdlib only. No LLM, no invented numbers.
A signal is a systematic flag, not a trade call and not investment advice.

Locked composite, 0-100:
- Trend 40: last vs SMA50 (10), last vs SMA200 (10), SMA50 vs SMA200 (8),
  SMA200 slope over 20 days (6), 20-day breakout (6)
- Momentum 30: 1M return (10), 3M return (10), RSI 14 (10)
- Mean reversion 15: distance from SMA200 (9), Bollinger %B 20d 2sd (6).
  Scored toward neutral when stretched, not toward chasing.
- Volatility and context 15: 20-day realized vol vs its own median (8),
  VIX regime (7). For the VIX ticker itself the second slot uses its own
  vol ratio instead of the VIX level, to avoid self reference.
Labels: Strong Bullish 75+, Bullish 60-74, Neutral 40-59, Bearish 25-39,
Strong Bearish below 25.

Inputs: data/prices.json, 1y daily closes per ticker. Backtest uses the
same score_closes() on 5y history pulled by backtest.py.
No ATR: prices.json has closes only, no high/low series, so ATR is
unavailable and is not scored. That is recorded, not invented.
No COT, no carry: not in the free feed, so not scored.
"""

import json
import math
import os
import statistics
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
PRICES = os.path.join(BASE, "data", "prices.json")
OUT = os.path.join(BASE, "data", "signals.json")


def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains = []
    losses = []
    for i in range(1, n + 1):
        d = closes[-i] - closes[-i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def pct(a, b):
    if b in (None, 0):
        return None
    return (a - b) / abs(b) * 100.0


def fmt(x, decimals=2):
    if x is None:
        return "n/a"
    if abs(x) < 10:
        return f"{x:.4f}" if decimals == 4 else f"{x:.2f}"
    return f"{x:,.2f}"


def fmt_price(x):
    if x is None:
        return "n/a"
    if abs(x) < 10:
        return f"{x:.4f}"
    if abs(x) < 1000:
        return f"{x:.2f}"
    return f"{x:,.2f}"


def label_for(score):
    if score >= 75:
        return "Strong Bullish"
    if score >= 60:
        return "Bullish"
    if score >= 40:
        return "Neutral"
    if score >= 25:
        return "Bearish"
    return "Strong Bearish"


def rolling_vols(closes, window=20):
    vols = []
    rets = []
    for i in range(1, len(closes)):
        rets.append((closes[i] - closes[i - 1]) / closes[i - 1])
    for i in range(window, len(rets) + 1):
        seg = rets[i - window:i]
        if len(seg) >= 2:
            vols.append(statistics.pstdev(seg) * math.sqrt(252) * 100.0)
    return vols


def score_closes(closes, vix_last=None, is_vix=False, vol_now=None, vol_med=None):
    """Score a closes list ending today. Returns dict with components.
    vol_now and vol_med are optional precomputed values, used by the
    backtest to avoid recomputing the full rolling vol series on every
    walk-forward date. When omitted they are computed from closes."""
    if len(closes) < 200:
        return None
    last = closes[-1]
    s50 = sma(closes, 50)
    s200 = sma(closes, 200)
    s200_20 = sma(closes[:-20], 200) if len(closes) >= 220 else None
    r = rsi(closes, 14)
    chg_1m = pct(last, closes[-22]) if len(closes) >= 22 else None
    chg_3m = pct(last, closes[-64]) if len(closes) >= 64 else None
    high_52 = max(closes[-252:])
    low_52 = min(closes[-252:])
    pos_52 = (last - low_52) / (high_52 - low_52) * 100.0 if high_52 != low_52 else 50.0
    dist_200 = pct(last, s200)

    # Bollinger 20d, 2sd
    seg20 = closes[-20:]
    mid20 = sum(seg20) / 20
    sd20 = statistics.pstdev(seg20) if len(seg20) >= 2 else 0.0
    upper = mid20 + 2 * sd20
    lower = mid20 - 2 * sd20
    pct_b = (last - lower) / (upper - lower) if upper != lower else 0.5

    # Trend, 40
    trend = 0
    trend += 10 if last > s50 else 0
    trend += 10 if last > s200 else 0
    trend += 8 if s50 > s200 else 0
    if s200_20 is not None:
        slope = pct(s200, s200_20)
        trend += 6 if slope is not None and slope > 0 else (3 if slope == 0 else 0)
    else:
        trend += 3
    prior20 = closes[-21:-1]
    if last >= max(prior20):
        trend += 6
        breakout = "up"
    elif last <= min(prior20):
        trend += 0
        breakout = "down"
    else:
        trend += 3
        breakout = "none"

    # Momentum, 30
    mom = 0
    if chg_1m is not None:
        mom += 10 if chg_1m >= 3 else (7 if chg_1m >= 0 else (3 if chg_1m >= -3 else 0))
    if chg_3m is not None:
        mom += 10 if chg_3m >= 5 else (7 if chg_3m >= 0 else (3 if chg_3m >= -5 else 0))
    if r is not None:
        mom += 6 if r >= 70 else (10 if r >= 55 else (7 if r >= 45 else (3 if r >= 30 else 0)))

    # Mean reversion, 15, toward neutral when stretched
    mr = 0
    adist = abs(dist_200) if dist_200 is not None else 99.0
    mr += 9 if adist < 2 else (6 if adist < 5 else (3 if adist < 10 else 0))
    mr += 6 if 0.2 <= pct_b <= 0.8 else (3 if 0.0 <= pct_b <= 1.0 else 0)

    # Volatility and context, 15
    if vol_now is None or vol_med is None:
        vols = rolling_vols(closes)
        if vol_now is None:
            vol_now = vols[-1] if vols else None
        if vol_med is None:
            vol_med = statistics.median(vols) if vols else None
    vol_score = 5
    if vol_now is not None and vol_med:
        vol_score = 8 if vol_now <= vol_med else (5 if vol_now <= 1.5 * vol_med else 2)
    if is_vix:
        ctx_score = 7 if vol_now is not None and vol_med and vol_now <= vol_med else (4 if vol_now is not None and vol_med and vol_now <= 1.5 * vol_med else 1)
        ctx_note = "own vol used for context, no self reference to VIX level"
    elif vix_last is not None:
        ctx_score = 7 if vix_last < 20 else (4 if vix_last <= 25 else 1)
        ctx_note = f"VIX {vix_last:.2f}"
    else:
        ctx_score = 4
        ctx_note = "VIX unknown, context neutral"
    volctx = vol_score + ctx_score

    total = trend + mom + mr + volctx
    label = label_for(total)

    # Reasons, weighted, top 3
    reasons = []
    def add(w, text):
        reasons.append((w, text))
    if last > s50 and last > s200:
        add(70, f"Above 50D ({fmt_price(s50)}) and 200D ({fmt_price(s200)})")
    elif last < s50 and last < s200:
        add(70, f"Below 50D ({fmt_price(s50)}) and 200D ({fmt_price(s200)})")
    elif last > s50:
        add(55, f"Above 50D ({fmt_price(s50)}), below 200D ({fmt_price(s200)})")
    else:
        add(55, f"Below 50D ({fmt_price(s50)}), above 200D ({fmt_price(s200)})")
    add(60 if s50 > s200 else 50, "50D above 200D" if s50 > s200 else "50D below 200D")
    if s200_20 is not None:
        slope = pct(s200, s200_20)
        add(45, f"200D {'rising' if slope and slope > 0 else 'falling'} {slope:+.2f}% over 20 days" if slope is not None else "200D slope n/a")
    if breakout == "up":
        add(90, "At 20-day high (breakout up)")
    elif breakout == "down":
        add(90, "At 20-day low (breakout down)")
    if r is not None:
        tag = "overbought" if r >= 70 else ("oversold" if r < 30 else "neutral")
        add(85 if r >= 70 or r < 30 else 50, f"RSI 14 at {r:.1f} ({tag})")
    if chg_1m is not None and chg_3m is not None:
        add(60 if abs(chg_1m) >= 3 or abs(chg_3m) >= 5 else 40,
            f"1M {chg_1m:+.2f}%, 3M {chg_3m:+.2f}%")
    if pos_52 <= 5:
        add(80, f"At {pos_52:.1f}% of 52-week range (near low)")
    elif pos_52 >= 95:
        add(80, f"At {pos_52:.1f}% of 52-week range (near high)")
    else:
        add(35, f"At {pos_52:.1f}% of 52-week range")
    if dist_200 is not None and abs(dist_200) >= 10:
        add(55, f"{dist_200:+.2f}% from 200D (stretched)")
    elif dist_200 is not None:
        add(30, f"{dist_200:+.2f}% from 200D")
    if pct_b < 0 or pct_b > 1:
        add(50, f"Bollinger %B {pct_b:.2f} (outside bands)")
    elif pct_b >= 0.8 or pct_b <= 0.2:
        add(45, f"Bollinger %B {pct_b:.2f} (near band edge)")
    if vol_now is not None and vol_med:
        add(40 if vol_now > 1.5 * vol_med else 25,
            f"20-day vol {vol_now:.1f}% vs median {vol_med:.1f}%")
    if not is_vix and vix_last is not None:
        add(40 if vix_last > 25 else 20, f"VIX {vix_last:.2f} ({ctx_note})")
    reasons.sort(key=lambda x: (-x[0], x[1]))
    top = [t for _, t in reasons[:3]]

    return {
        "score": total,
        "label": label,
        "trend": trend,
        "momentum": mom,
        "mean_reversion": mr,
        "volatility_context": volctx,
        "last": last,
        "sma_50": s50,
        "sma_200": s200,
        "rsi_14": r,
        "chg_1m": chg_1m,
        "chg_3m": chg_3m,
        "pos_52w": pos_52,
        "high_52w": high_52,
        "low_52w": low_52,
        "dist_200_pct": dist_200,
        "bollinger_pct_b": pct_b,
        "breakout_20d": breakout,
        "vol_20d_pct": vol_now,
        "vol_median_pct": vol_med,
        "reasons": top,
    }


def main():
    with open(PRICES) as f:
        data = json.load(f)
    tickers = data["tickers"]
    vix_last = tickers.get("^VIX", {}).get("last")
    out_tickers = {}
    counts = {}
    for sym, t in tickers.items():
        closes = t.get("closes") or []
        if len(closes) < 200:
            continue
        res = score_closes(closes, vix_last=vix_last, is_vix=(sym == "^VIX"))
        if res is None:
            continue
        res.update({
            "symbol": sym,
            "name": t.get("label"),
            "group": t.get("group"),
            "last_date": t.get("last_date"),
        })
        out_tickers[sym] = res
        counts[res["label"]] = counts.get(res["label"], 0) + 1

    def ret_1m(a, b):
        if a is None or b is None:
            return None
        return pct(a["last"], b["last"]) if False else None

    def chg(sym, days):
        t = tickers.get(sym)
        if not t or len(t.get("closes", [])) < days + 1:
            return None
        return pct(t["closes"][-1], t["closes"][-1 - days])

    cross = [
        {"pair": "Gold vs US 10Y yield, 1M",
         "gold_1m_pct": chg("GC=F", 21), "tnx_1m_pct": chg("^TNX", 21),
         "note": "Paired moves for the same window, not causality."},
        {"pair": "WTI vs DXY, 1M",
         "wti_1m_pct": chg("CL=F", 21), "dxy_1m_pct": chg("DX-Y.NYB", 21),
         "note": "Paired moves for the same window, not causality."},
        {"pair": "Copper vs S&P 500, 1M",
         "copper_1m_pct": chg("HG=F", 21), "spx_1m_pct": chg("^GSPC", 21),
         "note": "Paired moves for the same window, not causality."},
    ]

    now_chicago = datetime.now(ZoneInfo("America/Chicago"))
    out = {
        "generated_at_chicago": now_chicago.isoformat(),
        "generated_date_chicago": now_chicago.date().isoformat(),
        "source_date": data.get("generated_date_chicago"),
        "method": "Locked rules Nov 11, 2026: Trend 40, Momentum 30, Mean reversion 15, Volatility and context 15. No ATR (no high/low series in prices.json), no COT, no carry.",
        "note": "A signal is a systematic flag, not a trade call and not investment advice.",
        "counts_by_label": counts,
        "tickers": out_tickers,
        "cross_asset": cross,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {OUT} tickers={len(out_tickers)} counts={counts}")
    for sym in ["EURUSD=X", "GC=F", "CL=F", "DX-Y.NYB", "^GSPC"]:
        r = out_tickers.get(sym)
        if r:
            print(f"{sym} {r['score']} {r['label']} trend={r['trend']} mom={r['momentum']} mr={r['mean_reversion']} vol={r['volatility_context']} reasons={r['reasons']}")


if __name__ == "__main__":
    main()
