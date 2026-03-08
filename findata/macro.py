"""Macro economy data via FRED (Federal Reserve Economic Data).

800,000+ time series covering interest rates, inflation, GDP, employment, etc.
Requires: FRED_API_KEY environment variable (free at https://fred.stlouisfed.org/docs/api/api_key.html)
"""

from __future__ import annotations

import os
from typing import Literal

import pandas as pd
from fredapi import Fred

from .utils import fmt_number, fmt_percent

_fred: Fred | None = None

COMMON_SERIES = {
    "FEDFUNDS": "Federal Funds Rate",
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "T10Y2Y": "10Y-2Y Spread (recession indicator)",
    "CPIAUCSL": "CPI (Monthly, inflation)",
    "PCEPILFE": "Core PCE (Fed preferred inflation)",
    "A191RL1Q225SBEA": "Real GDP Growth Rate",
    "UNRATE": "Unemployment Rate",
    "SAHMREALTIME": "Sahm Rule (recession warning)",
    "DEXCHUS": "CNY/USD Exchange Rate",
    "DCOILWTICO": "WTI Crude Oil Price",
    "VIXCLS": "VIX Volatility Index",
    "M2SL": "M2 Money Supply",
    "MORTGAGE30US": "30-Year Mortgage Rate",
    "PAYEMS": "Total Nonfarm Payrolls",
    "UMCSENT": "Consumer Sentiment (UMich)",
    "DTWEXBGS": "Trade Weighted USD Index",
    "BAMLH0A0HYM2": "High Yield Bond Spread",
}


def _get_fred() -> Fred:
    global _fred
    if _fred is None:
        key = os.environ.get("FRED_API_KEY")
        if not key:
            raise RuntimeError(
                "FRED_API_KEY not set. Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html\n"
                "Then: export FRED_API_KEY='your_key'"
            )
        _fred = Fred(api_key=key)
    return _fred


def list_common_series() -> dict[str, str]:
    """Return a dict of commonly used FRED series IDs and descriptions."""
    return COMMON_SERIES.copy()


def get_series(
    series_id: str,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
) -> pd.Series:
    """Get a FRED time series.

    Args:
        series_id: FRED series ID (e.g. 'FEDFUNDS', 'CPIAUCSL')
        start: start date string (e.g. '2020-01-01')
        end: end date string
        limit: if set, return only the last N observations
    """
    fred = _get_fred()
    data = fred.get_series(series_id, observation_start=start, observation_end=end)
    if limit and len(data) > limit:
        data = data.tail(limit)
    data.name = series_id
    return data


def get_series_info(series_id: str) -> dict:
    """Get metadata about a FRED series."""
    fred = _get_fred()
    info = fred.get_series_info(series_id)
    return {
        "id": info.get("id", series_id),
        "title": info.get("title", ""),
        "frequency": info.get("frequency", ""),
        "units": info.get("units", ""),
        "seasonal_adjustment": info.get("seasonal_adjustment", ""),
        "last_updated": str(info.get("last_updated", "")),
        "notes": (info.get("notes") or "")[:300],
    }


def search_series(
    query: str,
    limit: int = 10,
) -> pd.DataFrame:
    """Search FRED for time series matching a query."""
    fred = _get_fred()
    results = fred.search(query)
    if results is None or results.empty:
        return pd.DataFrame()
    cols = ["title", "frequency", "units", "seasonal_adjustment", "popularity"]
    available = [c for c in cols if c in results.columns]
    return results[available].head(limit)


def get_macro_dashboard() -> dict[str, dict]:
    """Get a snapshot of key macro indicators (12 series)."""
    dashboard_ids = [
        "FEDFUNDS", "DGS10", "DGS2", "T10Y2Y",
        "CPIAUCSL", "UNRATE", "A191RL1Q225SBEA",
        "DCOILWTICO", "VIXCLS", "DEXCHUS",
        "SAHMREALTIME", "MORTGAGE30US",
    ]
    result = {}
    for sid in dashboard_ids:
        try:
            data = get_series(sid, limit=1)
            label = COMMON_SERIES.get(sid, sid)
            latest = data.iloc[-1] if len(data) > 0 else None
            date = str(data.index[-1].date()) if len(data) > 0 else "N/A"
            result[sid] = {"label": label, "value": latest, "date": date}
        except Exception as e:
            result[sid] = {"label": COMMON_SERIES.get(sid, sid), "value": None, "date": f"Error: {e}"}
    return result


def get_yield_curve() -> dict:
    """Get current yield curve data (2Y, 5Y, 10Y, 30Y) plus 10Y-2Y spread."""
    maturities = {
        "DGS1MO": "1M", "DGS3MO": "3M", "DGS6MO": "6M",
        "DGS1": "1Y", "DGS2": "2Y", "DGS5": "5Y",
        "DGS10": "10Y", "DGS30": "30Y",
    }
    curve = {}
    for sid, label in maturities.items():
        try:
            data = get_series(sid, limit=1)
            curve[label] = data.iloc[-1] if len(data) > 0 else None
        except Exception:
            curve[label] = None

    spread_2_10 = None
    if curve.get("10Y") is not None and curve.get("2Y") is not None:
        spread_2_10 = curve["10Y"] - curve["2Y"]

    return {
        "curve": curve,
        "spread_10y_2y": spread_2_10,
        "inverted": spread_2_10 is not None and spread_2_10 < 0,
    }


def get_recession_indicators() -> dict:
    """Get key recession warning indicators."""
    indicators = {}
    for sid, label in [
        ("T10Y2Y", "10Y-2Y Spread"),
        ("SAHMREALTIME", "Sahm Rule"),
        ("UNRATE", "Unemployment Rate"),
        ("UMCSENT", "Consumer Sentiment"),
        ("BAMLH0A0HYM2", "HY Bond Spread"),
    ]:
        try:
            data = get_series(sid, limit=1)
            val = data.iloc[-1] if len(data) > 0 else None
            indicators[sid] = {"label": label, "value": val}
        except Exception:
            indicators[sid] = {"label": label, "value": None}
    return indicators


def format_dashboard(dashboard: dict) -> str:
    """Format macro dashboard into readable text."""
    lines = []
    for sid, info in dashboard.items():
        val = info["value"]
        val_str = f"{val:.2f}" if val is not None else "N/A"
        lines.append(f"  {info['label']:<40s} {val_str:>10s}  ({info['date']})")
    return "\n".join(lines)


def format_yield_curve(yc: dict) -> str:
    """Format yield curve into readable text."""
    lines = ["  Maturity   Yield"]
    for label, val in yc["curve"].items():
        val_str = f"{val:.2f}%" if val is not None else "N/A"
        lines.append(f"  {label:<10s}  {val_str}")
    lines.append(f"\n  10Y-2Y Spread: {yc['spread_10y_2y']:.2f}%" if yc["spread_10y_2y"] is not None else "")
    if yc.get("inverted"):
        lines.append("  *** YIELD CURVE INVERTED -- recession warning ***")
    return "\n".join(lines)
