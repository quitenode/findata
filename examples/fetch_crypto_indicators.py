#!/usr/bin/env python3
"""
Fetch BTC on-chain indicators from free public APIs.
Outputs JSON to stdout or writes to docs/data.json (crypto_indicators field).

No API keys required. Sources: CoinGecko, alternative.me, yfinance, computed.
"""

import json
import math
import sys
import time
from datetime import datetime

import requests
import yfinance as yf


def fetch_all():
    indicators = []
    btc_price = None
    btc_mcap = None

    def add(name, value, link="", signal=""):
        indicators.append({"name": name, "value": str(value), "link": link, "signal": signal})

    # --- BTC Price ---
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=false&developer_data=false",
            timeout=10,
        )
        d = r.json()["market_data"]
        btc_price = d["current_price"]["usd"]
        btc_mcap = d["market_cap"]["usd"]
        chg24 = d.get("price_change_percentage_24h", 0)
        chg7 = d.get("price_change_percentage_7d", 0)
        add("BTC Price", f"${btc_price:,.0f}", signal="neutral")
        add("24h Change", f"{chg24:+.2f}%", signal="bullish" if chg24 > 0 else "bearish")
        add("7d Change", f"{chg7:+.2f}%", signal="bullish" if chg7 > 0 else "bearish")
    except Exception as e:
        print(f"  BTC price: {e}", file=sys.stderr)

    time.sleep(0.5)

    # --- BTC + ETH Dominance ---
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        g = r.json()["data"]
        btc_dom = g["market_cap_percentage"]["btc"]
        eth_dom = g["market_cap_percentage"]["eth"]
        total_mcap = g["total_market_cap"]["usd"]
        add("BTC Dominance", f"{btc_dom:.1f}%",
            link="https://www.tradingview.com/symbols/CRYPTOCAP-BTC.D/",
            signal="bullish" if btc_dom > 55 else ("bearish" if btc_dom < 40 else "neutral"))
        add("BTC+ETH Dominance", f"{btc_dom + eth_dom:.1f}%",
            link="https://btctools.io/stats/dominance")
        add("Total Crypto MCap", f"${total_mcap / 1e12:.2f}T")
    except Exception as e:
        print(f"  Dominance: {e}", file=sys.stderr)

    time.sleep(0.5)

    # --- Crypto Fear & Greed ---
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10)
        data = r.json()["data"]
        cur = data[0]
        prev = data[1] if len(data) > 1 else {}
        val = int(cur["value"])
        sig = "bearish" if val < 25 else ("bullish" if val > 75 else "neutral")
        add("Fear & Greed Index", f"{val} ({cur['value_classification']})",
            link="https://alternative.me/crypto/fear-and-greed-index/", signal=sig)
    except Exception as e:
        print(f"  Fear&Greed: {e}", file=sys.stderr)

    # --- BTC technicals from yfinance ---
    try:
        h = yf.Ticker("BTC-USD").history(period="2y", interval="1d")
        c = h["Close"].dropna()
        price = c.iloc[-1]
        if btc_price is None:
            btc_price = price

        # SMA
        sma50 = c.tail(50).mean()
        sma200 = c.tail(200).mean() if len(c) >= 200 else None
        sma111 = c.tail(111).mean() if len(c) >= 111 else None
        sma350 = c.tail(350).mean() if len(c) >= 350 else None
        add("SMA 50", f"${sma50:,.0f}", signal="bullish" if price > sma50 else "bearish")
        if sma200:
            add("SMA 200", f"${sma200:,.0f}", signal="bullish" if price > sma200 else "bearish")

        # RSI 14
        changes = [c.iloc[i + 1] - c.iloc[i] for i in range(len(c) - 1)]
        recent14 = changes[-14:]
        gains = sum(x for x in recent14 if x > 0) / 14
        losses = sum(abs(x) for x in recent14 if x < 0) / 14
        rsi = round(100 - (100 / (1 + gains / losses)), 1) if losses > 0 else 100
        sig = "bearish" if rsi > 70 else ("bullish" if rsi < 30 else "neutral")
        add("RSI (14d)", str(rsi),
            link="https://www.cryptowaves.app/relative-strength-index/BTC", signal=sig)

        # 60-day cumulative return
        if len(c) >= 61:
            ret60 = round((c.iloc[-1] / c.iloc[-61] - 1) * 100, 2)
            add("60d Cumulative Return", f"{ret60:+.2f}%",
                link="https://www.aicoin.com/chart/i:btc60dds:aicoin?lang=zh",
                signal="bullish" if ret60 > 20 else ("bearish" if ret60 < -20 else "neutral"))

        # Pi Cycle Top: 111 DMA crosses 350 DMA x 2
        if sma111 and sma350:
            sma350x2 = sma350 * 2
            crossed = sma111 > sma350x2
            add("Pi Cycle Top", "CROSSED — Top Signal!" if crossed else f"Not crossed (111DMA: {sma111:,.0f} < 350DMAx2: {sma350x2:,.0f})",
                link="https://www.lookintobitcoin.com/charts/pi-cycle-top-indicator/",
                signal="bearish" if crossed else "bullish")

        # 2-Year MA Multiplier
        sma730 = c.tail(min(730, len(c))).mean()
        if price > sma730 * 5:
            ma2y = "Near top band — extreme caution"
            sig = "bearish"
        elif price > sma730:
            ma2y = f"Above 2Y MA (${sma730:,.0f})"
            sig = "bullish"
        else:
            ma2y = f"Below 2Y MA (${sma730:,.0f})"
            sig = "neutral"
        add("2-Year MA Multiplier", ma2y,
            link="https://decentrader.com/charts/bitcoin-investor-tool-2-year-ma-multiplier/", signal=sig)

        # ahr999 approximation
        if sma200:
            genesis = datetime(2009, 1, 3)
            days_age = (datetime.now() - genesis).days
            predicted = 10 ** (5.84 * math.log10(days_age) - 17.01)
            if predicted > 0:
                ahr999 = round((price / sma200) * (price / predicted), 3)
                sig = "bullish" if ahr999 < 0.45 else ("bearish" if ahr999 > 1.2 else "neutral")
                add("ahr999 Index", str(ahr999), signal=sig)

        # Puell Multiple approximation
        daily_coins = 3.125 * 144
        avg_365 = c.tail(365).mean() if len(c) >= 365 else c.mean()
        puell = round((daily_coins * price) / (daily_coins * avg_365), 2)
        sig = "bullish" if puell < 0.5 else ("bearish" if puell > 3 else "neutral")
        add("Puell Multiple", str(puell),
            link="https://www.lookintobitcoin.com/charts/puell-multiple/", signal=sig)

        # 200-Week MA Heatmap
        hw = yf.Ticker("BTC-USD").history(period="5y", interval="1wk")
        cw = hw["Close"].dropna()
        if len(cw) >= 200:
            sma200w = cw.tail(200).mean()
            ratio = price / sma200w
            if ratio > 3:
                hm = "Red (Overheated)"
                sig = "bearish"
            elif ratio > 2:
                hm = "Orange"
                sig = "bearish"
            elif ratio > 1.5:
                hm = "Yellow"
                sig = "neutral"
            elif ratio > 1:
                hm = "Blue"
                sig = "bullish"
            else:
                hm = "Purple (Undervalued)"
                sig = "bullish"
            add("200W MA Heatmap", f"{hm} ({ratio:.2f}x)",
                link="https://www.lookintobitcoin.com/charts/200-week-moving-average-heatmap/", signal=sig)

        # 1Y Holder % approximation — use 1Y return as proxy for conviction
        if len(c) >= 365:
            ret1y = (price / c.iloc[-365] - 1) * 100
            holder_proxy = "Strong hands" if ret1y < 20 else "Distribution likely"
            add("1Y Return (holder proxy)", f"{ret1y:+.1f}%",
                link="https://www.lookintobitcoin.com/charts/1-year-hodl-wave/")

        # Unrealized Profit/Loss — approximate from price vs SMA
        if sma200:
            upl = round((price - sma200) / sma200 * 100, 1)
            sig = "bearish" if upl > 60 else ("bullish" if upl < 0 else "neutral")
            add("Unrealized P/L (approx)", f"{upl:+.1f}%",
                link="https://www.lookintobitcoin.com/charts/relative-unrealized-profit--loss/", signal=sig)

    except Exception as e:
        print(f"  BTC technicals: {e}", file=sys.stderr)

    # --- USD Index ---
    try:
        usd = yf.Ticker("DX-Y.NYB").fast_info.get("lastPrice")
        sig = "bullish" if usd < 100 else ("bearish" if usd > 105 else "neutral")
        add("USD Index (DXY)", f"{usd:.2f}",
            link="https://www.cnbc.com/quotes/.DXY", signal=sig)
    except Exception as e:
        print(f"  USD: {e}", file=sys.stderr)

    # --- CNY ---
    try:
        cny = yf.Ticker("CNY=X").fast_info.get("lastPrice")
        add("USD/CNY", f"{cny:.4f}")
    except Exception as e:
        print(f"  CNY: {e}", file=sys.stderr)

    # --- MSTR Premium ---
    try:
        tk = yf.Ticker("MSTR")
        mstr_mcap = tk.fast_info.get("marketCap")
        btc_held = 553555  # approximate as of early 2026
        btc_val = btc_held * btc_price if btc_price else 0
        if mstr_mcap and btc_val:
            prem = round(mstr_mcap / btc_val, 2)
            add("MSTR NAV Premium", f"{prem}x",
                link="https://www.mstr-tracker.com/",
                signal="bullish" if prem > 2 else ("bearish" if prem < 1.2 else "neutral"))
    except Exception as e:
        print(f"  MSTR: {e}", file=sys.stderr)

    # --- Halving ---
    halving = datetime(2024, 4, 19)
    days_since = (datetime.now() - halving).days
    next_halving = datetime(2028, 3, 15)
    days_to = (next_halving - datetime.now()).days
    add("Halving Cycle", f"Day {days_since} post-halving ({days_to} days to next)",
        signal="neutral")

    # --- CBBI approximation ---
    # CBBI combines multiple indicators; rough weighted average
    cbbi_score = 50
    component_count = 0
    if rsi:
        cbbi_score += (rsi - 50) * 0.3
        component_count += 1
    if puell:
        cbbi_score += (puell - 1) * 15
        component_count += 1
    if ahr999:
        cbbi_score += (ahr999 - 0.8) * 20
        component_count += 1
    cbbi_est = max(0, min(100, round(cbbi_score)))
    add("CBBI (estimated)", str(cbbi_est),
        link="https://colintalkscrypto.com/cbbi/",
        signal="bearish" if cbbi_est > 90 else ("bullish" if cbbi_est < 30 else "neutral"))

    # --- BTC ETF Flow (placeholder — no free API) ---
    add("BTC ETF Flow", "See Dune dashboard",
        link="https://dune.com/hildobby/btc-etfs", signal="neutral")

    # --- Alt Season Index (placeholder) ---
    if btc_dom:
        alt_est = max(0, min(100, round(100 - btc_dom * 1.5)))
        add("Alt Season (est.)", str(alt_est),
            link="https://www.blockchaincenter.net/en/altcoin-season-index/",
            signal="bearish" if alt_est > 75 else ("bullish" if alt_est < 25 else "neutral"))

    return indicators


def main():
    print("Fetching BTC on-chain indicators...", file=sys.stderr)
    indicators = fetch_all()
    print(f"  {len(indicators)} indicators computed", file=sys.stderr)

    if "--json" in sys.argv:
        print(json.dumps(indicators, indent=2))
    else:
        for ind in indicators:
            sig = ind.get("signal", "")
            mark = {"bullish": "+", "bearish": "-", "neutral": "="}.get(sig, " ")
            print(f"  [{mark}] {ind['name']:30s}  {ind['value']}")


if __name__ == "__main__":
    main()
