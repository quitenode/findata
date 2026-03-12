#!/usr/bin/env python3
"""
Daily market prediction generator.
Pulls data from all free sources, computes technicals, and writes reports.

Outputs per-date folder with:
  predictions/2026-03-09/
    report_en.md    (English markdown)
    report_cn.md    (Chinese markdown)
    report_en.pdf   (English PDF)
    report_cn.pdf   (Chinese PDF)

Usage:
    python daily_prediction.py                   # writes to ../predictions/
    python daily_prediction.py /path/to/output/  # custom output dir
"""

import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from findata import us_stocks, crypto, reddit_sentiment as reddit

PT = ZoneInfo("America/Los_Angeles")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "predictions")

SIGNAL_CN = {
    "Bullish": "看涨", "Bearish": "看跌",
    "Lean Bullish": "偏多", "Lean Bearish": "偏空",
    "Neutral": "中性", "N/A": "N/A",
}
WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

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
    now = datetime.now(PT)
    lines = []
    lines.append(f"# Daily Market Prediction -- {now.strftime('%Y-%m-%d (%A)')}")
    lines.append(f"\nGenerated at {now.strftime('%Y-%m-%d %H:%M %Z')}\n")

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


def translate_signal(sig: str) -> str:
    return SIGNAL_CN.get(sig, sig)


