#!/usr/bin/env python3
"""Fetch free market data for the Trading Screen v1.

Primary source: Yahoo Finance chart API, no key.
Secondary: ECB daily FX reference rates, no key.
Attempted with short timeouts and graceful fallback: FRED fredgraph.csv,
CFTC COT text file. If they fail, they are labeled unavailable, never faked.

Writes data/prices.json. Keeps last good data labeled stale on failure.
Uses stdlib only, no yfinance.
"""
import json
import math
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUT = DATA_DIR / "prices.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# label, group, Yahoo symbol
TICKERS = [
    # FX, G10 majors and crosses
    ("EUR/USD", "FX", "EURUSD=X"),
    ("GBP/USD", "FX", "GBPUSD=X"),
    ("USD/JPY", "FX", "USDJPY=X"),
    ("USD/CHF", "FX", "USDCHF=X"),
    ("AUD/USD", "FX", "AUDUSD=X"),
    ("USD/CAD", "FX", "USDCAD=X"),
    ("NZD/USD", "FX", "NZDUSD=X"),
    ("EUR/GBP", "FX", "EURGBP=X"),
    ("EUR/JPY", "FX", "EURJPY=X"),
    ("GBP/JPY", "FX", "GBPJPY=X"),
    # Commodities, Energy
    ("WTI Crude", "Energy", "CL=F"),
    ("Brent Crude", "Energy", "BZ=F"),
    ("Natural Gas", "Energy", "NG=F"),
    # Metals
    ("Gold", "Metals", "GC=F"),
    ("Silver", "Metals", "SI=F"),
    ("Copper", "Metals", "HG=F"),
    ("Platinum", "Metals", "PL=F"),
    # Agriculture
    ("Corn", "Agriculture", "ZC=F"),
    ("Wheat", "Agriculture", "ZW=F"),
    ("Soybeans", "Agriculture", "ZS=F"),
    ("Coffee", "Agriculture", "KC=F"),
    ("Sugar", "Agriculture", "SB=F"),
    # Cross asset and rates, Yahoo yields are the primary rates source
    ("Dollar Index (DXY)", "Cross-asset", "DX-Y.NYB"),
    ("S&P 500", "Cross-asset", "^GSPC"),
    ("Nasdaq Composite", "Cross-asset", "^IXIC"),
    ("VIX", "Cross-asset", "^VIX"),
    ("US 13-Week Bill", "Rates", "^IRX"),
    ("US 5-Year Yield", "Rates", "^FVX"),
    ("US 10-Year Yield", "Rates", "^TNX"),
    ("US 30-Year Yield", "Rates", "^TYX"),
]

FRED_SERIES = ["DGS2", "DGS10", "DGS30", "T10YIE", "CPIAUCSL", "FEDFUNDS", "DFII10"]
# Legacy COT, futures-only columns (0-indexed): 7 open interest, 8 non-commercial
# long, 9 non-commercial short. Verified Nov 11 against the downloaded files:
# total long equals NC long plus spreading plus commercial long, and total
# long plus nonreportable long equals open interest (within a few contracts
# of CFTC rounding). Both files use the same legacy layout, so one parser
# serves both. FinFutWk is financial futures only (FX here). deacom is the
# legacy combined file, which holds the commodities. The plain NYMEX WTI
# futures line is not in deacom, so WTI uses the ICE Europe light sweet
# line and NatGas uses Henry Hub, both labeled as such on the page.
COT_FILES = [
    ("FinFutWk.txt", "https://www.cftc.gov/dea/newcot/FinFutWk.txt", {
        "EURO FX - CHICAGO MERCANTILE EXCHANGE": "EUR",
        "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE": "GBP",
        "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE": "JPY",
        "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "CAD",
        "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE": "CHF",
        "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "AUD",
    }),
    ("deacom.txt", "https://www.cftc.gov/dea/newcot/deacom.txt", {
        "GOLD - COMMODITY EXCHANGE INC.": "Gold",
        "SILVER - COMMODITY EXCHANGE INC.": "Silver",
        "COPPER- #1 - COMMODITY EXCHANGE INC.": "Copper",
        "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE": "WTI (ICE Europe)",
        "HENRY HUB - NEW YORK MERCANTILE EXCHANGE": "NatGas (Henry Hub)",
        "CORN - CHICAGO BOARD OF TRADE": "Corn",
        "WHEAT-SRW - CHICAGO BOARD OF TRADE": "Wheat (SRW)",
        "SOYBEANS - CHICAGO BOARD OF TRADE": "Soybeans",
    }),
]


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100.0


