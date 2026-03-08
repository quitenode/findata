"""Forex, commodities, and precious metals via OANDA.

141+ instruments: currency pairs, gold, oil, crypto, stock indices.
Requires: OANDA_ACCOUNT_ID and OANDA_API_KEY environment variables.
Free practice account at https://www.oanda.com/register
"""

from __future__ import annotations

import os
from typing import Literal

import pandas as pd
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts

from .utils import fmt_currency, fmt_number

_client: oandapyV20.API | None = None
_account_id: str | None = None

COMMON_PAIRS = {
    "forex": ["EUR_USD", "USD_JPY", "GBP_USD", "AUD_USD", "USD_CNH", "USD_CHF"],
    "metals": ["XAU_USD", "XAG_USD"],
    "energy": ["WTICO_USD", "BCO_USD", "NATGAS_USD"],
    "crypto": ["BTC_USD", "ETH_USD"],
    "indices": ["SPX500_USD", "NAS100_USD", "US30_USD", "HK33_HKD"],
    "agriculture": ["CORN_USD", "SOYBN_USD", "WHEAT_USD"],
}


def _get_client() -> tuple[oandapyV20.API, str]:
    global _client, _account_id
    if _client is None:
        token = os.environ.get("OANDA_API_KEY")
        acc = os.environ.get("OANDA_ACCOUNT_ID")
        if not token or not acc:
            raise RuntimeError(
                "OANDA_API_KEY and OANDA_ACCOUNT_ID not set.\n"
                "Get a free practice account at https://www.oanda.com/register\n"
                "Then: export OANDA_API_KEY='your_token'\n"
                "      export OANDA_ACCOUNT_ID='your_account_id'"
            )
        _client = oandapyV20.API(access_token=token, environment="practice")
        _account_id = acc
    return _client, _account_id


def list_common_pairs() -> dict[str, list[str]]:
    """Return commonly traded instruments by category."""
    return COMMON_PAIRS.copy()


def get_price(instrument: str = "EUR_USD") -> dict:
    """Get real-time bid/ask price for an instrument.

    Args:
        instrument: OANDA instrument name (e.g. 'EUR_USD', 'XAU_USD', 'WTICO_USD')
    """
    client, acc = _get_client()
    params = {"instruments": instrument}
    r = pricing.PricingInfo(accountID=acc, params=params)
    client.request(r)

    prices = r.response.get("prices", [])
    if not prices:
        return {"instrument": instrument, "error": "No price data"}

    p = prices[0]
    bid = float(p["bids"][-1]["price"]) if p.get("bids") else None
    ask = float(p["asks"][-1]["price"]) if p.get("asks") else None
    spread = ask - bid if bid and ask else None

    return {
        "instrument": p.get("instrument", instrument),
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "mid": (bid + ask) / 2 if bid and ask else None,
        "tradeable": p.get("tradeable", False),
        "time": p.get("time", ""),
    }


def get_prices_batch(instrument_list: list[str]) -> pd.DataFrame:
    """Get prices for multiple instruments at once."""
    client, acc = _get_client()
    params = {"instruments": ",".join(instrument_list)}
    r = pricing.PricingInfo(accountID=acc, params=params)
    client.request(r)

    rows = []
    for p in r.response.get("prices", []):
        bid = float(p["bids"][-1]["price"]) if p.get("bids") else None
        ask = float(p["asks"][-1]["price"]) if p.get("asks") else None
        rows.append({
            "instrument": p.get("instrument"),
            "bid": bid,
            "ask": ask,
            "spread": ask - bid if bid and ask else None,
        })
    return pd.DataFrame(rows)