def generate_report_cn() -> str:
    """Generate Chinese version of the report."""
    now = datetime.now(PT)
    weekday = WEEKDAY_CN[now.weekday()]
    lines = []
    lines.append(f"# 每日市场预测 -- {now.strftime('%Y-%m-%d')} ({weekday})")
    lines.append(f"\n生成时间: {now.strftime('%Y-%m-%d %H:%M')} 太平洋时间\n")

    # ---- 美股 ----
    lines.append("## 美股市场\n")
    lines.append("### 主要指数\n")
    lines.append("| 代码 | 价格 | 日涨跌 | 5日涨跌 | 10日涨跌 | vs 5日均线 | vs 20日均线 | RSI | 年化波动率 | 信号 |")
    lines.append("|------|------|--------|---------|----------|-----------|------------|-----|----------|------|")

    for ticker in INDICES:
        q = safe_quote(ticker)
        hist = safe_history(ticker)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        sma5_cn = "上方" if tech.get("trend_sma5") == "above" else "下方"
        sma20_cn = "上方" if tech.get("trend_sma20") == "above" else ("下方" if tech.get("trend_sma20") == "below" else "N/A")
        lines.append(
            f"| {ticker} | {fmt(q.get('price'), prefix='$')} "
            f"| {fmt(tech.get('ret_1d'), suffix='%')} "
            f"| {fmt(tech.get('ret_5d'), suffix='%')} "
            f"| {fmt(tech.get('ret_10d'), suffix='%')} "
            f"| {sma5_cn} "
            f"| {sma20_cn} "
            f"| {fmt(tech.get('rsi'), 0)} "
            f"| {fmt(tech.get('volatility'), 1, suffix='%')} "
            f"| **{translate_signal(sig)}** |"
        )

    lines.append("\n### 科技巨头\n")
    lines.append("| 代码 | 价格 | 市值 | 日涨跌 | 5日涨跌 | vs 5日均线 | RSI | 信号 |")
    lines.append("|------|------|------|--------|---------|-----------|-----|------|")

    for ticker in MEGACAPS:
        q = safe_quote(ticker)
        hist = safe_history(ticker)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        mcap = q.get("market_cap")
        mcap_str = f"${mcap/1e12:.2f}万亿" if mcap and mcap > 1e12 else (f"${mcap/1e9:.0f}亿" if mcap else "N/A")
        sma5_cn = "上方" if tech.get("trend_sma5") == "above" else "下方"
        lines.append(
            f"| {ticker} | {fmt(q.get('price'), prefix='$')} "
            f"| {mcap_str} "
            f"| {fmt(tech.get('ret_1d'), suffix='%')} "
            f"| {fmt(tech.get('ret_5d'), suffix='%')} "
            f"| {sma5_cn} "
            f"| {fmt(tech.get('rsi'), 0)} "
            f"| **{translate_signal(sig)}** |"
        )

    # ---- 板块 ----
    lines.append("\n### 板块表现 (5日)\n")
    lines.append("| 板块ETF | 5日涨跌 | 信号 |")
    lines.append("|---------|---------|------|")

    sector_names_cn = {
        "XLE": "能源", "XLF": "金融", "XLK": "科技", "XLV": "医疗",
        "XLI": "工业", "XLC": "通信", "XLP": "必需消费", "XLRE": "房地产",
        "XLU": "公用事业", "XLB": "材料",
    }
    sector_data = []
    for etf in SECTORS:
        hist = safe_history(etf)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        sector_data.append((etf, tech.get("ret_5d"), sig))
    sector_data.sort(key=lambda x: x[1] if x[1] is not None else -999, reverse=True)
    for etf, ret5d, sig in sector_data:
        name_cn = sector_names_cn.get(etf, etf)
        lines.append(f"| {etf} ({name_cn}) | {fmt(ret5d, suffix='%')} | **{translate_signal(sig)}** |")

    # ---- 大宗商品 ----
    lines.append("\n### 大宗商品与避险资产\n")
    lines.append("| 代码 | 价格 | 日涨跌 | 5日涨跌 | 信号 |")
    lines.append("|------|------|--------|---------|------|")

    commodity_names_cn = {"USO": "原油", "GLD": "黄金", "SLV": "白银", "TLT": "长期国债", "UUP": "美元指数"}
    for ticker in COMMODITIES_ETFS:
        q = safe_quote(ticker)
        hist = safe_history(ticker)
        tech = compute_technicals(hist["Close"]) if not hist.empty else {}
        sig = direction_signal(tech)
        name_cn = commodity_names_cn.get(ticker, ticker)
        lines.append(
            f"| {ticker} ({name_cn}) | {fmt(q.get('price'), prefix='$')} "
            f"| {fmt(tech.get('ret_1d'), suffix='%')} "
            f"| {fmt(tech.get('ret_5d'), suffix='%')} "
            f"| **{translate_signal(sig)}** |"
        )

    # ---- 加密货币 ----
    lines.append("\n## 加密货币\n")
    lines.append("| 币种 | 价格 | 24小时涨跌 | 7日涨跌 | 30日涨跌 | 信号 |")
    lines.append("|------|------|-----------|---------|----------|------|")

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
                f"| **{translate_signal(sig)}** |"
            )
        except Exception as e:
            lines.append(f"| {coin_id} | 错误 | | | | {e} |")

    lines.append("\n### 热门币种\n")
    try:
        trending = crypto.get_trending()
        for t in trending[:7]:
            lines.append(f"- #{t['rank']} **{t['name']}** ({t['symbol']}) -- 市值排名 {t.get('market_cap_rank', 'N/A')}")
    except Exception:
        lines.append("- (获取失败)")

    # ---- Reddit舆情 ----
    lines.append("\n## Reddit 舆情\n")
    sub_names_cn = {"wallstreetbets": "华尔街赌场", "stocks": "股票", "investing": "投资"}
    for sub in REDDIT_SUBS:
        try:
            posts = reddit.get_hot_posts(sub, limit=20)
            name_cn = sub_names_cn.get(sub, sub)
            lines.append(f"\n### r/{sub} ({name_cn}) -- 热门帖子\n")
            for _, row in posts.head(5).iterrows():
                flair = f" `{row['flair']}`" if row.get("flair") else ""
                lines.append(f"- [{row['score']:>5} 分] {row['title'][:80]}{flair}")

            tickers = reddit.extract_ticker_mentions(posts, min_mentions=1)
            if not tickers.empty:
                mentions = ", ".join(f"**{r['ticker']}**({r['mentions']})" for _, r in tickers.head(10).iterrows())
                lines.append(f"\n提及股票: {mentions}")
        except Exception:
            lines.append(f"\n### r/{sub}\n\n- (获取失败)")

    # ---- 预测总结 ----
    lines.append("\n## 预测总结\n")

    spy_hist = safe_history("SPY")
    spy_tech = compute_technicals(spy_hist["Close"]) if not spy_hist.empty else {}
    spy_sig = direction_signal(spy_tech)

    lines.append(f"**整体市场信号: {translate_signal(spy_sig)}**\n")
    lines.append("| 资产 | 明日预测 | 下周预测 | 关键价位 |")
    lines.append("|------|---------|---------|---------|")

    if spy_tech:
        spy_support = spy_tech["low_20d"]
        spy_resist = spy_tech["sma20"] if spy_tech["sma20"] else spy_tech["sma5"]
        lines.append(f"| SPY | {translate_signal(spy_sig)} | {translate_signal(spy_sig)} | 支撑: ${spy_support:.2f}, 阻力: ${spy_resist:.2f} |")

    for pair, coin_id in [("BTC/USDT", "bitcoin"), ("ETH/USDT", "ethereum")]:
        try:
            ohlcv = crypto.get_ohlcv(pair, "1d", limit=20)
            tech = compute_technicals(ohlcv["close"])
            sig = direction_signal(tech)
            lines.append(f"| {pair.split('/')[0]} | {translate_signal(sig)} | {translate_signal(sig)} | 支撑: ${tech['low_20d']:,.0f}, 阻力: ${tech['sma20']:,.0f} |")
        except Exception:
            pass

    lines.append("\n### 关键因素\n")

    all_posts = reddit.scan_multiple_subreddits(REDDIT_SUBS, limit_per_sub=15)
    top_titles = " ".join(all_posts["title"].tolist()) if not all_posts.empty else ""

    theme_keywords_cn = {
        "石油/能源": ["oil", "crude", "energy", "OPEC"],
        "战争/地缘政治": ["war", "Iran", "Iraq", "conflict", "sanctions", "missile"],
        "美联储/利率": ["Fed", "rate", "interest", "FOMC", "Powell", "inflation", "CPI"],
        "AI/科技": ["AI", "artificial intelligence", "GPU", "chip", "NVIDIA", "semiconductor"],
        "财报季": ["earnings", "revenue", "EPS", "beat", "miss", "guidance"],
        "经济衰退": ["recession", "crash", "bear", "correction", "downturn"],
        "加密货币上涨": ["bitcoin rally", "crypto surge", "BTC pump", "bull run"],
    }
    themes = []
    for theme, keywords in theme_keywords_cn.items():
        if any(kw.lower() in top_titles.lower() for kw in keywords):
            themes.append(theme)

    if themes:
        for t in themes:
            lines.append(f"- **{t}** 是当前Reddit讨论的主要话题")
    else:
        lines.append("- Reddit舆情中未检测到明显的宏观主题")

    lines.append(f"\n---\n*免责声明: 基于公开数据的自动化分析，不构成投资建议。*\n")

    return "\n".join(lines)


