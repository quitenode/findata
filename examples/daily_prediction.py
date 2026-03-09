#!/usr/bin/env python3
"""
Daily market prediction generator.
Pulls data from all free sources, computes technicals, and writes a markdown report.

Usage:
    python daily_prediction.py                   # writes to ../predictions/
    python daily_prediction.py /path/to/output/  # custom output dir
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from findata import us_stocks, crypto, reddit_sentiment as reddit


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "predictions")

INDICES = ["SPY", "QQQ", "DIA", "IWM"]
MEGACAPS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]
SECTORS = ["XLE", "XLF", "XLK", "XLV", "XLI", "XLC", "XLP", "XLRE", "XLU", "XLB"]
COMMODITIES_ETFS = ["USO", "GLD", "SLV", "TLT", "UUP"]
CRYPTO_COINS = ["bitcoin", "ethereum", "solana"]
CRYPTO_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
REDDIT_SUBS = ["wallstreetbets", "stocks", "investing"]


def safe_quote(ticker):
    try:
        return us_stocks.get_quote(ticker)
    except Exception as e:
        return {"ticker": ticker, "price": None, "error": str(e)}


def safe_history(ticker, period="1mo", interval="1d"):
    try:
        return us_stocks.get_history(ticker, period=period, interval=interval)
    except Exception:
        return pd.DataFrame()


def compute_technicals(closes: pd.Series) -> dict:
    if closes is None or len(closes) < 5:
        return {}
    last = closes.iloc[-1]
    sma5 = closes.tail(5).mean()
    sma10 = closes.tail(10).mean() if len(closes) >= 10 else None
    sma20 = closes.mean() if len(closes) >= 15 else None
    daily_ret = closes.pct_change().dropna()
    vol = daily_ret.std() * (252 ** 0.5) * 100 if len(daily_ret) > 2 else None

    ret_1d = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100 if len(closes) >= 2 else None
    ret_5d = (closes.iloc[-1] / closes.iloc[-6] - 1) * 100 if len(closes) >= 6 else None
    ret_10d = (closes.iloc[-1] / closes.iloc[-11] - 1) * 100 if len(closes) >= 11 else None

    trend_sma5 = "above" if last > sma5 else "below"
    trend_sma20 = "above" if sma20 and last > sma20 else ("below" if sma20 else "N/A")

    # Simple RSI (14-period)
    rsi = None
    if len(daily_ret) >= 14:
        gains = daily_ret.clip(lower=0).tail(14).mean()
        losses = (-daily_ret.clip(upper=0)).tail(14).mean()
        if losses > 0:
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))

    return {
        "last": last,
        "sma5": sma5,
        "sma20": sma20,
        "trend_sma5": trend_sma5,
        "trend_sma20": trend_sma20,
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "ret_10d": ret_10d,
        "volatility": vol,
        "rsi": rsi,
        "high_20d": closes.max(),
        "low_20d": closes.min(),
    }


def direction_signal(tech: dict) -> str:
    """Heuristic direction signal based on technicals."""
    if not tech:
        return "N/A"
    score = 0
    if tech.get("trend_sma5") == "above":
        score += 1
    else:
        score -= 1
    if tech.get("trend_sma20") == "above":
        score += 1
    else:
        score -= 1
    if tech.get("ret_5d") is not None:
        if tech["ret_5d"] > 1:
            score += 1
        elif tech["ret_5d"] < -1:
            score -= 1
    if tech.get("rsi") is not None:
        if tech["rsi"] > 70:
            score -= 1
        elif tech["rsi"] < 30:
            score += 1

    if score >= 2:
        return "Bullish"
    elif score <= -2:
        return "Bearish"
    elif score > 0:
        return "Lean Bullish"
    elif score < 0:
        return "Lean Bearish"
    return "Neutral"


def fmt(val, decimals=2, prefix="", suffix=""):
    if val is None:
        return "N/A"
    return f"{prefix}{val:,.{decimals}f}{suffix}"


def generate_report() -> str:
    now = datetime.utcnow()
    lines = []
    lines.append(f"# Daily Market Prediction -- {now.strftime('%Y-%m-%d (%A)')}")
    lines.append(f"\nGenerated at {now.strftime('%Y-%m-%d %H:%M UTC')}\n")

    # ---- US EQUITIES ----
    lines.append("## US Equities\n")
    lines.append("### Indices\n")
    lines.append("| Ticker | Price | 1d% | 5d% | 10d% | vs SMA5 | vs SMA20 | RSI | Vol(ann) | Signal |")
    lines.append("|--------|-------|-----|-----|------|---------|----------|-----|----------|--------|")

    for ticker in INDICES:
        q = safe_quote(ticker)
        hist = safe_history(ticker)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        lines.append(
            f"| {ticker} | {fmt(q.get('price'), prefix='$')} "
            f"| {fmt(tech.get('ret_1d'), suffix='%')} "
            f"| {fmt(tech.get('ret_5d'), suffix='%')} "
            f"| {fmt(tech.get('ret_10d'), suffix='%')} "
            f"| {tech.get('trend_sma5', 'N/A')} "
            f"| {tech.get('trend_sma20', 'N/A')} "
            f"| {fmt(tech.get('rsi'), 0)} "
            f"| {fmt(tech.get('volatility'), 1, suffix='%')} "
            f"| **{sig}** |"
        )

    lines.append("\n### Mega-Caps\n")
    lines.append("| Ticker | Price | MktCap | 1d% | 5d% | vs SMA5 | RSI | Signal |")
    lines.append("|--------|-------|--------|-----|-----|---------|-----|--------|")

    for ticker in MEGACAPS:
        q = safe_quote(ticker)
        hist = safe_history(ticker)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        mcap = q.get("market_cap")
        mcap_str = f"${mcap/1e12:.2f}T" if mcap and mcap > 1e12 else (f"${mcap/1e9:.0f}B" if mcap else "N/A")
        lines.append(
            f"| {ticker} | {fmt(q.get('price'), prefix='$')} "
            f"| {mcap_str} "
            f"| {fmt(tech.get('ret_1d'), suffix='%')} "
            f"| {fmt(tech.get('ret_5d'), suffix='%')} "
            f"| {tech.get('trend_sma5', 'N/A')} "
            f"| {fmt(tech.get('rsi'), 0)} "
            f"| **{sig}** |"
        )

    # ---- SECTORS ----
    lines.append("\n### Sector Performance (5-day)\n")
    lines.append("| Sector | 5d% | Signal |")
    lines.append("|--------|-----|--------|")

    sector_data = []
    for etf in SECTORS:
        hist = safe_history(etf)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        sector_data.append((etf, tech.get("ret_5d"), sig))

    sector_data.sort(key=lambda x: x[1] if x[1] is not None else -999, reverse=True)
    for etf, ret5d, sig in sector_data:
        lines.append(f"| {etf} | {fmt(ret5d, suffix='%')} | **{sig}** |")

    # ---- COMMODITIES ----
    lines.append("\n### Commodities & Safe Havens\n")
    lines.append("| Ticker | Price | 1d% | 5d% | Signal |")
    lines.append("|--------|-------|-----|-----|--------|")

    for ticker in COMMODITIES_ETFS:
        q = safe_quote(ticker)
        hist = safe_history(ticker)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        lines.append(
            f"| {ticker} | {fmt(q.get('price'), prefix='$')} "
            f"| {fmt(tech.get('ret_1d'), suffix='%')} "
            f"| {fmt(tech.get('ret_5d'), suffix='%')} "
            f"| **{sig}** |"
        )

    # ---- CRYPTO ----
    lines.append("\n## Crypto\n")
    lines.append("| Coin | Price | 24h% | 7d% | 30d% | Signal |")
    lines.append("|------|-------|------|-----|------|--------|")

    for coin_id in CRYPTO_COINS:
        try:
            info = crypto.get_coin_info(coin_id)
            ohlcv = crypto.get_ohlcv(
                {"bitcoin": "BTC/USDT", "ethereum": "ETH/USDT", "solana": "SOL/USDT"}[coin_id],
                "1d", limit=20,
            )
            tech = compute_technicals(ohlcv["close"]) if not ohlcv.empty else {}
            sig = direction_signal(tech)
            lines.append(
                f"| {info['symbol']} | {fmt(info['price_usd'], prefix='$')} "
                f"| {fmt(info.get('change_24h_pct'), suffix='%')} "
                f"| {fmt(info.get('change_7d_pct'), suffix='%')} "
                f"| {fmt(info.get('change_30d_pct'), suffix='%')} "
                f"| **{sig}** |"
            )
        except Exception as e:
            lines.append(f"| {coin_id} | Error | | | | {e} |")

    lines.append("\n### Trending Coins\n")
    try:
        trending = crypto.get_trending()
        for t in trending[:7]:
            lines.append(f"- #{t['rank']} **{t['name']}** ({t['symbol']}) -- MCap Rank {t.get('market_cap_rank', 'N/A')}")
    except Exception:
        lines.append("- (failed to fetch trending)")

    # ---- REDDIT SENTIMENT ----
    lines.append("\n## Reddit Sentiment\n")

    for sub in REDDIT_SUBS:
        try:
            posts = reddit.get_hot_posts(sub, limit=20)
            lines.append(f"\n### r/{sub} -- Top Posts\n")
            for _, row in posts.head(5).iterrows():
                flair = f" `{row['flair']}`" if row.get("flair") else ""
                lines.append(f"- [{row['score']:>5} pts] {row['title'][:80]}{flair}")

            tickers = reddit.extract_ticker_mentions(posts, min_mentions=1)
            if not tickers.empty:
                mentions = ", ".join(f"**{r['ticker']}**({r['mentions']})" for _, r in tickers.head(10).iterrows())
                lines.append(f"\nTicker mentions: {mentions}")
        except Exception:
            lines.append(f"\n### r/{sub}\n\n- (failed to fetch)")

    # ---- PREDICTION SUMMARY ----
    lines.append("\n## Prediction Summary\n")

    spy_hist = safe_history("SPY")
    spy_tech = compute_technicals(spy_hist["Close"]) if not spy_hist.empty else {}
    spy_sig = direction_signal(spy_tech)

    lines.append(f"**Overall Market Signal: {spy_sig}**\n")
    lines.append("| Asset | Tomorrow | Next Week | Key Levels |")
    lines.append("|-------|----------|-----------|------------|")

    if spy_tech:
        spy_support = spy_tech["low_20d"]
        spy_resist = spy_tech["sma20"] if spy_tech["sma20"] else spy_tech["sma5"]
        lines.append(f"| SPY | {spy_sig} | {spy_sig} | Support: ${spy_support:.2f}, Resist: ${spy_resist:.2f} |")

    for pair, coin_id in [("BTC/USDT", "bitcoin"), ("ETH/USDT", "ethereum")]:
        try:
            ohlcv = crypto.get_ohlcv(pair, "1d", limit=20)
            tech = compute_technicals(ohlcv["close"])
            sig = direction_signal(tech)
            lines.append(f"| {pair.split('/')[0]} | {sig} | {sig} | Support: ${tech['low_20d']:,.0f}, Resist: ${tech['sma20']:,.0f} |")
        except Exception:
            pass

    lines.append("\n### Key Factors\n")

    # Auto-detect themes from Reddit
    all_posts = reddit.scan_multiple_subreddits(REDDIT_SUBS, limit_per_sub=15)
    top_titles = " ".join(all_posts["title"].tolist()) if not all_posts.empty else ""

    themes = []
    theme_keywords = {
        "oil": ["oil", "crude", "energy", "OPEC"],
        "war/geopolitics": ["war", "Iran", "Iraq", "conflict", "sanctions", "missile"],
        "Fed/rates": ["Fed", "rate", "interest", "FOMC", "Powell", "inflation", "CPI"],
        "AI/tech": ["AI", "artificial intelligence", "GPU", "chip", "NVIDIA", "semiconductor"],
        "earnings": ["earnings", "revenue", "EPS", "beat", "miss", "guidance"],
        "recession": ["recession", "crash", "bear", "correction", "downturn"],
        "crypto rally": ["bitcoin rally", "crypto surge", "BTC pump", "bull run"],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw.lower() in top_titles.lower() for kw in keywords):
            themes.append(theme)

    if themes:
        for t in themes:
            lines.append(f"- **{t}** is a dominant theme in current Reddit discussion")
    else:
        lines.append("- No dominant macro theme detected in Reddit sentiment")

    lines.append(f"\n---\n*Disclaimer: Automated analysis based on public data. Not financial advice.*\n")

    return "\n".join(lines)


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating daily prediction report...")
    report = generate_report()

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"{date_str}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w") as f:
        f.write(report)

    print(f"Report saved to: {filepath}")
    print(f"Length: {len(report)} chars, {report.count(chr(10))} lines")


if __name__ == "__main__":
    main()
