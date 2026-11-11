#!/usr/bin/env python3
"""Build static index.html for the Trading Screen v1 from data/prices.json."""
import json
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "prices.json"
OUT = ROOT / "index.html"


def fmt(v, digits=2, suffix=""):
    if v is None:
        return "n/a"
    try:
        return f"{float(v):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "n/a"


def pct_fmt(v):
    if v is None:
        return "n/a"
    sign = "+" if v >= 0 else ""
    cls = "pos" if v >= 0 else "neg"
    return f'<span class="{cls}">{sign}{v:.2f}%</span>'


def num(v, digits=2):
    if v is None:
        return "n/a"
    return f"{float(v):,.{digits}f}"


def trend(row):
    last, s50, s200 = row.get("last"), row.get("sma_50"), row.get("sma_200")
    if last is None or s50 is None or s200 is None:
        return "n/a"
    if last > s50 and last > s200:
        return "Above 50D and 200D"
    if last < s50 and last < s200:
        return "Below 50D and 200D"
    if last > s50:
        return "Above 50D, below 200D"
    return "Below 50D, above 200D"


def table(headers, rows):
    th = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>\n"
    return f'<table class="sortable"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def board_rows(data, group):
    rows = []
    for sym, row in data["tickers"].items():
        if row.get("group") != group:
            continue
        status = row.get("status", "")
        badge = ""
        if status in ("stale", "failed"):
            badge = f' <span class="stale">{html.escape(status)}</span>'
        digits = 4 if group == "FX" else 2
        rows.append([
            f"<strong>{html.escape(row.get('label', sym))}</strong>{badge}<br><span class='sym'>{html.escape(sym)}</span>",
            num(row.get("last"), digits),
            pct_fmt(row.get("chg_1d")),
            pct_fmt(row.get("chg_1w")),
            pct_fmt(row.get("chg_1m")),
            pct_fmt(row.get("chg_ytd")),
            num(row.get("pos_52w"), 1) if row.get("pos_52w") is not None else "n/a",
            num(row.get("sma_50"), digits),
            num(row.get("sma_200"), digits),
            num(row.get("rsi_14"), 1) if row.get("rsi_14") is not None else "n/a",
            trend(row),
        ])
    return rows


