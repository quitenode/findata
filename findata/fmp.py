"""Financial Modeling Prep (FMP) data -- fundamentals, DCF, congress trades, insider.

253+ endpoints covering financials, analyst estimates, ESG, SEC filings, and more.
Unique data: congress/senate trades, DCF valuation, institutional holdings.
Requires: FMP_API_KEY environment variable (free 250 req/day at https://site.financialmodelingprep.com/register)
Note: New accounts use /stable/ endpoints (old /api/v3/ deprecated 2025-08-31).
"""

from __future__ import annotations

import os

import pandas as pd
import requests

from .utils import fmt_currency, fmt_number, safe_get

_BASE_URL = "https://financialmodelingprep.com/stable"
_session = requests.Session()


def _get_key() -> str:
    key = os.environ.get("FMP_API_KEY")
    if not key:
        raise RuntimeError(
            "FMP_API_KEY not set. Get a free key at "
            "https://site.financialmodelingprep.com/register\n"
            "Then: export FMP_API_KEY='your_key'"
        )
    return key


def _get(endpoint: str, params: dict | None = None) -> list | dict:
    p = params or {}
    p["apikey"] = _get_key()
    resp = _session.get(f"{_BASE_URL}/{endpoint}", params=p, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Company profile & quotes
# ---------------------------------------------------------------------------

def get_profile(ticker: str) -> dict:
    """Get company profile: price, market cap, sector, CEO, description, etc."""
    data = _get("profile", {"symbol": ticker.upper()})
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else {}


def get_quote(ticker: str) -> dict:
    """Get real-time quote with extended metrics."""
    data = _get("quote", {"symbol": ticker.upper()})
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else {}


def get_quote_batch(tickers: list[str]) -> pd.DataFrame:
    """Get quotes for multiple tickers at once."""
    symbols = ",".join(t.upper() for t in tickers)
    data = _get("quote", {"symbol": symbols})
    if isinstance(data, list):
        return pd.DataFrame(data)
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Financial statements
# ---------------------------------------------------------------------------

def get_income_statement(
    ticker: str,
    period: str = "annual",
    limit: int = 5,
) -> pd.DataFrame:
    """Get income statements.

    Args:
        period: 'annual' or 'quarter'
    """
    data = _get("income-statement", {
        "symbol": ticker.upper(),
        "period": period,
        "limit": limit,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_balance_sheet(
    ticker: str,
    period: str = "annual",
    limit: int = 5,
) -> pd.DataFrame:
    """Get balance sheet statements."""
    data = _get("balance-sheet-statement", {
        "symbol": ticker.upper(),
        "period": period,
        "limit": limit,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_cash_flow(
    ticker: str,
    period: str = "annual",
    limit: int = 5,
) -> pd.DataFrame:
    """Get cash flow statements."""
    data = _get("cash-flow-statement", {
        "symbol": ticker.upper(),
        "period": period,
        "limit": limit,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


# ---------------------------------------------------------------------------
# Analysis & valuation
# ---------------------------------------------------------------------------

def get_dcf(ticker: str) -> dict:
    """Get DCF (Discounted Cash Flow) intrinsic value estimate."""
    data = _get("discounted-cash-flow", {"symbol": ticker.upper()})
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else {}


def get_analyst_estimates(
    ticker: str,
    period: str = "annual",
    limit: int = 5,
) -> pd.DataFrame:
    """Get analyst EPS and revenue estimates."""
    data = _get("analyst-estimates", {
        "symbol": ticker.upper(),
        "period": period,
        "limit": limit,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_analyst_ratings(ticker: str) -> pd.DataFrame:
    """Get analyst stock ratings (buy/sell/hold consensus)."""
    data = _get("rating", {"symbol": ticker.upper()})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_price_target(ticker: str) -> pd.DataFrame:
    """Get analyst price target history."""
    data = _get("price-target", {"symbol": ticker.upper()})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


# ---------------------------------------------------------------------------
# Alternative data (FMP unique features)
# ---------------------------------------------------------------------------

def get_insider_trades(
    ticker: str,
    limit: int = 20,
) -> pd.DataFrame:
    """Get insider trading data (CEO/CFO buying/selling)."""
    data = _get("insider-trading", {
        "symbol": ticker.upper(),
        "limit": limit,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_senate_trades(limit: int = 20) -> pd.DataFrame:
    """Get US Senate stock trading disclosures."""
    data = _get("senate-trading", {"limit": limit})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_congress_trades(limit: int = 20) -> pd.DataFrame:
    """Get US House of Representatives stock trading disclosures."""
    data = _get("house-disclosure", {"limit": limit})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_institutional_holders(ticker: str) -> pd.DataFrame:
    """Get institutional holders (13F data)."""
    data = _get("institutional-holder", {"symbol": ticker.upper()})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


# ---------------------------------------------------------------------------
# Technical & market data
# ---------------------------------------------------------------------------

def get_technical_indicators(
    ticker: str,
    indicator: str = "rsi",
    period: int = 14,
    time_period: str = "daily",
) -> pd.DataFrame:
    """Get technical indicators (RSI, SMA, EMA, MACD, etc.).

    Args:
        indicator: 'rsi', 'sma', 'ema', 'macd', 'adx', 'williams', etc.
        period: lookback period
        time_period: 'daily', 'weekly', 'monthly'
    """
    data = _get("technical_indicator", {
        "symbol": ticker.upper(),
        "type": indicator,
        "period": period,
        "timeperiod": time_period,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_earnings(
    ticker: str,
    limit: int = 10,
) -> pd.DataFrame:
    """Get historical earnings (actual vs estimate)."""
    data = _get("earnings", {
        "symbol": ticker.upper(),
        "limit": limit,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_esg_score(ticker: str) -> pd.DataFrame:
    """Get ESG (Environmental, Social, Governance) scores."""
    data = _get("esg-environmental-social-governance-data", {"symbol": ticker.upper()})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


# ---------------------------------------------------------------------------
# SEC filings
# ---------------------------------------------------------------------------

def get_sec_filings(
    ticker: str,
    filing_type: str = "10-K",
    limit: int = 10,
) -> pd.DataFrame:
    """Get SEC filings list (10-K, 10-Q, 8-K, S-1, etc.)."""
    data = _get("sec_filings", {
        "symbol": ticker.upper(),
        "type": filing_type,
        "limit": limit,
    })
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


# ---------------------------------------------------------------------------
# Market overview
# ---------------------------------------------------------------------------

def get_market_gainers(limit: int = 20) -> pd.DataFrame:
    """Get top market gainers today."""
    data = _get("stock_market/gainers", {"limit": limit})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_market_losers(limit: int = 20) -> pd.DataFrame:
    """Get top market losers today."""
    data = _get("stock_market/losers", {"limit": limit})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_market_most_active(limit: int = 20) -> pd.DataFrame:
    """Get most actively traded stocks today."""
    data = _get("stock_market/actives", {"limit": limit})
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()


def get_sector_performance() -> pd.DataFrame:
    """Get today's sector performance."""
    data = _get("sectors-performance")
    return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()
