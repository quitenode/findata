"""Polygon.io market data -- stocks, options, forex, crypto.

Covers real-time and historical data with full market coverage.
Requires: POLYGON_API_KEY environment variable (free at https://polygon.io/pricing)
Free tier: 5 API calls/minute, 2 years history, end-of-day data.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
from polygon import RESTClient

from .utils import fmt_currency, fmt_number

_client: RESTClient | None = None


def _get_client() -> RESTClient:
    global _client
    if _client is None:
        key = os.environ.get("POLYGON_API_KEY")
        if not key:
            raise RuntimeError(
                "POLYGON_API_KEY not set. Get a free key at "
                "https://polygon.io/pricing\n"
                "Then: export POLYGON_API_KEY='your_key'"
            )
        _client = RESTClient(api_key=key)
    return _client


def get_ticker_details(ticker: str) -> dict:
    """Get detailed info about a ticker: name, market cap, description, SIC, etc."""
    c = _get_client()
    d = c.get_ticker_details(ticker.upper())
    return {
        "ticker": d.ticker,
        "name": d.name,
        "market": d.market,
        "locale": d.locale,
        "type": d.type,
        "currency": d.currency_name,
        "market_cap": d.market_cap,
        "shares_outstanding": d.share_class_shares_outstanding,
        "description": (d.description or "")[:400],
        "sic_code": d.sic_code,
        "sic_description": d.sic_description,
        "homepage": d.homepage_url,
        "list_date": d.list_date,
        "total_employees": d.total_employees,
    }


def get_daily_bars(
    ticker: str,
    days: int = 30,
    adjusted: bool = True,
) -> pd.DataFrame:
    """Get daily OHLCV bars (aggregates).

    Args:
        days: number of calendar days of history
        adjusted: whether to adjust for splits
    """
    c = _get_client()
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    aggs = list(c.list_aggs(
        ticker=ticker.upper(),
        multiplier=1,
        timespan="day",
        from_=start,
        to=end,
        adjusted=adjusted,
        limit=5000,
    ))

    rows = []
    for a in aggs:
        rows.append({
            "date": datetime.fromtimestamp(a.timestamp / 1000).strftime("%Y-%m-%d"),
            "open": a.open,
            "high": a.high,
            "low": a.low,
            "close": a.close,
            "volume": a.volume,
            "vwap": a.vwap,
            "transactions": a.transactions,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.set_index("date")
    return df


def get_intraday_bars(
    ticker: str,
    multiplier: int = 5,
    timespan: str = "minute",
    days: int = 1,
) -> pd.DataFrame:
    """Get intraday bars.

    Args:
        multiplier: size of timespan multiplier (e.g. 5 for 5-minute bars)
        timespan: 'minute', 'hour'
        days: how many days of intraday data
    """
    c = _get_client()
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    aggs = list(c.list_aggs(
        ticker=ticker.upper(),
        multiplier=multiplier,
        timespan=timespan,
        from_=start,
        to=end,
        limit=5000,
    ))

    rows = []
    for a in aggs:
        rows.append({
            "time": datetime.fromtimestamp(a.timestamp / 1000).strftime("%Y-%m-%d %H:%M"),
            "open": a.open,
            "high": a.high,
            "low": a.low,
            "close": a.close,
            "volume": a.volume,
            "vwap": a.vwap,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.set_index("time")
    return df


def get_previous_close(ticker: str) -> dict:
    """Get previous day's OHLCV data."""
    c = _get_client()
    aggs = list(c.list_aggs(
        ticker=ticker.upper(),
        multiplier=1,
        timespan="day",
        from_=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        to=datetime.now().strftime("%Y-%m-%d"),
        limit=1,
        sort="desc",
    ))
    if not aggs:
        return {"ticker": ticker.upper(), "error": "No data"}
    a = aggs[0]
    return {
        "ticker": ticker.upper(),
        "open": a.open,
        "high": a.high,
        "low": a.low,
        "close": a.close,
        "volume": a.volume,
        "vwap": a.vwap,
        "date": datetime.fromtimestamp(a.timestamp / 1000).strftime("%Y-%m-%d"),
    }


def get_grouped_daily(date: str | None = None) -> pd.DataFrame:
    """Get all tickers' daily bars for a given date (market snapshot).

    Args:
        date: date string (YYYY-MM-DD), defaults to most recent trading day
    """
    c = _get_client()
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    resp = c.get_grouped_daily_aggs(date=date)
    rows = []
    for a in resp:
        rows.append({
            "ticker": a.ticker,
            "open": a.open,
            "high": a.high,
            "low": a.low,
            "close": a.close,
            "volume": a.volume,
            "vwap": a.vwap,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("volume", ascending=False)
    return df


def search_tickers(
    query: str,
    market: str = "stocks",
    limit: int = 10,
) -> pd.DataFrame:
    """Search for tickers by name or symbol.

    Args:
        market: 'stocks', 'crypto', 'fx', 'otc', 'indices'
    """
    c = _get_client()
    results = list(c.list_tickers(
        search=query,
        market=market,
        limit=limit,
    ))
    rows = []
    for t in results:
        rows.append({
            "ticker": t.ticker,
            "name": t.name,
            "market": t.market,
            "type": t.type,
            "currency": t.currency_name,
            "locale": t.locale,
        })
    return pd.DataFrame(rows)


def get_related_companies(ticker: str) -> list[dict]:
    """Get related/peer companies for a ticker."""
    c = _get_client()
    try:
        results = c.get_related_companies(ticker.upper())
        return [{"ticker": r.ticker} for r in results]
    except Exception:
        return []


def get_stock_splits(ticker: str) -> pd.DataFrame:
    """Get historical stock splits."""
    c = _get_client()
    splits = list(c.list_splits(ticker=ticker.upper(), limit=20))
    rows = []
    for s in splits:
        rows.append({
            "execution_date": s.execution_date,
            "split_from": s.split_from,
            "split_to": s.split_to,
        })
    return pd.DataFrame(rows)


def get_dividends(ticker: str) -> pd.DataFrame:
    """Get historical dividends."""
    c = _get_client()
    divs = list(c.list_dividends(ticker=ticker.upper(), limit=20))
    rows = []
    for d in divs:
        rows.append({
            "ex_date": d.ex_dividend_date,
            "pay_date": d.pay_date,
            "cash_amount": d.cash_amount,
            "frequency": d.frequency,
            "type": d.dividend_type,
        })
    return pd.DataFrame(rows)