def md_to_pdf(md_text: str, pdf_path: str) -> bool:
    """Convert markdown text to PDF using weasyprint."""
    try:
        import markdown
        from weasyprint import HTML

        html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

        html_full = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&family=Inter:wght@400;600;700&display=swap');
    body {{
        font-family: 'Inter', 'Noto Sans SC', sans-serif;
        font-size: 11px;
        line-height: 1.5;
        color: #1a1a1a;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px 30px;
    }}
    h1 {{ font-size: 20px; border-bottom: 2px solid #333; padding-bottom: 6px; }}
    h2 {{ font-size: 16px; color: #2c3e50; margin-top: 24px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
    h3 {{ font-size: 13px; color: #34495e; margin-top: 16px; }}
    table {{
        border-collapse: collapse;
        width: 100%;
        font-size: 10px;
        margin: 8px 0;
    }}
    th, td {{
        border: 1px solid #ddd;
        padding: 4px 6px;
        text-align: left;
    }}
    th {{ background-color: #f5f5f5; font-weight: 600; }}
    tr:nth-child(even) {{ background-color: #fafafa; }}
    strong {{ color: #c0392b; }}
    ul {{ padding-left: 20px; }}
    li {{ margin: 2px 0; font-size: 10.5px; }}
    code {{ background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 10px; }}
    hr {{ border: none; border-top: 1px solid #ccc; margin: 16px 0; }}
    em {{ font-size: 9px; color: #777; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

        HTML(string=html_full).write_pdf(pdf_path)
        return True
    except Exception as e:
        print(f"  PDF generation failed: {e}")
        return False


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else OUTPUT_DIR

    date_str = datetime.now(PT).strftime("%Y-%m-%d")
    day_dir = os.path.join(output_dir, date_str)
    os.makedirs(day_dir, exist_ok=True)

    # English report
    print(f"[1/4] Generating English report...")
    report_en = generate_report()
    en_md_path = os.path.join(day_dir, f"{date_str}_prediction_en.md")
    with open(en_md_path, "w") as f:
        f.write(report_en)
    print(f"  Saved: {en_md_path}")

    # Chinese report
    print(f"[2/4] Generating Chinese report...")
    report_cn = generate_report_cn()
    cn_md_path = os.path.join(day_dir, f"{date_str}_prediction_cn.md")
    with open(cn_md_path, "w") as f:
        f.write(report_cn)
    print(f"  Saved: {cn_md_path}")

    # English PDF
    print(f"[3/4] Generating English PDF...")
    en_pdf_path = os.path.join(day_dir, f"{date_str}_prediction_en.pdf")
    if md_to_pdf(report_en, en_pdf_path):
        print(f"  Saved: {en_pdf_path}")

    # Chinese PDF
    print(f"[4/4] Generating Chinese PDF...")
    cn_pdf_path = os.path.join(day_dir, f"{date_str}_prediction_cn.pdf")
    if md_to_pdf(report_cn, cn_pdf_path):
        print(f"  Saved: {cn_pdf_path}")

    print(f"\nAll reports saved to: {day_dir}/")


if __name__ == "__main__":
    main()
