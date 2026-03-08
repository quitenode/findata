#!/usr/bin/env python3
"""
Crypto market analysis combining ccxt exchange data and CoinGecko metadata.

Usage:
    source ../findata-env/bin/activate
    python analyze_crypto.py                     # BTC overview
    python analyze_crypto.py bitcoin             # specific coin
    python analyze_crypto.py bitcoin ethereum solana   # compare coins
    python analyze_crypto.py --top               # top 20 by market cap
    python analyze_crypto.py --trending          # trending coins
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from findata import crypto
from findata.utils import print_section, df_to_text


COIN_TO_PAIR = {
    "bitcoin": "BTC/USDT",
    "ethereum": "ETH/USDT",
    "solana": "SOL/USDT",
    "ripple": "XRP/USDT",
    "dogecoin": "DOGE/USDT",
    "cardano": "ADA/USDT",
    "avalanche-2": "AVAX/USDT",
    "polkadot": "DOT/USDT",
    "chainlink": "LINK/USDT",
    "litecoin": "LTC/USDT",
}


def analyze_coin(coin_id: str) -> None:
    """Full analysis of a single coin."""
    print(f"\n{'#' * 70}")
    print(f"  CRYPTO ANALYSIS: {coin_id.upper()}")
    print(f"{'#' * 70}")

    # CoinGecko metadata
    print("\n[1/4] Fetching coin info (CoinGecko)...")
    info = crypto.get_coin_info(coin_id)
    print_section("COIN INFO", crypto.format_coin_info(info))

    # Exchange ticker
    pair = COIN_TO_PAIR.get(coin_id, f"{info['symbol']}/USDT")
    print(f"\n[2/4] Fetching exchange ticker ({pair})...")
    try:
        ticker = crypto.get_ticker(pair)
        print_section("EXCHANGE TICKER (OKX)", crypto.format_ticker(ticker))
    except Exception as e:
        print(f"  (Ticker not available: {e})")

    # Order book
    print(f"\n[3/4] Fetching order book ({pair})...")
    try:
        ob = crypto.get_orderbook(pair, limit=5)
        ob_text = (
            f"  Best Bid: ${ob['best_bid']:,.2f}\n"
            f"  Best Ask: ${ob['best_ask']:,.2f}\n"
            f"  Spread:   ${ob['spread']:,.2f}\n\n"
            f"  BIDS:\n{df_to_text(ob['bids'])}\n\n"
            f"  ASKS:\n{df_to_text(ob['asks'])}"
        )
        print_section("ORDER BOOK", ob_text)
    except Exception as e:
        print(f"  (Order book not available: {e})")

    # K-line data (daily, last 30 candles)
    print(f"\n[4/4] Fetching K-line data ({pair}, 1d, last 14)...")
    try:
        ohlcv = crypto.get_ohlcv(pair, timeframe="1d", limit=14)
        print_section("K-LINE DATA (Daily, Last 14)", df_to_text(ohlcv))
    except Exception as e:
        print(f"  (K-line not available: {e})")


def show_top_coins() -> None:
    """Show top coins by market cap."""
    print("\n[Fetching top 20 coins by market cap...]")
    top = crypto.get_top_coins(limit=20)
    print_section("TOP 20 COINS BY MARKET CAP", df_to_text(top))


def show_trending() -> None:
    """Show trending coins on CoinGecko."""
    print("\n[Fetching trending coins...]")
    trending = crypto.get_trending()
    lines = []
    for c in trending:
        lines.append(
            f"  #{c['rank']:<3} {c['name']} ({c['symbol']}) "
            f"-- Market Cap Rank: {c.get('market_cap_rank', 'N/A')}"
        )
    print_section("TRENDING COINS (CoinGecko)", "\n".join(lines))


def compare_coins(coin_ids: list[str]) -> None:
    """Compare multiple coins side by side."""
    print(f"\n{'#' * 70}")
    print(f"  CRYPTO COMPARISON: {', '.join(c.upper() for c in coin_ids)}")
    print(f"{'#' * 70}")

    rows = []
    for coin_id in coin_ids:
        try:
            info = crypto.get_coin_info(coin_id)
            rows.append({
                "Coin": f"{info['name']} ({info['symbol']})",
                "Price": f"${info['price_usd']:,.2f}" if info["price_usd"] else "N/A",
                "24h%": f"{info['change_24h_pct']:.1f}%" if info.get("change_24h_pct") else "N/A",
                "7d%": f"{info['change_7d_pct']:.1f}%" if info.get("change_7d_pct") else "N/A",
                "MktCap": f"${info['market_cap']:,.0f}" if info["market_cap"] else "N/A",
                "Rank": info.get("market_cap_rank", "N/A"),
            })
        except Exception as e:
            rows.append({"Coin": coin_id, "Price": f"Error: {e}"})

    import pandas as pd
    print_section("COMPARISON", df_to_text(pd.DataFrame(rows)))


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if sys.argv[1] == "--top":
        show_top_coins()
    elif sys.argv[1] == "--trending":
        show_trending()
    elif len(sys.argv) > 2:
        compare_coins(sys.argv[1:])
    else:
        analyze_coin(sys.argv[1])

    print(f"\n{'=' * 70}")
    print("  Analysis complete.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