def main():
    payload = json.loads(DATA.read_text())
    tickers = payload["tickers"]
    gen = payload.get("generated_at_chicago", "")
    gen_date = payload.get("generated_date_chicago", "")
    counts = payload.get("counts", {})

    def get(sym):
        return tickers.get(sym, {})

    # Composite signals v1, from data/signals.json (locked rules in signals.py).
    sig_path = ROOT / "data" / "signals.json"
    sig_rows = []
    sig_note = "Composite signals unavailable in this run (data/signals.json not found)."
    sig_counts = {}
    if sig_path.exists():
        sig = json.loads(sig_path.read_text())
        sig_counts = sig.get("counts_by_label", {})
        sig_note = (
            f"Signals as of {html.escape(str(sig.get('generated_at_chicago', '')))}. "
            "Score 0 to 100: Trend 40, Momentum 30, Mean reversion 15, Volatility and context 15. "
            "Strong Bullish 75 or higher, Bullish 60 to 74, Neutral 40 to 59, Bearish 25 to 39, Strong Bearish below 25. "
            "A signal is a systematic flag to look closer, not a buy or sell call and not investment advice."
        )
        for sym, s in sorted(sig.get("tickers", {}).items(), key=lambda kv: -kv[1].get("score", 0)):
            reasons = "; ".join(s.get("reasons", [])[:3])
            sig_rows.append([
                f"<strong>{html.escape(s.get('name', sym))}</strong><br><span class='sym'>{html.escape(sym)}</span>",
                num(s.get("score"), 0),
                html.escape(s.get("label", "")),
                num(s.get("trend"), 0),
                num(s.get("momentum"), 0),
                num(s.get("mean_reversion"), 0),
                num(s.get("volatility_context"), 0),
                html.escape(reasons),
            ])
    signals_table = table(
        ["Instrument", "Score", "Label", "Trend /40", "Momentum /30", "Mean rev /15", "Vol /15", "Top reasons"],
        sig_rows,
    ) if sig_rows else "<p>Composite signals unavailable in this run.</p>"
    backtest_note = (
        "Backtest, rules locked before testing, 5y daily history, 31,561 observations: "
        "20-day forward return, Bullish labels averaged +0.35% versus Neutral +0.38%, "
        "Bearish labels averaged +1.65%, so Bearish labels rose on average instead of falling. "
        "Verdict: no signal. Bullish did not beat Neutral, and Bearish behaved like a contrarian bounce flag in this window. "
        "Full numbers in backtest_signals.md. No thresholds were tuned after seeing these results."
    )

    # Cross asset snapshot
    snap = []
    for sym in ["DX-Y.NYB", "^GSPC", "^IXIC", "^VIX", "^TNX", "^FVX", "^IRX"]:
        r = get(sym)
        if not r or r.get("status") == "failed":
            snap.append(f"<div class='card'><div class='card-label'>{html.escape(sym)}</div><div class='card-value'>n/a</div><div class='card-sub'>failed to fetch</div></div>")
            continue
        snap.append(
            f"<div class='card'><div class='card-label'>{html.escape(r.get('label', sym))}</div>"
            f"<div class='card-value'>{num(r.get('last'), 2)}</div>"
            f"<div class='card-sub'>1D {pct_fmt(r.get('chg_1d'))} | 1M {pct_fmt(r.get('chg_1m'))} | YTD {pct_fmt(r.get('chg_ytd'))}</div></div>"
        )
    snapshot = "".join(snap)

    # Macro and rates
    tnx, fvx, irx, tyx = get("^TNX"), get("^FVX"), get("^IRX"), get("^TYX")
    slope_10_5 = None
    if tnx.get("last") is not None and fvx.get("last") is not None:
        slope_10_5 = tnx["last"] - fvx["last"]
    slope_30_10 = None
    if tyx.get("last") is not None and tnx.get("last") is not None:
        slope_30_10 = tyx["last"] - tnx["last"]
    fred = payload.get("fred", {})
    fred_rows = []
    labels = {"DGS2": "US 2Y (FRED DGS2)", "DGS10": "US 10Y (FRED DGS10)", "DGS30": "US 30Y (FRED DGS30)",
              "T10YIE": "10Y breakeven inflation (T10YIE)", "CPIAUCSL": "CPI, all items (CPIAUCSL)",
              "FEDFUNDS": "Effective Fed funds (FEDFUNDS)", "DFII10": "Real 10Y yield (DFII10)"}
    for code, label in labels.items():
        f = fred.get(code, {})
        if f.get("status") == "ok":
            fred_rows.append([html.escape(label), num(f.get("value"), 2), html.escape(str(f.get("date", ""))), "ok"])
        else:
            fred_rows.append([html.escape(label), "unavailable", "n/a", f"not fetched: {html.escape(str(f.get('error', 'timeout') or ''))}"])
    fred_table = table(["Series", "Value", "Date", "Status"], fred_rows)

    # US Treasury par yields, the only free source found for the 2Y.
    tsy = payload.get("treasury", {})
    slope_2_10 = None
    if tsy.get("status") == "ok":
        y = tsy.get("yields", {})
        tsy_rows = []
        for tenor in ["1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]:
            if tenor in y:
                tsy_rows.append([html.escape(tenor), num(y[tenor], 2)])
        if "2 Yr" in y and "10 Yr" in y:
            slope_2_10 = y["10 Yr"] - y["2 Yr"]
        tsy_html = table(["Tenor", "Yield %"], tsy_rows)
        tsy_note = f"US Treasury Daily Par Yield Curve Rates, {html.escape(str(tsy.get('date', '')))}. 2Y/10Y slope: {num(slope_2_10, 2)} points."
    else:
        tsy_html = "<p class='warn'>Treasury par yields unavailable in this run. " + html.escape(str(tsy.get("error", ""))) + "</p>"
        tsy_note = "Treasury par yields unavailable in this run, so the 2Y/10Y spread is not shown."

    # Positioning
    cot = payload.get("cot", {})
    if cot.get("status") == "ok" and cot.get("rows"):
        cot_rows = []
        for r in cot["rows"]:
            net = r.get("net_noncommercial")
            cot_rows.append([
                html.escape(r.get("contract", "")),
                num(r.get("noncommercial_long"), 0),
                num(r.get("noncommercial_short"), 0),
                num(net, 0),
                num(r.get("open_interest"), 0),
                html.escape(r.get("source", "")),
            ])
        cot_html = table(["Contract", "Non-commercial long", "Non-commercial short", "Net long minus short", "Open interest", "Source"], cot_rows)
        cot_note = html.escape(cot.get("note", ""))
    else:
        cot_html = "<p class='warn'>Positioning is unavailable in this run. " + html.escape(cot.get("note", "CFTC COT did not load. No numbers have been invented.")) + "</p>"
        cot_note = ""

    # Signals
    ok_rows = [r for r in tickers.values() if r.get("status") == "ok" and r.get("chg_1d") is not None]
    movers = sorted(ok_rows, key=lambda r: abs(r.get("chg_1d") or 0), reverse=True)[:8]
    mover_rows = [[html.escape(r.get("label", "")), pct_fmt(r.get("chg_1d")), pct_fmt(r.get("chg_1w")), pct_fmt(r.get("chg_ytd"))] for r in movers]
    movers_table = table(["Biggest 1D movers", "1D", "1W", "YTD"], mover_rows)
    overbought = [r for r in ok_rows if r.get("rsi_14") is not None and r["rsi_14"] >= 70]
    oversold = [r for r in ok_rows if r.get("rsi_14") is not None and r["rsi_14"] <= 30]
    rsi_rows = []
    for r in sorted(overbought, key=lambda x: -x["rsi_14"]):
        rsi_rows.append([html.escape(r.get("label", "")), num(r.get("rsi_14"), 1), "Overbought (RSI 70 or higher)"])
    for r in sorted(oversold, key=lambda x: x["rsi_14"]):
        rsi_rows.append([html.escape(r.get("label", "")), num(r.get("rsi_14"), 1), "Oversold (RSI 30 or lower)"])
    rsi_table = table(["RSI extremes", "RSI 14", "Read"], rsi_rows) if rsi_rows else "<p>No ticker is at an RSI extreme (70 or higher, 30 or lower) in this run.</p>"
    breaks = [r for r in ok_rows if r.get("pos_52w") is not None and (r["pos_52w"] >= 98 or r["pos_52w"] <= 2)]
    break_rows = [[html.escape(r.get("label", "")), num(r.get("pos_52w"), 1), num(r.get("last"), 2), num(r.get("high_52w"), 2), num(r.get("low_52w"), 2)] for r in breaks]
    break_table = table(["Near 52-week edge", "Position in range", "Last", "52W high", "52W low"], break_rows) if break_rows else "<p>No ticker is within 2 points of its 52-week high or low in this run.</p>"

    # Driver notes, moves only, no causality claimed
    gold, oil, dxy, copper, spx = get("GC=F"), get("CL=F"), get("DX-Y.NYB"), get("HG=F"), get("^GSPC")
    drivers = (
        f"Gold 1M {pct_fmt(gold.get('chg_1m'))} while the US 10Y yield moved {pct_fmt(tnx.get('chg_1m'))} over the same month. "
        f"WTI 1M {pct_fmt(oil.get('chg_1m'))} while DXY moved {pct_fmt(dxy.get('chg_1m'))}. "
        f"Copper 1M {pct_fmt(copper.get('chg_1m'))} while the S and P 500 moved {pct_fmt(spx.get('chg_1m'))}. "
        "These are paired moves for the same window, not proof that one caused the other."
    )

    ecb = payload.get("ecb", {})
    ecb_line = "ECB reference rates unavailable in this run."
    if ecb.get("status") == "ok":
        usd = ecb["rates"].get("USD")
        gbp = ecb["rates"].get("GBP")
        jpy = ecb["rates"].get("JPY")
        ecb_line = f"ECB reference rates, {html.escape(str(ecb.get('date', '')))}: EUR/USD {usd}, EUR/GBP {gbp}, EUR/JPY {jpy}."

    headers = ["Instrument", "Last", "1D", "1W", "1M", "YTD", "52W pos", "50D avg", "200D avg", "RSI 14", "Trend"]
    fx_table = table(headers, board_rows(payload, "FX"))
    energy_table = table(headers, board_rows(payload, "Energy"))
    metals_table = table(headers, board_rows(payload, "Metals"))
    ags_table = table(headers, board_rows(payload, "Agriculture"))
    rates_rows = []
    for sym in ["^IRX", "^FVX", "^TNX", "^TYX"]:
        r = get(sym)
        rates_rows.append([html.escape(r.get("label", sym)), num(r.get("last"), 2), pct_fmt(r.get("chg_1d")), pct_fmt(r.get("chg_1w")), pct_fmt(r.get("chg_1m")), pct_fmt(r.get("chg_ytd")), num(r.get("pos_52w"), 1) if r.get("pos_52w") is not None else "n/a", num(r.get("sma_50"), 2), num(r.get("sma_200"), 2), num(r.get("rsi_14"), 1) if r.get("rsi_14") is not None else "n/a", trend(r)])
    rates_table = table(headers, rates_rows)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trading Screen, FX, Commodities, Macro and Rates</title>
<style>
body {{ background: #0b0f14; color: #d6dde6; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin: 0; padding: 0; }}
header {{ padding: 20px 24px 12px; border-bottom: 1px solid #1e2a38; }}
h1 {{ margin: 0; font-size: 22px; color: #e8eef4; letter-spacing: 1px; }}
.sub {{ color: #8fa3b5; font-size: 13px; margin-top: 6px; }}
main {{ padding: 16px 24px 40px; max-width: 1280px; }}
h2 {{ color: #7fd1ff; font-size: 15px; margin: 28px 0 10px; letter-spacing: 1px; text-transform: uppercase; }}
h3 {{ color: #c8d6e2; font-size: 13px; margin: 18px 0 8px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }}
.card {{ background: #111a24; border: 1px solid #1e2a38; padding: 12px; }}
.card-label {{ color: #8fa3b5; font-size: 11px; text-transform: uppercase; }}
.card-value {{ font-size: 22px; color: #fff; margin: 6px 0; }}
.card-sub {{ font-size: 12px; color: #aebccb; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: #0f1620; }}
th, td {{ padding: 8px 10px; border-bottom: 1px solid #1a2634; text-align: right; white-space: nowrap; }}
th:first-child, td:first-child {{ text-align: left; }}
th {{ color: #8fa3b5; cursor: pointer; }}
tr:hover td {{ background: #141f2c; }}
.pos {{ color: #4ade80; }} .neg {{ color: #f87171; }}
.sym {{ color: #7a8b9c; font-size: 11px; }}
.stale {{ color: #fbbf24; font-size: 11px; }}
.warn {{ background: #2a1e08; border: 1px solid #7a5a12; padding: 12px; color: #fde68a; }}
.note {{ color: #8fa3b5; font-size: 13px; line-height: 1.6; }}
footer {{ border-top: 1px solid #1e2a38; padding: 16px 24px; color: #8fa3b5; font-size: 12px; line-height: 1.7; }}
a {{ color: #7fd1ff; }}
</style>
</head>
<body>
<header>
<h1>TRADING SCREEN</h1>
<div class="sub">FX, commodities, macro and rates. Institutional morning screen from free data only. Not for trading.</div>
<div class="sub">Data as of {html.escape(gen)} Chicago ({html.escape(gen_date)}). Fetched {counts.get('ok', 0)} of {counts.get('total', 0)} tickers ok. Click any column header to sort. Stale rows keep the last good value and are labeled stale.</div>
</header>
<main>
<h2>Cross-asset snapshot</h2>
<div class="cards">{snapshot}</div>
<p class="note">{ecb_line}</p>

<h2>Signals, composite score (v1)</h2>
<p class="note">{sig_note}</p>
{signals_table}
<p class="note"><strong>Counts:</strong> Strong Bullish {sig_counts.get('Strong Bullish', 0)}, Bullish {sig_counts.get('Bullish', 0)}, Neutral {sig_counts.get('Neutral', 0)}, Bearish {sig_counts.get('Bearish', 0)}, Strong Bearish {sig_counts.get('Strong Bearish', 0)}.</p>
<p class="note">{backtest_note}</p>

<h2>FX board, G10</h2>
{fx_table}
<p class="note">Carry: policy rate differentials are not in the free Yahoo feed, so no carry column is shown. Trend is last price versus the 50 day and 200 day averages. 52W pos is where the last price sits in its 52 week range, 0 is the low, 100 is the high.</p>

<h2>Commodities, Energy</h2>
{energy_table}
<h2>Commodities, Metals</h2>
{metals_table}
<h2>Commodities, Agriculture</h2>
{ags_table}
<p class="note">Front month futures only. Curve shape (contango or backwardation) needs the full futures curve, which is not free here.</p>

<h2>Macro and rates</h2>
{rates_table}
<p class="note">Yahoo yields are the primary rates source in this build: 13 week bill, 5Y, 10Y, 30Y. 10Y minus 5Y slope: {num(slope_10_5, 2)} points. 30Y minus 10Y slope: {num(slope_30_10, 2)} points. {tsy_note} FRED was attempted with a 12 second timeout and is shown below, with failures labeled honestly.</p>
<h3>FRED macro series (attempted, may be unavailable)</h3>
{fred_table}
<h3>US Treasury par yields (official, fills the 2Y gap)</h3>
{tsy_html}
<h3>Driver notes (paired moves, not causality)</h3>
<p class="note">{drivers}</p>

<h2>Positioning, CFTC Commitments of Traders</h2>
{cot_html}
<p class="note">{html.escape(cot_note)}</p>

<h2>Signals, movers and extremes</h2>
<h3>Biggest 1 day movers</h3>
{movers_table}
<h3>RSI extremes</h3>
{rsi_table}
<h3>Near 52 week edge</h3>
{break_table}
</main>
<footer>
<p><strong>Sources:</strong> Yahoo Finance chart API (no key, 1 year daily), ECB daily euro reference rates (no key), US Treasury Daily Par Yield Curve Rates (no key), FRED fredgraph.csv (attempted, 12s timeout), CFTC Commitments of Traders weekly text files (FinFutWk.txt for FX, deacom.txt legacy combined for commodities).</p>
<p><strong>Honest limits:</strong> Yahoo is unofficial and indicative, not execution grade. No tick data, no order book, no options volatility surface, no OTC forwards or swaps, no credit spreads at institutional depth. COT is weekly and lagged (Tuesday positions, released Friday). FRED is daily and lagged. Futures are front month only. This screen is a learning exercise, not a trading signal and not investment advice.</p>
<p><strong>How to read it:</strong> start with the snapshot, then check FX and commodities for trend (above or below the 200 day average) and momentum (RSI), then check rates and positioning for context. A signal on this page alone is not a trade.</p>
<p>Built from free data only. Refresh: python3 fetch.py, then python3 signals.py, then python3 build_page.py. Backtest: python3 backtest.py (5y history, rules locked first).</p>
</footer>
<script>
document.querySelectorAll('table.sortable').forEach(function(t){{
  t.querySelectorAll('th').forEach(function(th, idx){{
    th.addEventListener('click', function(){{
      var rows = Array.from(t.querySelectorAll('tbody tr'));
      var asc = th.dataset.asc !== '1';
      th.dataset.asc = asc ? '1' : '0';
      rows.sort(function(a, b){{
        var av = a.cells[idx].textContent.trim().replace(/[%+,]/g, '');
        var bv = b.cells[idx].textContent.trim().replace(/[%+,]/g, '');
        var an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
      rows.forEach(function(r){{ t.querySelector('tbody').appendChild(r); }});
    }});
  }});
}});
</script>
</body>
</html>
"""
    OUT.write_text(page)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    if "\u2014" in page:
        raise SystemExit("em dash found in generated page, fix before calling this done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
