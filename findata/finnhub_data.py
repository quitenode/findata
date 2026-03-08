"""Finnhub financial data -- real-time quotes, company news, insider trades, earnings.

Free tier: 60 calls/min. Covers US stocks primarily.
Requires: FINNHUB_API_KEY environment variable (free at https://finnhub.io/register)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import finnhub

from .utils import fmt_currency, fmt_number

_client: finnhub.Client | None = None


def _get_client() -> finnhub.Client:
    global _client
    if _client is None:
        key = os.environ.get("FINNHUB_API_KEY")
        if not key:
            raise RuntimeError(
                "FINNHUB_API_KEY not set. Get a free key at "
                "https://finnhub.io/register\n"
                "Then: export FINNHUB_API_KEY='your_key'"
            )
        _client = finnhub.Client(api_key=key)
    return _client


def get_quote(ticker: str) -> dict:
    """Get real-time quote: current price, change, high/low, open, previous close."""
    c = _get_client()
    q = c.quote(ticker.upper())
    return {
        "ticker": ticker.upper(),
        "price": q.get("c"),
        "change": q.get("d"),
        "change_pct": q.get("dp"),
        "high": q.get("h"),
        "low": q.get("l"),
        "open": q.get("o"),
        "previous_close": q.get("pc"),
        "timestamp": q.get("t"),
    }


def get_company_profile(ticker: str) -> dict:
    """Get company profile: industry, market cap, IPO date, logo, etc."""
    c = _get_client()
    p = c.company_profile2(symbol=ticker.upper())
    return {
        "ticker": p.get("ticker"),
        "name": p.get("name"),
        "country": p.get("country"),
        "exchange": p.get("exchange"),
        "industry": p.get("finnhubIndustry"),
        "market_cap": p.get("marketCapitalization"),
        "ipo_date": p.get("ipo"),
        "logo": p.get("logo"),
        "url": p.get("weburl"),
        "shares_outstanding": p.get("shareOutstanding"),
    }


def get_company_news(
    ticker: str,
    days_back: int = 7,
) -> pd.DataFrame:
    """Get recent news for a company.

    Args:
        days_back: how many days back to fetch
    """
    c = _get_client()
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    news = c.company_news(ticker.upper(), _from=start, to=end)

    rows = []
    for n in news[:20]:
        rows.append({
            "headline": n.get("headline", ""),
            "source": n.get("source", ""),
            "datetime": datetime.fromtimestamp(n.get("datetime", 0)).strftime("%Y-%m-%d %H:%M"),
            "summary": (n.get("summary") or "")[:200],
            "url": n.get("url", ""),
            "category": n.get("category", ""),
        })
    return pd.DataFrame(rows)


def get_analyst_recommendations(ticker: str) -> pd.DataFrame:
    """Get analyst recommendation trends (buy/hold/sell counts by period)."""
    c = _get_client()
    recs = c.recommendation_trends(ticker.upper())
    rows = []
    for r in recs[:6]:
        rows.append({
            "period": r.get("period"),
            "strong_buy": r.get("strongBuy", 0),
            "buy": r.get("buy", 0),
            "hold": r.get("hold", 0),
            "sell": r.get("sell", 0),
            "strong_sell": r.get("strongSell", 0),
        })
    return pd.DataFrame(rows)


def get_price_target(ticker: str) -> dict:
    """Get analyst price target consensus."""
    c = _get_client()
    pt = c.price_target(ticker.upper())
    return {
        "ticker": ticker.upper(),
        "target_high": pt.get("targetHigh"),
        "target_low": pt.get("targetLow"),
        "target_mean": pt.get("targetMean"),
        "target_median": pt.get("targetMedian"),
        "last_updated": pt.get("lastUpdated"),
    }


def get_insider_transactions(ticker: str) -> pd.DataFrame:
    """Get insider transactions (Form 4 filings)."""
    c = _get_client()
    data = c.stock_insider_transactions(ticker.upper())
    txns = data.get("data", [])

    rows = []
    for t in txns[:20]:
        rows.append({
            "name": t.get("name", ""),
            "share": t.get("share", 0),
            "change": t.get("change", 0),
            "transaction_type": t.get("transactionType", ""),
            "filing_date": t.get("filingDate", ""),
            "transaction_date": t.get("transactionDate", ""),
        })
    return pd.DataFrame(rows)


def get_earnings_calendar(
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Get upcoming earnings calendar.

    Args:
        start/end: date strings, defaults to next 7 days
    """
    c = _get_client()
    if not start:
        start = datetime.now().strftime("%Y-%m-%d")
    if not end:
        end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    data = c.earnings_calendar(_from=start, to=end, symbol="")
    earnings = data.get("earningsCalendar", [])

    rows = []
    for e in earnings[:50]:
        rows.append({
            "date": e.get("date", ""),
            "symbol": e.get("symbol", ""),
            "eps_estimate": e.get("epsEstimate"),
            "eps_actual": e.get("epsActual"),
            "revenue_estimate": e.get("revenueEstimate"),
            "revenue_actual": e.get("revenueActual"),
            "hour": e.get("hour", ""),
        })
    return pd.DataFrame(rows)


def get_basic_financials(ticker: str) -> dict:
    """Get key financial metrics (P/E, P/B, ROE, margins, etc.)."""
    c = _get_client()
    data = c.company_basic_financials(ticker.upper(), "all")
    metrics = data.get("metric", {})
    return {
        "ticker": ticker.upper(),
        "52w_high": metrics.get("52WeekHigh"),
        "52w_low": metrics.get("52WeekLow"),
        "pe_ttm": metrics.get("peTTM"),
        "pb_quarterly": metrics.get("pbQuarterly"),
        "ps_ttm": metrics.get("psTTM"),
        "dividend_yield": metrics.get("dividendYieldIndicatedAnnual"),
        "roe_ttm": metrics.get("roeTTM"),
        "roa_ttm": metrics.get("roaTTM"),
        "gross_margin_ttm": metrics.get("grossMarginTTM"),
        "operating_margin_ttm": metrics.get("operatingMarginTTM"),
        "net_margin_ttm": metrics.get("netProfitMarginTTM"),
        "revenue_growth_3y": metrics.get("revenueGrowth3Y"),
        "eps_growth_3y": metrics.get("epsGrowth3Y"),
        "beta": metrics.get("beta"),
    }


def get_market_status() -> dict:
    """Get current market open/close status for major exchanges."""
    c = _get_client()
    data = c.market_status(exchange="US")
    return {
        "exchange": data.get("exchange"),
        "is_open": data.get("isOpen"),
        "session": data.get("session"),
        "timezone": data.get("timezone"),
    }


def format_quote(q: dict) -> str:
    """Format a Finnhub quote into readable text."""
    lines = [
        f"{q['ticker']}",
        f"  Price:     {fmt_currency(q['price'])}",
        f"  Change:    {fmt_currency(q['change'])} ({q['change_pct']:.2f}%)" if q.get("change_pct") else "",
        f"  Day Range: {fmt_currency(q['low'])} - {fmt_currency(q['high'])}",
        f"  Open:      {fmt_currency(q['open'])}",
        f"  Prev Close:{fmt_currency(q['previous_close'])}",
    ]
    return "\n".join(line for line in lines if line)
