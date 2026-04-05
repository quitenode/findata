"""US stock data via yfinance -- quotes, K-lines, financials, analyst ratings."""

from __future__ import annotations

from typing import Literal

import pandas as pd
import yfinance as yf

from .utils import fmt_currency, fmt_number, fmt_percent


def get_quote(ticker: str) -> dict:
    """Get current quote: price, change, volume, market cap, P/E, etc."""
    t = yf.Ticker(ticker)
    info = t.info
    fast = t.fast_info

    return {
        "ticker": ticker.upper(),
        "name": info.get("shortName") or info.get("longName", ticker),
        "price": fast.get("lastPrice"),
        "previous_close": fast.get("previousClose"),
        "change": _calc_change(fast.get("lastPrice"), fast.get("previousClose")),
        "change_pct": _calc_change_pct(fast.get("lastPrice"), fast.get("previousClose")),
        "day_high": fast.get("dayHigh"),
        "day_low": fast.get("dayLow"),
        "volume": fast.get("lastVolume"),
        "market_cap": fast.get("marketCap"),
        "currency": fast.get("currency", "USD"),
        "exchange": info.get("exchange"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "eps": info.get("trailingEps"),
        "dividend_yield": info.get("dividendYield"),
        "52w_high": fast.get("yearHigh"),
        "52w_low": fast.get("yearLow"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


def get_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Get OHLCV K-line data.

    Args:
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    if df.empty:
        return df
    df.index.name = "Date"
    return df[["Open", "High", "Low", "Close", "Volume"]]


def get_financials(
    ticker: str,
    statement: Literal["income", "balance", "cashflow", "all"] = "all",
    quarterly: bool = False,
) -> dict[str, pd.DataFrame]:
    """Get financial statements.

    Returns a dict with keys: 'income', 'balance', 'cashflow'.
    """
    t = yf.Ticker(ticker)
    result = {}

    if statement in ("income", "all"):
        result["income"] = t.quarterly_income_stmt if quarterly else t.income_stmt

    if statement in ("balance", "all"):
        result["balance"] = t.quarterly_balance_sheet if quarterly else t.balance_sheet

    if statement in ("cashflow", "all"):
        result["cashflow"] = t.quarterly_cashflow if quarterly else t.cashflow

    return result


def get_analyst_ratings(ticker: str) -> dict:
    """Get analyst recommendations, target prices, and upgrades/downgrades."""
    t = yf.Ticker(ticker)
    info = t.info

    recommendations = None
    try:
        recs = t.recommendations
        if recs is not None and not recs.empty:
            recommendations = recs.tail(10)
    except Exception:
        pass

    upgrades_downgrades = None
    try:
        ud = t.upgrades_downgrades
        if ud is not None and not ud.empty:
            upgrades_downgrades = ud.tail(10)
    except Exception:
        pass

    return {
        "ticker": ticker.upper(),
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "target_mean": info.get("targetMeanPrice"),
        "target_median": info.get("targetMedianPrice"),
        "recommendation": info.get("recommendationKey"),
        "num_analysts": info.get("numberOfAnalystOpinions"),
        "recommendations": recommendations,
        "upgrades_downgrades": upgrades_downgrades,
    }


def get_news(ticker: str) -> list[dict]:
    """Get recent news headlines for a ticker."""
    t = yf.Ticker(ticker)
    news = t.news or []
    results = []
    for item in news[:15]:
        c = item.get("content") or item
        provider = c.get("provider", {})
        canon = c.get("canonicalUrl") or c.get("clickThroughUrl") or {}
        results.append({
            "title": c.get("title") or item.get("title", ""),
            "publisher": provider.get("displayName") if isinstance(provider, dict) else (c.get("publisher") or item.get("publisher", "")),
            "link": canon.get("url") if isinstance(canon, dict) else (c.get("link") or item.get("link", "")),
            "published": c.get("pubDate") or item.get("providerPublishTime", ""),
            "type": c.get("contentType") or item.get("type", ""),
        })
    return results


def get_options_chain(ticker: str, expiration: str | None = None) -> dict:
    """Get options chain data.

    Args:
        expiration: specific date string, or None for nearest expiry.
    Returns dict with 'calls', 'puts' DataFrames and 'expirations' list.
    """
    t = yf.Ticker(ticker)
    expirations = t.options
    if not expirations:
        return {"calls": pd.DataFrame(), "puts": pd.DataFrame(), "expirations": []}

    exp = expiration or expirations[0]
    chain = t.option_chain(exp)
    return {
        "expiration": exp,
        "calls": chain.calls,
        "puts": chain.puts,
        "expirations": list(expirations),
    }


def compare_peers(tickers: list[str]) -> pd.DataFrame:
    """Side-by-side comparison of key metrics for multiple tickers."""
    rows = []
    for sym in tickers:
        try:
            q = get_quote(sym)
            rows.append({
                "Ticker": q["ticker"],
                "Name": q["name"],
                "Price": fmt_currency(q["price"]),
                "Change%": fmt_percent(q["change_pct"]),
                "MktCap": fmt_number(q["market_cap"]),
                "P/E": f"{q['pe_ratio']:.1f}" if q["pe_ratio"] else "N/A",
                "EPS": fmt_currency(q["eps"]) if q["eps"] else "N/A",
                "DivYield": fmt_percent(q["dividend_yield"]) if q["dividend_yield"] else "N/A",
                "52wHigh": fmt_currency(q["52w_high"]),
                "52wLow": fmt_currency(q["52w_low"]),
                "Sector": q["sector"] or "N/A",
            })
        except Exception as e:
            rows.append({"Ticker": sym, "Name": f"Error: {e}"})

    return pd.DataFrame(rows)


def format_quote(quote: dict) -> str:
    """Format a quote dict into a readable string."""
    lines = [
        f"{quote['name']} ({quote['ticker']})",
        f"  Price:      {fmt_currency(quote['price'])}",
        f"  Change:     {fmt_currency(quote['change'])} ({fmt_percent(quote['change_pct'])})",
        f"  Volume:     {fmt_number(quote['volume'], 0)}",
        f"  Market Cap: {fmt_number(quote['market_cap'])}",
        f"  P/E:        {quote['pe_ratio']:.2f}" if quote.get("pe_ratio") else "  P/E:        N/A",
        f"  EPS:        {fmt_currency(quote['eps'])}" if quote.get("eps") else "  EPS:        N/A",
        f"  52w Range:  {fmt_currency(quote['52w_low'])} - {fmt_currency(quote['52w_high'])}",
        f"  Sector:     {quote.get('sector', 'N/A')}",
        f"  Industry:   {quote.get('industry', 'N/A')}",
    ]
    return "\n".join(lines)


def _calc_change(current, previous):
    if current is not None and previous is not None:
        return current - previous
    return None


def _calc_change_pct(current, previous):
    if current is not None and previous is not None and previous != 0:
        return (current - previous) / previous
    return None
