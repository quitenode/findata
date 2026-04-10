#!/usr/bin/env python3
"""Regenerate docs/data.json and copy prediction markdowns into docs/ for GitHub Pages."""

import sys
import os
import json
import math
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PT = ZoneInfo("America/Los_Angeles")

REPO_DIR = os.path.join(os.path.dirname(__file__), "..")
DOCS_DIR = os.path.join(REPO_DIR, "docs")
PRED_DIR = os.path.join(REPO_DIR, "predictions")

import pandas as pd
from findata import us_stocks, crypto, reddit_sentiment as reddit

DATA_JSON_PATH = os.path.join(DOCS_DIR, "data.json")


def sanitize_for_json(obj):
    """Make data RFC 8259–safe: Python json allows NaN/Infinity but browser JSON.parse does not."""
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(x) for x in obj]
    try:
        import numpy as np

        if isinstance(obj, np.ndarray):
            return sanitize_for_json(obj.tolist())
        if isinstance(obj, np.generic):
            return sanitize_for_json(obj.item())
    except ImportError:
        pass
    return obj


def _compute_technicals(closes, highs, lows, volumes):
    """Compute key technical indicators from OHLCV arrays."""
    n = len(closes)
    last = closes[-1]

    def sma(arr, period):
        return sum(arr[-period:]) / period if len(arr) >= period else None

    def ema(arr, period):
        if len(arr) < period:
            return None
        k = 2 / (period + 1)
        e = sum(arr[:period]) / period
        for v in arr[period:]:
            e = v * k + e * (1 - k)
        return e

    sma5 = sma(closes, 5)
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    sma200 = sma(closes, 200)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd = round(ema12 - ema26, 4) if ema12 and ema26 else None

    rsi = None
    if n >= 15:
        changes = [closes[i+1] - closes[i] for i in range(n-1)]
        recent = changes[-14:]
        gains = sum(c for c in recent if c > 0) / 14
        losses = sum(abs(c) for c in recent if c < 0) / 14
        rsi = round(100 - (100 / (1 + gains / losses)), 1) if losses > 0 else 100.0

    avg_vol = sma(volumes, 20)
    vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol and volumes else None

    returns = [(closes[i+1] - closes[i]) / closes[i] for i in range(n-1)]
    vol20 = round((sum(r*r for r in returns[-20:]) / min(20, len(returns))) ** 0.5 * 252**0.5 * 100, 1) if len(returns) >= 5 else None

    bb_upper, bb_lower = None, None
    if n >= 20:
        s20 = closes[-20:]
        mean = sum(s20) / 20
        std = (sum((v - mean)**2 for v in s20) / 20) ** 0.5
        bb_upper = round(mean + 2 * std, 2)
        bb_lower = round(mean - 2 * std, 2)

    high_3m = max(highs) if highs else None
    low_3m = min(lows) if lows else None

    def signal(val, bull_test, bear_test):
        if bull_test:
            return "bullish"
        if bear_test:
            return "bearish"
        return "neutral"

    indicators = {
        "rsi": {"value": rsi, "signal": signal(rsi, rsi and rsi < 30, rsi and rsi > 70)},
        "macd": {"value": macd, "signal": signal(macd, macd and macd > 0, macd and macd < 0)},
        "sma20": {"value": round(sma20, 2) if sma20 else None, "signal": signal(sma20, sma20 and last > sma20, sma20 and last < sma20)},
        "sma50": {"value": round(sma50, 2) if sma50 else None, "signal": signal(sma50, sma50 and last > sma50, sma50 and last < sma50)},
        "sma200": {"value": round(sma200, 2) if sma200 else None, "signal": signal(sma200, sma200 and last > sma200, sma200 and last < sma200)},
        "bollinger": {"upper": bb_upper, "lower": bb_lower, "signal": signal(None, bb_lower and last < bb_lower, bb_upper and last > bb_upper)},
        "volatility": {"value": vol20, "signal": signal(vol20, False, vol20 and vol20 > 40)},
        "volume_ratio": {"value": vol_ratio, "signal": signal(vol_ratio, vol_ratio and vol_ratio > 1.5, vol_ratio and vol_ratio < 0.5)},
        "high_3m": {"value": round(high_3m, 2) if high_3m else None},
        "low_3m": {"value": round(low_3m, 2) if low_3m else None},
    }

    score = 0
    if rsi and rsi < 30: score += 2
    elif rsi and rsi < 45: score += 1
    elif rsi and rsi > 70: score -= 2
    elif rsi and rsi > 55: score -= 1
    if macd and macd > 0: score += 1
    elif macd: score -= 1
    if sma50 and last > sma50: score += 1
    elif sma50: score -= 1
    if sma200 and last > sma200: score += 1
    elif sma200: score -= 1

    overall = "Strong Buy" if score >= 3 else ("Buy" if score >= 1 else ("Strong Sell" if score <= -3 else ("Sell" if score <= -1 else "Neutral")))
    indicators["overall"] = {"label": overall, "score": score}

    return indicators


