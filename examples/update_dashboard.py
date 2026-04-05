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

    megacaps = []
    for t in ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]:
        try:
            q = us_stocks.get_quote(t)
            h = us_stocks.get_history(t, period="1mo", interval="1d")
            chg = q.get("change_pct")
            megacaps.append({
                "ticker": t, "name": q.get("name", ""), "price": q["price"],
                "change_pct": round(chg * 100, 2) if chg else None,
                "market_cap": q.get("market_cap"), "pe": q.get("pe_ratio"),
                "history": h["Close"].tolist(),
                "dates": [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in h.index],
            })
        except Exception:
            pass
    data["megacaps"] = megacaps

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
    data["reddit"] = reddit_data

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