def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi14(closes):
    if len(closes) < 15:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:14]) / 14.0
    avg_loss = sum(losses[:14]) / 14.0
    for i in range(14, len(gains)):
        avg_gain = (avg_gain * 13.0 + gains[i]) / 14.0
        avg_loss = (avg_loss * 13.0 + losses[i]) / 14.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def fetch_yahoo(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
    raw = fetch_url(url, timeout=15)
    d = json.loads(raw)
    result = d["chart"]["result"][0]
    meta = result.get("meta", {})
    stamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    pairs = []
    for ts, c in zip(stamps, closes):
        if c is not None and math.isfinite(c):
            pairs.append((ts, float(c)))
    if len(pairs) < 30:
        raise ValueError(f"only {len(pairs)} closes for {symbol}")
    dates = [datetime.fromtimestamp(ts, tz=timezone.utc).date() for ts, _ in pairs]
    vals = [c for _, c in pairs]
    last = vals[-1]
    last_date = dates[-1].isoformat()
    year = dates[-1].year
    ytd_base = None
    for dt, v in zip(dates, vals):
        if dt.year == year:
            ytd_base = v
            break
    def ago(n):
        return vals[-1 - n] if len(vals) > n else None
    high52 = meta.get("fiftyTwoWeekHigh") or max(vals)
    low52 = meta.get("fiftyTwoWeekLow") or min(vals)
    pos52 = None
    if high52 and low52 and high52 != low52:
        pos52 = (last - low52) / (high52 - low52) * 100.0
    return {
        "symbol": symbol,
        "last": last,
        "last_date": last_date,
        "currency": meta.get("currency"),
        "long_name": meta.get("longName") or meta.get("shortName") or symbol,
        "chg_1d": pct(last, ago(1)),
        "chg_1w": pct(last, ago(5)),
        "chg_1m": pct(last, ago(21)),
        "chg_3m": pct(last, ago(63)),
        "chg_ytd": pct(last, ytd_base),
        "high_52w": high52,
        "low_52w": low52,
        "pos_52w": pos52,
        "sma_50": sma(vals, 50),
        "sma_200": sma(vals, 200),
        "rsi_14": rsi14(vals),
        "closes": vals[-260:],
        "dates": [d.isoformat() for d in dates[-260:]],
        "status": "ok",
    }


def fetch_ecb():
    raw = fetch_url("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=15)
    root = ET.fromstring(raw)
    ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    rates = {}
    date = None
    for cube in root.findall(".//e:Cube[@time]", ns):
        date = cube.get("time")
        for child in cube.findall("e:Cube", ns):
            rates[child.get("currency")] = float(child.get("rate"))
    if not rates:
        raise ValueError("no ECB rates parsed")
    return {"date": date, "rates": rates, "status": "ok"}


def fetch_fred(series):
    # Short timeout only. FRED timed out twice from this VM on Nov 11, so
    # any failure here is expected and must not block the Yahoo data.
    try:
        raw = fetch_url(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", timeout=12)
    except Exception as e:
        return {"series": series, "status": "unavailable", "error": str(e)[:120]}
    lines = [l for l in raw.strip().splitlines() if l and not l.startswith("DATE")]
    if not lines:
        return {"series": series, "status": "unavailable", "error": "empty csv"}
    last = lines[-1].split(",")
    if len(last) < 2 or last[1] in ("", "."):
        return {"series": series, "status": "unavailable", "error": "no value in last row"}
    try:
        return {"series": series, "status": "ok", "date": last[0], "value": float(last[1])}
    except ValueError:
        return {"series": series, "status": "unavailable", "error": "unparsable value"}


def _parse_cot_line(parts, strict=True):
    # parts is one csv-parsed COT row. Returns a dict or None.
    # Fields 7/8/9 are open interest, non-commercial long, non-commercial
    # short in both legacy files, verified Nov 11: values are plausible and
    # in the same direction as the combined file. deacom also satisfies the
    # total identity (total long at 13 equals NC long plus spreading plus
    # commercial long, total long plus nonreportable long equals OI, within
    # a few contracts of CFTC rounding), so it gets the strict check.
    # FinFutWk does NOT satisfy that identity: its post-commercial columns
    # 13-19 are extra fields (totals sit at 20-23 and do reconcile with OI,
    # but the long categories do not sum to them), so it gets bounds only.
    # Do not tighten this without first identifying columns 13-19.
    try:
        oi = int(float(parts[7]))
        longs = int(float(parts[8]))
        shorts = int(float(parts[9]))
        spread = int(float(parts[10]))
        comm_long = int(float(parts[11]))
        total_long = int(float(parts[13]))
        nonrep_long = int(float(parts[15]))
    except (ValueError, IndexError):
        return None
    if oi <= 0 or longs < 0 or shorts < 0 or longs > oi or shorts > oi:
        return None
    if strict:
        if abs(total_long - (longs + spread + comm_long)) > 5:
            return None
        if abs((total_long + nonrep_long) - oi) > 5:
            return None
    return {"open_interest": oi, "noncommercial_long": longs,
            "noncommercial_short": shorts,
            "net_noncommercial": longs - shorts}


def fetch_cot():
    # Earlier failure was two bugs, both fixed Nov 11 on retry: the CFTC
    # 403 was transient (same URL returns 200 now, even with the old UA),
    # and the parser used line.startswith(name) on lines that start with a
    # quote, so no contract ever matched. Now csv-parsed with exact names.
    rows = []
    dates = []
    errors = []
    import csv as _csv
    import io as _io
    for fname, url, targets in COT_FILES:
        try:
            raw = fetch_url(url, timeout=30)
        except Exception as e:
            errors.append(f"{fname}: {e}"[:160])
            continue
        strict = (fname == "deacom.txt")
        for line in raw.splitlines():
            row = next(_csv.reader(_io.StringIO(line)), None)
            if not row or len(row) < 17:
                continue
            label = targets.get(row[0])
            if not label:
                continue
            parsed = _parse_cot_line(row, strict=strict)
            if not parsed:
                continue
            parsed["contract"] = label
            parsed["source"] = fname
            parsed["report_date"] = row[2]
            dates.append(row[2])
            rows.append(parsed)
    if not rows:
        return {"status": "unavailable",
                "error": "; ".join(errors)[:200] if errors else "no contracts parsed",
                "note": "CFTC COT files did not load or no contracts parsed. Positioning is shown as unavailable, no numbers invented.",
                "rows": []}
    return {"status": "ok",
            "report_date": max(dates) if dates else None,
            "note": f"Weekly COT, Tuesday positions, released Friday. Net is non-commercial longs minus shorts. Report date {max(dates) if dates else 'n/a'}. FX rows are legacy financial futures, commodity rows are the legacy combined file.",
            "rows": rows}


def fetch_treasury(chicago_month):
    # US Treasury Daily Par Yield Curve Rates, no key. The TextView page is
    # HTML, not a clean CSV (the yield.csv URL 404s), so parse the table
    # whose header row contains "10 Yr", map columns by header, and take
    # the last dated row. Sanity: yields must be between 2 and 8 percent.
    # This is the only free source found for the 2Y yield, which Yahoo
    # does not carry, so it unlocks the 2Y/10Y spread.
    import re
    url = ("https://home.treasury.gov/resource-center/data-chart-center/"
           "interest-rates/TextView?type=daily_treasury_yield_curve"
           f"&field_tdr_date_value_month={chicago_month}")
    try:
        raw = fetch_url(url, timeout=30)
    except Exception as e:
        return {"status": "unavailable", "error": str(e)[:160]}
    header = None
    last = None
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", raw, re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(1), re.S)]
        if not cells:
            continue
        if "10 Yr" in cells and "2 Yr" in cells:
            header = cells
            continue
        if header and re.match(r"\d{2}/\d{2}/\d{4}", cells[0] or ""):
            try:
                vals = {h: float(cells[i]) for i, h in enumerate(header)
                        if i < len(cells) and h in ("1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr")}
            except ValueError:
                continue
            if "10 Yr" in vals and 2.0 <= vals["10 Yr"] <= 8.0:
                last = {"date": cells[0], "yields": vals}
    if not last:
        return {"status": "unavailable", "error": "no parseable yield row"}
    return {"status": "ok", "date": last["date"], "yields": last["yields"]}


def main():
    now_utc = datetime.now(timezone.utc)
    chicago = now_utc.astimezone(ZoneInfo("America/Chicago"))
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text()).get("tickers", {})
        except Exception:
            previous = {}
    tickers = {}
    ok = failed = 0
    for label, group, symbol in TICKERS:
        try:
            row = fetch_yahoo(symbol)
            row["label"] = label
            row["group"] = group
            tickers[symbol] = row
            ok += 1
            print(f"ok {symbol} {label} {row['last']} ({row['last_date']})")
        except Exception as e:
            failed += 1
            print(f"FAIL {symbol} {label}: {e}")
            prev = previous.get(symbol)
            if prev:
                prev = dict(prev)
                prev["status"] = "stale"
                prev["error"] = str(e)[:160]
                tickers[symbol] = prev
            else:
                tickers[symbol] = {"label": label, "group": group, "symbol": symbol, "status": "failed", "error": str(e)[:160]}
        time.sleep(0.25)
    try:
        ecb = fetch_ecb()
        print(f"ok ECB {ecb['date']} USD {ecb['rates'].get('USD')}")
    except Exception as e:
        print(f"FAIL ECB: {e}")
        ecb = {"status": "unavailable", "error": str(e)[:160]}
    fred = {}
    for s in FRED_SERIES:
        fred[s] = fetch_fred(s)
        print(f"fred {s}: {fred[s].get('status')} {fred[s].get('value')}")
    cot = fetch_cot()
    print(f"cot: {cot.get('status')} rows={len(cot.get('rows', []))}")
    treasury = fetch_treasury(chicago.strftime("%Y%m"))
    print(f"treasury: {treasury.get('status')} {treasury.get('date')} {treasury.get('yields')}")
    payload = {
        "generated_at_utc": now_utc.isoformat(),
        "generated_at_chicago": chicago.isoformat(),
        "generated_date_chicago": chicago.date().isoformat(),
        "tickers": tickers,
        "ecb": ecb,
        "fred": fred,
        "cot": cot,
        "treasury": treasury,
        "counts": {"ok": ok, "failed": failed, "total": len(TICKERS)},
        "sources": {
            "yahoo": "Yahoo Finance chart API, no key, range 1y daily. Unofficial and indicative, not execution grade.",
            "ecb": "ECB daily euro reference rates, no key.",
            "fred": "FRED fredgraph.csv, attempted with 12s timeout. Timed out from this VM on Nov 11, 2026 (curl HTTP 000, three variants), so Yahoo yields are the primary rates source. The FRED API needs a free 32-character key.",
            "cot": "CFTC Commitments of Traders, free weekly text files: FinFutWk.txt for FX, deacom.txt (legacy combined) for commodities. Retried Nov 11: both return HTTP 200; the earlier 403 was transient and the parser bug (startswith on quoted lines) is fixed.",
            "treasury": "US Treasury Daily Par Yield Curve Rates TextView page, no key. The yield.csv URL 404s, the HTML table parses cleanly and is the only free source found for the 2Y yield.",
        },
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"wrote {OUT} ok={ok} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