def _fetch_finviz(ticker):
    """Fetch Seeking Alpha-equivalent data from Finviz (free, no API key)."""
    import re
    _hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get(f"https://finviz.com/quote.ashx?t={ticker}", headers=_hdrs, timeout=10)
    html = r.text
    metrics = {}
    rows = re.findall(r'<tr class="table-dark-row">(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        for i in range(0, len(cells) - 1, 2):
            label = re.sub(r'<[^>]+>', '', cells[i]).strip()
            val = re.sub(r'<[^>]+>', '', cells[i + 1]).strip()
            if label:
                metrics[label] = val

    KEYS = [
        "Recom", "Target Price", "P/E", "Forward P/E", "PEG", "P/S", "P/B",
        "EPS (ttm)", "EPS next Y", "EPS next 5Y", "EPS Q/Q",
        "Insider Own", "Insider Trans", "Inst Own", "Inst Trans",
        "Short Float", "Short Ratio", "Beta",
        "SMA20", "SMA50", "SMA200", "RSI (14)", "Volatility",
        "52W High", "52W Low",
        "Perf Week", "Perf Month", "Perf Quarter", "Perf Half Y", "Perf Year", "Perf YTD",
        "Earnings", "Dividend", "Dividend %",
    ]
    return {k: metrics[k] for k in KEYS if k in metrics}


def generate_data_json():
    data = {
        "generated": datetime.now(PT).strftime("%Y-%m-%d %H:%M %Z"),
        "date": datetime.now(PT).strftime("%Y-%m-%d"),
    }

    INDEX_MAP = [
        ("^DJI",  "DJIA"),
        ("^GSPC", "S&P 500"),
        ("^IXIC", "NASDAQ"),
        ("^RUT",  "RUSS 2K"),
        ("^VIX",  "VIX"),
    ]
    indices = []
    for t, name in INDEX_MAP:
        try:
            q = us_stocks.get_quote(t)
            h = us_stocks.get_history(t, period="1mo", interval="1d")
            chg_pct = q.get("change_pct")
            price = q.get("price")
            prev = q.get("previous_close")
            change_pts = round(price - prev, 2) if price and prev else None
            entry = {
                "ticker": t, "name": name, "price": price,
                "change_pts": change_pts,
                "change_pct": round(chg_pct * 100, 2) if chg_pct else None,
                "previous_close": prev,
                "history": h["Close"].tolist(),
                "dates": [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in h.index],
            }
            if t == "^GSPC":
                entry["ohlc"] = [
                    {
                        "time": str(d.date()) if hasattr(d, "date") else str(d)[:10],
                        "open": row["Open"], "high": row["High"],
                        "low": row["Low"], "close": row["Close"],
                    }
                    for d, row in h.iterrows()
                ]
                entry["volume"] = [
                    {
                        "time": str(d.date()) if hasattr(d, "date") else str(d)[:10],
                        "value": row["Volume"],
                    }
                    for d, row in h.iterrows()
                ]
            indices.append(entry)
        except Exception:
            pass
    data["indices"] = indices

    # ---- All stocks: S&P 500 + Nasdaq 100 (batch fetch) ----
    import io as _io
    MEGACAP_TICKERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]

    all_tickers = set(MEGACAP_TICKERS)
    try:
        import requests as _req
        _hdrs = {"User-Agent": "Mozilla/5.0"}
        r = _req.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=_hdrs, timeout=10)
        sp = pd.read_html(_io.StringIO(r.text))[0]
        all_tickers |= set(sp["Symbol"].str.replace(".", "-", regex=False).tolist())
        r2 = _req.get("https://en.wikipedia.org/wiki/Nasdaq-100", headers=_hdrs, timeout=10)
        ndx_tables = pd.read_html(_io.StringIO(r2.text))
        for _t in ndx_tables:
            if "Ticker" in _t.columns:
                all_tickers |= set(_t["Ticker"].astype(str).str.replace(".", "-", regex=False).tolist())
                break
        print(f"  Universe: {len(all_tickers)} tickers (S&P 500 + Nasdaq 100)")
    except Exception as e:
        print(f"  Warning: could not fetch index constituents: {e}")

    all_tickers = sorted(all_tickers)
    import yfinance as yf

    # Batch download 3-month OHLCV for all tickers
    print(f"  Downloading 3mo history for {len(all_tickers)} tickers...")
    batch_data = yf.download(" ".join(all_tickers), period="3mo", interval="1d", group_by="ticker", progress=False, threads=True)

    # Fetch quotes individually (fast_info) — in batches of Tickers objects
    BATCH_SZ = 50
    all_quotes = {}
    for i in range(0, len(all_tickers), BATCH_SZ):
        chunk = all_tickers[i:i+BATCH_SZ]
        try:
            tks = yf.Tickers(" ".join(chunk))
            for sym in chunk:
                try:
                    fi = tks.tickers[sym].fast_info
                    info = tks.tickers[sym].info
                    all_quotes[sym] = {
                        "price": fi.get("lastPrice"),
                        "previous_close": fi.get("previousClose"),
                        "market_cap": fi.get("marketCap"),
                        "pe": info.get("trailingPE"),
                        "eps": info.get("trailingEps"),
                        "forward_pe": info.get("forwardPE"),
                        "dividend_yield": info.get("dividendYield"),
                        "52w_high": fi.get("yearHigh"),
                        "52w_low": fi.get("yearLow"),
                        "name": info.get("shortName") or info.get("longName", sym),
                        "sector": info.get("sector"),
                        "industry": info.get("industry"),
                    }
                except Exception:
                    pass
        except Exception:
            pass
    print(f"  Quotes fetched: {len(all_quotes)}")

    megacaps = []
    all_stocks = []
    for t in all_tickers:
        try:
            q = all_quotes.get(t)
            if not q or not q.get("price"):
                continue
            # Extract OHLCV from batch data
            if len(all_tickers) > 1 and t in batch_data.columns.get_level_values(0):
                h = batch_data[t].dropna(how="all")
            else:
                h = batch_data.dropna(how="all")
            if h.empty or "Close" not in h.columns:
                continue

            chg_pct = None
            if q["price"] and q.get("previous_close"):
                chg_pct = round((q["price"] / q["previous_close"] - 1) * 100, 2)

            entry = {
                "ticker": t, "name": q.get("name", ""), "price": q["price"],
                "change_pct": chg_pct,
                "market_cap": q.get("market_cap"), "pe": q.get("pe"),
                "eps": q.get("eps"), "forward_pe": q.get("forward_pe"),
                "dividend_yield": q.get("dividend_yield"),
                "52w_high": q.get("52w_high"), "52w_low": q.get("52w_low"),
                "sector": q.get("sector"), "industry": q.get("industry"),
                "history": h["Close"].dropna().tolist()[-22:],
                "dates": [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in h.index][-22:],
            }

            closes = h["Close"].dropna().tolist()
            highs = h["High"].dropna().tolist()
            lows = h["Low"].dropna().tolist()
            volumes = h["Volume"].dropna().tolist()
            if len(closes) >= 14:
                entry["technicals"] = _compute_technicals(closes, highs, lows, volumes)

            all_stocks.append(entry)

            if t in MEGACAP_TICKERS:
                mega_entry = dict(entry)
                try:
                    news_items = us_stocks.get_news(t)
                    mega_entry["news"] = news_items[:8]
                except Exception:
                    mega_entry["news"] = []
                try:
                    ar = us_stocks.get_analyst_ratings(t)
                    mega_entry["analyst"] = {
                        "target_mean": ar.get("target_mean"),
                        "target_high": ar.get("target_high"),
                        "target_low": ar.get("target_low"),
                        "recommendation": ar.get("recommendation"),
                        "num_analysts": ar.get("num_analysts"),
                    }
                except Exception:
                    pass
                try:
                    mega_entry["finviz"] = _fetch_finviz(t)
                except Exception:
                    pass
                megacaps.append(mega_entry)
        except Exception:
            pass

    megacaps.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)
    data["megacaps"] = megacaps
    data["all_stocks"] = all_stocks
    print(f"  Stocks: {len(all_stocks)} total, {len(megacaps)} mega-caps with news")

    sector_names = {
        "XLE": "Energy", "XLF": "Finance", "XLK": "Tech", "XLV": "Healthcare",
        "XLI": "Industrial", "XLC": "Comm", "XLP": "Staples", "XLRE": "RealEstate",
        "XLU": "Utilities", "XLB": "Materials",
    }
    sectors = []
    for t, name in sector_names.items():
        try:
            h = us_stocks.get_history(t, period="1mo", interval="1d")
            c = h["Close"]
            ret5 = round((c.iloc[-1] / c.iloc[-6] - 1) * 100, 2) if len(c) >= 6 else None
            sectors.append({"ticker": t, "name": name, "ret_5d": ret5})
        except Exception:
            pass
    sectors.sort(key=lambda x: x.get("ret_5d") or -999, reverse=True)
    data["sectors"] = sectors

    # ---- CNN Fear & Greed Index (real data from CNN API) ----
    try:
        import requests as _req
        _cnn_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": "https://www.cnn.com/markets/fear-and-greed",
            "Accept": "application/json",
        }
        r = _req.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                      headers=_cnn_headers, timeout=10)
        r.raise_for_status()
        cnn = r.json()
        fg = cnn["fear_and_greed"]
        score = round(fg["score"])
        rating = fg["rating"].title()

        # Extract 7 component indicators from the response
        components = []
        component_map = {
            "market_momentum_sp500": "Market Momentum",
            "stock_price_strength": "Stock Price Strength",
            "stock_price_breadth": "Stock Price Breadth",
            "put_call_options": "Put & Call Options",
            "market_volatility_vix": "Market Volatility",
            "safe_haven_demand": "Safe Haven Demand",
            "junk_bond_demand": "Junk Bond Demand",
        }
        for key, name in component_map.items():
            comp = cnn.get(key, {})
            if isinstance(comp, dict) and "score" in comp:
                components.append({
                    "name": name,
                    "desc": comp.get("rating", "").title(),
                    "score": round(comp["score"]),
                })

        data["fear_greed"] = {
            "score": score,
            "rating": rating,
            "previous_close": fg.get("previous_close"),
            "previous_1_week": fg.get("previous_1_week"),
            "previous_1_month": fg.get("previous_1_month"),
            "previous_1_year": fg.get("previous_1_year"),
            "components": components,
            "source": "CNN",
        }
        print(f"  Fear & Greed (CNN): {score} ({rating})")
    except Exception as e:
        print(f"  Warning: CNN Fear & Greed failed ({e}), skipping")

    COMMODITY_MAP = [
        ("CL=F",     "WTI Crude",       "/bbl"),
        ("GC=F",     "Gold",            "/oz"),
        ("SI=F",     "Silver",          "/oz"),
        ("^TNX",     "10Y Yield",       "%"),
        ("DX-Y.NYB", "US Dollar Index", ""),
    ]
    commodities = []
    for t, name, unit in COMMODITY_MAP:
        try:
            q = us_stocks.get_quote(t)
            h = us_stocks.get_history(t, period="1mo", interval="1d")
            c = h["Close"]
            price = q.get("price")
            prev = q.get("previous_close")
            change_pts = round(price - prev, 2) if price and prev else None
            ret5 = round((c.iloc[-1] / c.iloc[-6] - 1) * 100, 2) if len(c) >= 6 else None
            commodities.append({
                "ticker": t, "name": name, "unit": unit, "price": price,
                "change_pts": change_pts,
                "change_pct": round((price / prev - 1) * 100, 2) if price and prev else None,
                "ret_5d": ret5,
                "history": c.tolist(),
                "dates": [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in h.index],
            })
        except Exception:
            pass
    data["commodities"] = commodities

    cryptos = []
    for coin_id, pair in [("bitcoin", "BTC/USDT"), ("ethereum", "ETH/USDT"), ("solana", "SOL/USDT")]:
        try:
            info = crypto.get_coin_info(coin_id)
            ohlcv = crypto.get_ohlcv(pair, "1d", limit=30)
            cryptos.append({
                "id": coin_id, "symbol": info["symbol"], "price": info["price_usd"],
                "change_24h": info.get("change_24h_pct"), "change_7d": info.get("change_7d_pct"),
                "market_cap": info.get("market_cap"),
                "history": ohlcv["close"].tolist(),
                "dates": [str(d)[:10] for d in ohlcv.index],
            })
        except Exception:
            pass
    data["crypto"] = cryptos

    # Crypto on-chain indicators — computed from free APIs
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from fetch_crypto_indicators import fetch_all
        print("  Fetching BTC on-chain indicators from APIs...")
        ci = fetch_all()
        today = datetime.now(PT).strftime("%Y-%m-%d")
        for ind in ci:
            ind["date"] = today
        data["crypto_indicators"] = ci
        print(f"  {len(ci)} indicators computed")
    except Exception as e:
        print(f"  Warning: failed to compute crypto indicators: {e}")

    reddit_data = []
    for sub in ["wallstreetbets", "stocks", "investing"]:
        try:
            posts = reddit.get_hot_posts(sub, limit=10)
            items = [
                {"title": r["title"][:100], "score": int(r["score"]),
                 "comments": int(r["num_comments"]), "flair": r.get("flair", ""),
                 "url": r.get("url", "")}
                for _, r in posts.head(7).iterrows()
            ]
            tickers = reddit.extract_ticker_mentions(posts, min_mentions=1)
            mentions = [{"ticker": r["ticker"], "count": int(r["mentions"])} for _, r in tickers.head(10).iterrows()]
            reddit_data.append({"subreddit": sub, "posts": items, "ticker_mentions": mentions})
        except Exception:
            pass
    if reddit_data:
        data["reddit"] = reddit_data
    else:
        # Preserve existing reddit data from data.json (Reddit blocks datacenter IPs)
        try:
            if os.path.isfile(DATA_JSON_PATH):
                with open(DATA_JSON_PATH) as _f:
                    existing = json.load(_f)
                data["reddit"] = existing.get("reddit", [])
                if data["reddit"]:
                    print("  Reddit: kept existing data (live fetch failed)")
        except Exception:
            data["reddit"] = []

    reports = []
    if os.path.isdir(PRED_DIR):
        for d in sorted(os.listdir(PRED_DIR), reverse=True):
            dp = os.path.join(PRED_DIR, d)
            if os.path.isdir(dp):
                files = sorted(os.listdir(dp))
                reports.append({"date": d, "files": files})
    data["reports"] = reports

    return data


