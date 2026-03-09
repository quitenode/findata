#!/usr/bin/env python3
"""Regenerate docs/data.json and copy prediction markdowns into docs/ for GitHub Pages."""

import sys
import os
import json
import shutil
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_DIR = os.path.join(os.path.dirname(__file__), "..")
DOCS_DIR = os.path.join(REPO_DIR, "docs")
PRED_DIR = os.path.join(REPO_DIR, "predictions")

from findata import us_stocks, crypto, reddit_sentiment as reddit


def generate_data_json():
    data = {
        "generated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    indices = []
    for t in ["SPY", "QQQ", "DIA", "IWM"]:
        try:
            q = us_stocks.get_quote(t)
            h = us_stocks.get_history(t, period="1mo", interval="1d")
            chg = q.get("change_pct")
            indices.append({
                "ticker": t, "price": q["price"],
                "change_pct": round(chg * 100, 2) if chg else None,
                "history": h["Close"].tolist(),
                "dates": [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in h.index],
            })
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

    commodities = []
    for t, name in [("USO", "Oil"), ("GLD", "Gold"), ("SLV", "Silver"), ("TLT", "Bonds"), ("UUP", "Dollar")]:
        try:
            q = us_stocks.get_quote(t)
            h = us_stocks.get_history(t, period="1mo", interval="1d")
            c = h["Close"]
            ret5 = round((c.iloc[-1] / c.iloc[-6] - 1) * 100, 2) if len(c) >= 6 else None
            commodities.append({
                "ticker": t, "name": name, "price": q["price"], "ret_5d": ret5,
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
    with open(os.path.join(DOCS_DIR, "data.json"), "w") as f:
        json.dump(data, f)
    print(f"  data.json: {len(json.dumps(data))} bytes")

    print("Syncing predictions to docs/...")
    sync_predictions_to_docs()

    print("Dashboard updated.")


if __name__ == "__main__":
    main()
