"""Shared helpers for formatting, caching, and display."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd


def fmt_number(value: float | int | None, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"{value / 1e12:.{decimals}f}T"
    if abs_val >= 1e9:
        return f"{value / 1e9:.{decimals}f}B"
    if abs_val >= 1e6:
        return f"{value / 1e6:.{decimals}f}M"
    if abs_val >= 1e3:
        return f"{value / 1e3:.{decimals}f}K"
    return f"{value:.{decimals}f}"


def fmt_percent(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def fmt_currency(value: float | None, decimals: int = 2, symbol: str = "$") -> str:
    if value is None:
        return "N/A"
    return f"{symbol}{value:,.{decimals}f}"


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def df_to_text(df: pd.DataFrame, max_rows: int = 20) -> str:
    """Convert a DataFrame to a readable text table."""
    if df is None or df.empty:
        return "(no data)"
    if len(df) > max_rows:
        return df.head(max_rows).to_string() + f"\n... ({len(df) - max_rows} more rows)"
    return df.to_string()


def print_section(title: str, content: str, width: int = 70) -> None:
    """Print a formatted section with a header."""
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")
    print(content)