def sync_predictions_to_docs():
    """Copy prediction markdown files into docs/predictions/ for GitHub Pages."""
    docs_pred = os.path.join(DOCS_DIR, "predictions")
    if os.path.isdir(PRED_DIR):
        for d in os.listdir(PRED_DIR):
            src = os.path.join(PRED_DIR, d)
            dst = os.path.join(docs_pred, d)
            if os.path.isdir(src):
                os.makedirs(dst, exist_ok=True)
                for f in os.listdir(src):
                    if f.endswith(".md"):
                        shutil.copy2(os.path.join(src, f), os.path.join(dst, f))


def main():
    os.makedirs(DOCS_DIR, exist_ok=True)

    print("Generating data.json...")
    data = generate_data_json()

    # Avoid replacing a good snapshot with an empty one when Yahoo blocks CI (rate limit / datacenter).
    if len(data.get("indices") or []) == 0 and len(data.get("megacaps") or []) == 0:
        if os.path.isfile(DATA_JSON_PATH):
            print(
                "WARNING: No US equity data from Yahoo; leaving existing docs/data.json unchanged.",
                file=sys.stderr,
            )
        else:
            print("ERROR: No equity data and no existing data.json to fall back on.", file=sys.stderr)
            sys.exit(1)
    else:
        clean = sanitize_for_json(data)
        with open(DATA_JSON_PATH, "w") as f:
            json.dump(clean, f, allow_nan=False)
        print(f"  data.json: {len(json.dumps(clean, allow_nan=False))} bytes")

    print("Syncing predictions to docs/...")
    sync_predictions_to_docs()

    print("Dashboard updated.")


if __name__ == "__main__":
    main()
