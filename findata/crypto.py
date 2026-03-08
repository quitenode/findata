"""Crypto market data via ccxt (exchange data) and pycoingecko (coin metadata).

No API keys required for public data.
ccxt: real-time tickers, K-lines, orderbooks from 100+ exchanges.
pycoingecko: coin info, market caps, trending, categories.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import ccxt
import pandas as pd
from pycoingecko import CoinGeckoAPI

from .utils import fmt_currency, fmt_number, fmt_percent

_cg = CoinGeckoAPI()

DEFAULT_EXCHANGE = "okx"

_exchange_cache: dict[str, ccxt.Exchange] = {}


def _get_exchange(name: str = DEFAULT_EXCHANGE) -> ccxt.Exchange:
    if name not in _exchange_cache:
        cls = getattr(ccxt, name, None)
        if cls is None:
            raise ValueError(f"Unknown exchange: {name}. Available: {ccxt.exchanges[:20]}...")
        _exchange_cache[name] = cls()
    return _exchange_cache[name]


# ---------------------------------------------------------------------------
# ccxt: exchange-level data
# ---------------------------------------------------------------------------

def get_ticker(
    symbol: str = "BTC/USDT",
    exchange: str = DEFAULT_EXCHANGE,
) -> dict:
    """Get real-time ticker for a trading pair.

    Args:
        symbol: Trading pair, e.g. 'BTC/USDT', 'ETH/USDT'.
        exchange: Exchange name (okx, bybit, kraken, coinbase, etc.)
    """
    ex = _get_exchange(exchange)
    t = ex.fetch_ticker(symbol)
    return {
        "symbol": t["symbol"],
        "exchange": exchange,
        "last": t["last"],
        "bid": t["bid"],
        "ask": t["ask"],
        "high": t["high"],
        "low": t["low"],
        "volume": t["baseVolume"],
        "quote_volume": t["quoteVolume"],
        "change_pct": t["percentage"],
        "vwap": t.get("vwap"),
        "timestamp": t["datetime"],
    }


def get_tickers(
    symbols: list[str] | None = None,
    exchange: str = DEFAULT_EXCHANGE,
) -> pd.DataFrame:
    """Batch fetch tickers for multiple pairs.

    If symbols is None, fetches all available tickers (can be slow).
    """
    ex = _get_exchange(exchange)
    if symbols:
        tickers = {s: ex.fetch_ticker(s) for s in symbols}
    else:
        tickers = ex.fetch_tickers()

    rows = []
    for sym, t in tickers.items():
        rows.append({
            "symbol": sym,
            "last": t["last"],
            "change%": t.get("percentage"),
            "high": t["high"],
            "low": t["low"],
            "volume": t.get("baseVolume"),
        })
    return pd.DataFrame(rows).sort_values("volume", ascending=False, na_position="last")


def get_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1d",
    limit: int = 100,
    exchange: str = DEFAULT_EXCHANGE,
) -> pd.DataFrame:
    """Get OHLCV K-line data.

    Args:
        timeframe: '1m', '5m', '15m', '1h', '4h', '1d', '1w', '1M'
        limit: number of candles (max varies by exchange, typically 500-1000)
    """
    ex = _get_exchange(exchange)
    data = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    return df


def get_orderbook(
    symbol: str = "BTC/USDT",
    limit: int = 10,
    exchange: str = DEFAULT_EXCHANGE,
) -> dict:
    """Get order book (bids and asks).

    Returns dict with 'bids' and 'asks' DataFrames plus 'spread'.
    """
    ex = _get_exchange(exchange)
    ob = ex.fetch_order_book(symbol, limit=limit)

    bids_df = pd.DataFrame(ob["bids"][:limit], columns=["price", "amount", "_"])
    asks_df = pd.DataFrame(ob["asks"][:limit], columns=["price", "amount", "_"])
    bids_df = bids_df[["price", "amount"]]
    asks_df = asks_df[["price", "amount"]]

    spread = None
    if len(ob["asks"]) > 0 and len(ob["bids"]) > 0:
        spread = ob["asks"][0][0] - ob["bids"][0][0]

    return {
        "symbol": symbol,
        "bids": bids_df,
        "asks": asks_df,
        "best_bid": ob["bids"][0][0] if ob["bids"] else None,
        "best_ask": ob["asks"][0][0] if ob["asks"] else None,
        "spread": spread,
    }


def get_funding_rate(
    symbol: str = "BTC/USDT",
    exchange: str = DEFAULT_EXCHANGE,
) -> dict | None:
    """Get current funding rate for a perpetual contract (exchange must support it)."""
    ex = _get_exchange(exchange)
    if not ex.has.get("fetchFundingRate"):
        return None
    try:
        fr = ex.fetch_funding_rate(symbol)
        return {
            "symbol": fr.get("symbol"),
            "funding_rate": fr.get("fundingRate"),
            "next_funding_time": fr.get("fundingDatetime"),
            "timestamp": fr.get("datetime"),
        }
    except Exception:
        return None


def list_exchanges() -> list[str]:
    """List all available exchange names in ccxt."""
    return ccxt.exchanges


# ---------------------------------------------------------------------------
# CoinGecko: coin metadata and market overview
# ---------------------------------------------------------------------------

def get_coin_info(coin_id: str = "bitcoin") -> dict:
    """Get detailed coin info from CoinGecko.

    Args:
        coin_id: CoinGecko coin ID (bitcoin, ethereum, solana, etc.)
    """
    data = _cg.get_coin_by_id(
        coin_id,
        localization=False,
        tickers=False,
        community_data=False,
        developer_data=False,
    )
    md = data.get("market_data", {})
    return {
        "id": data["id"],
        "symbol": data["symbol"].upper(),
        "name": data["name"],
        "price_usd": md.get("current_price", {}).get("usd"),
        "market_cap": md.get("market_cap", {}).get("usd"),
        "market_cap_rank": data.get("market_cap_rank"),
        "total_volume": md.get("total_volume", {}).get("usd"),
        "high_24h": md.get("high_24h", {}).get("usd"),
        "low_24h": md.get("low_24h", {}).get("usd"),
        "change_24h_pct": md.get("price_change_percentage_24h"),
        "change_7d_pct": md.get("price_change_percentage_7d"),
        "change_30d_pct": md.get("price_change_percentage_30d"),
        "ath": md.get("ath", {}).get("usd"),
        "ath_date": md.get("ath_date", {}).get("usd"),
        "circulating_supply": md.get("circulating_supply"),
        "total_supply": md.get("total_supply"),
        "max_supply": md.get("max_supply"),
        "categories": data.get("categories", []),
        "description": (data.get("description", {}).get("en") or "")[:300],
    }


def get_trending() -> list[dict]:
    """Get trending coins on CoinGecko."""
    data = _cg.get_search_trending()
    return [
        {
            "rank": i + 1,
            "name": c["item"]["name"],
            "symbol": c["item"]["symbol"].upper(),
            "coin_id": c["item"]["id"],
            "market_cap_rank": c["item"].get("market_cap_rank"),
            "score": c["item"].get("score"),
        }
        for i, c in enumerate(data.get("coins", []))
    ]


def get_top_coins(
    vs_currency: str = "usd",
    limit: int = 20,
    order: str = "market_cap_desc",
) -> pd.DataFrame:
    """Get top coins by market cap from CoinGecko.

    Args:
        order: 'market_cap_desc', 'volume_desc', 'gecko_desc'
    """
    data = _cg.get_coins_markets(
        vs_currency=vs_currency,
        order=order,
        per_page=limit,
        page=1,
    )
    rows = []
    for c in data:
        rows.append({
            "rank": c["market_cap_rank"],
            "name": c["name"],
            "symbol": c["symbol"].upper(),
            "price": c["current_price"],
            "change_24h%": c.get("price_change_percentage_24h"),
            "market_cap": c["market_cap"],
            "volume_24h": c["total_volume"],
        })
    return pd.DataFrame(rows)


def get_coin_history(
    coin_id: str = "bitcoin",
    vs_currency: str = "usd",
    days: int | str = 30,
) -> pd.DataFrame:
    """Get historical price data from CoinGecko.

    Args:
        days: number of days (1, 7, 14, 30, 90, 180, 365, 'max')
    """
    data = _cg.get_coin_market_chart_by_id(
        id=coin_id,
        vs_currency=vs_currency,
        days=days,
    )
    prices = data.get("prices", [])
    df = pd.DataFrame(prices, columns=["timestamp", "price"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    return df


def search_coins(query: str) -> list[dict]:
    """Search for coins by name or symbol on CoinGecko."""
    data = _cg.search(query)
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "symbol": c["symbol"].upper(),
            "market_cap_rank": c.get("market_cap_rank"),
        }
        for c in data.get("coins", [])[:10]
    ]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_ticker(t: dict) -> str:
    """Format a ticker dict into readable text."""
    lines = [
        f"{t['symbol']} on {t['exchange']}",
        f"  Price:     {fmt_currency(t['last'])}",
        f"  Bid/Ask:   {fmt_currency(t['bid'])} / {fmt_currency(t['ask'])}",
        f"  24h High:  {fmt_currency(t['high'])}",
        f"  24h Low:   {fmt_currency(t['low'])}",
        f"  24h Vol:   {fmt_number(t['volume'])}",
        f"  Change:    {t['change_pct']:.2f}%" if t.get("change_pct") else "  Change:    N/A",
    ]
    return "\n".join(lines)


def format_coin_info(info: dict) -> str:
    """Format CoinGecko coin info into readable text."""
    lines = [
        f"{info['name']} ({info['symbol']}) -- Rank #{info.get('market_cap_rank', 'N/A')}",
        f"  Price:       {fmt_currency(info['price_usd'])}",
        f"  Market Cap:  {fmt_number(info['market_cap'])}",
        f"  24h Volume:  {fmt_number(info['total_volume'])}",
        f"  24h Change:  {info['change_24h_pct']:.2f}%" if info.get("change_24h_pct") else "",
        f"  7d Change:   {info['change_7d_pct']:.2f}%" if info.get("change_7d_pct") else "",
        f"  30d Change:  {info['change_30d_pct']:.2f}%" if info.get("change_30d_pct") else "",
        f"  ATH:         {fmt_currency(info['ath'])}",
        f"  Supply:      {fmt_number(info['circulating_supply'])} / {fmt_number(info['max_supply']) if info['max_supply'] else 'unlimited'}",
        f"  Categories:  {', '.join(info['categories'][:5])}" if info.get("categories") else "",
    ]
    return "\n".join(line for line in lines if line)