def get_candles(
    instrument: str = "EUR_USD",
    granularity: str = "D",
    count: int = 100,
) -> pd.DataFrame:
    """Get OHLCV candlestick data.

    Args:
        granularity: 'S5','S10','S15','S30','M1','M2','M4','M5','M10','M15',
                     'M30','H1','H2','H3','H4','H6','H8','H12','D','W','M'
        count: number of candles (max 5000)
    """
    client, _ = _get_client()
    params = {
        "granularity": granularity,
        "count": count,
    }
    r = instruments.InstrumentsCandles(instrument=instrument, params=params)
    client.request(r)

    rows = []
    for c in r.response.get("candles", []):
        mid = c.get("mid", {})
        rows.append({
            "time": c.get("time", ""),
            "open": float(mid.get("o", 0)),
            "high": float(mid.get("h", 0)),
            "low": float(mid.get("l", 0)),
            "close": float(mid.get("c", 0)),
            "volume": c.get("volume", 0),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    return df


def get_order_book(instrument: str = "EUR_USD") -> dict:
    """Get order book snapshot (shows where pending orders cluster)."""
    client, _ = _get_client()
    r = instruments.InstrumentsOrderBook(instrument=instrument)
    client.request(r)
    ob = r.response.get("orderBook", {})
    buckets = ob.get("buckets", [])
    df = pd.DataFrame(buckets)
    if not df.empty:
        df["price"] = df["price"].astype(float)
        df["longCountPercent"] = df["longCountPercent"].astype(float)
        df["shortCountPercent"] = df["shortCountPercent"].astype(float)
    return {
        "instrument": instrument,
        "price": float(ob.get("price", 0)),
        "time": ob.get("time", ""),
        "buckets": df,
    }


def get_position_book(instrument: str = "EUR_USD") -> dict:
    """Get position book (shows open position distribution -- retail sentiment)."""
    client, _ = _get_client()
    r = instruments.InstrumentsPositionBook(instrument=instrument)
    client.request(r)
    pb = r.response.get("positionBook", {})
    buckets = pb.get("buckets", [])
    df = pd.DataFrame(buckets)
    if not df.empty:
        df["price"] = df["price"].astype(float)
        df["longCountPercent"] = df["longCountPercent"].astype(float)
        df["shortCountPercent"] = df["shortCountPercent"].astype(float)

    total_long = df["longCountPercent"].sum() if not df.empty else 0
    total_short = df["shortCountPercent"].sum() if not df.empty else 0

    return {
        "instrument": instrument,
        "price": float(pb.get("price", 0)),
        "time": pb.get("time", ""),
        "long_pct": total_long,
        "short_pct": total_short,
        "buckets": df,
    }


def get_account_info() -> dict:
    """Get account summary (balance, unrealized P/L, margin)."""
    client, acc = _get_client()
    r = accounts.AccountSummary(accountID=acc)
    client.request(r)
    a = r.response.get("account", {})
    return {
        "id": a.get("id"),
        "currency": a.get("currency"),
        "balance": float(a.get("balance", 0)),
        "unrealized_pl": float(a.get("unrealizedPL", 0)),
        "nav": float(a.get("NAV", 0)),
        "margin_used": float(a.get("marginUsed", 0)),
        "margin_available": float(a.get("marginAvailable", 0)),
        "open_trades": a.get("openTradeCount", 0),
    }


def get_forex_dashboard() -> pd.DataFrame:
    """Quick dashboard: 7 major pairs + gold + oil + BTC."""
    dashboard_instruments = [
        "EUR_USD", "USD_JPY", "GBP_USD", "AUD_USD",
        "XAU_USD", "WTICO_USD", "BTC_USD",
    ]
    return get_prices_batch(dashboard_instruments)


def format_price(p: dict) -> str:
    """Format a price dict into readable text."""
    lines = [
        f"{p['instrument']}",
        f"  Bid:     {p['bid']:.5f}" if p.get("bid") else "  Bid:     N/A",
        f"  Ask:     {p['ask']:.5f}" if p.get("ask") else "  Ask:     N/A",
        f"  Spread:  {p['spread']:.5f}" if p.get("spread") else "  Spread:  N/A",
        f"  Mid:     {p['mid']:.5f}" if p.get("mid") else "  Mid:     N/A",
    ]
    return "\n".join(lines)
