"""SEC EDGAR data via edgartools -- filings, financials, insider trades.

Free, no API key required. Rate limit: 10 requests/second.
Requires: edgar.set_identity() to be called once before use.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

import edgar

from .utils import fmt_currency, fmt_number

_IDENTITY_SET = False


def _ensure_identity():
    global _IDENTITY_SET
    if not _IDENTITY_SET:
        edgar.set_identity("findata-toolkit research@example.com")
        _IDENTITY_SET = True


def get_company(ticker: str) -> edgar.Company:
    """Get an edgar Company object (cached helper)."""
    _ensure_identity()
    return edgar.Company(ticker)


def get_company_info(ticker: str) -> dict:
    """Get company overview: name, CIK, industry, SIC, filer category, etc."""
    c = get_company(ticker)
    return {
        "ticker": ticker.upper(),
        "name": c.name,
        "cik": c.cik,
        "sic": c.sic,
        "industry": c.industry,
        "tickers": c.tickers,
        "fiscal_year_end": c.fiscal_year_end,
        "is_large_accelerated": c.is_large_accelerated_filer,
        "is_foreign": c.is_foreign,
    }


def get_filings(
    ticker: str,
    form_type: str = "10-K",
    limit: int = 5,
) -> pd.DataFrame:
    """List recent filings of a given form type.

    Args:
        form_type: '10-K', '10-Q', '8-K', '4', 'DEF 14A', etc.
        limit: max number of filings to return.
    """
    c = get_company(ticker)
    filings = c.get_filings(form=form_type)

    rows = []
    for i, f in enumerate(filings):
        if i >= limit:
            break
        rows.append({
            "filed": str(f.filing_date),
            "form": f.form,
            "accession": f.accession_no,
            "description": f.primary_doc_description or "",
            "url": f.filing_url or "",
        })

    return pd.DataFrame(rows)


def get_financials(
    ticker: str,
    statement: Literal["income", "balance", "cashflow", "all"] = "all",
) -> dict:
    """Get structured financial data from latest 10-K.

    Returns dict with:
        - 'summary': key metrics (revenue, net income, FCF, etc.)
        - 'income' / 'balance' / 'cashflow': Statement text representations
    """
    c = get_company(ticker)
    fin = c.get_financials()

    result = {
        "summary": {
            "revenue": fin.get_revenue(),
            "net_income": fin.get_net_income(),
            "free_cash_flow": fin.get_free_cash_flow(),
            "total_assets": fin.get_total_assets(),
            "total_liabilities": fin.get_total_liabilities(),
            "stockholders_equity": fin.get_stockholders_equity(),
            "operating_income": fin.get_operating_income(),
            "operating_cash_flow": fin.get_operating_cash_flow(),
            "capex": fin.get_capital_expenditures(),
        }
    }

    if statement in ("income", "all"):
        try:
            result["income"] = str(fin.income_statement())
        except Exception:
            result["income"] = "(not available)"

    if statement in ("balance", "all"):
        try:
            result["balance"] = str(fin.balance_sheet())
        except Exception:
            result["balance"] = "(not available)"

    if statement in ("cashflow", "all"):
        try:
            result["cashflow"] = str(fin.cash_flow_statement())
        except Exception:
            result["cashflow"] = "(not available)"

    return result


def get_insider_trades(ticker: str, limit: int = 10) -> pd.DataFrame:
    """Get recent Form 4 insider transaction filings.

    Returns a DataFrame with filing date, accession number, and report date.
    """
    c = get_company(ticker)
    filings = c.get_filings(form="4")

    rows = []
    for i, f in enumerate(filings):
        if i >= limit:
            break
        rows.append({
            "filed": str(f.filing_date),
            "report_date": str(f.report_date) if f.report_date else "",
            "accession": f.accession_no,
            "url": f.filing_url or "",
        })

    return pd.DataFrame(rows)


def compare_periods(
    ticker: str,
    num_periods: int = 3,
) -> dict:
    """Compare key financial metrics across recent annual periods.

    Uses the structured data from the latest 10-K which typically
    includes 2-3 years of comparative data.
    """
    c = get_company(ticker)
    fin = c.get_financials()

    metrics = {}
    for name, getter in [
        ("Revenue", fin.get_revenue),
        ("Net Income", fin.get_net_income),
        ("Operating Income", fin.get_operating_income),
        ("Free Cash Flow", fin.get_free_cash_flow),
        ("Total Assets", fin.get_total_assets),
        ("Total Liabilities", fin.get_total_liabilities),
        ("Stockholders Equity", fin.get_stockholders_equity),
    ]:
        try:
            value = getter()
            metrics[name] = fmt_number(value) if value else "N/A"
        except Exception:
            metrics[name] = "N/A"

    return metrics


def format_company_info(info: dict) -> str:
    """Format company info dict into a readable string."""
    lines = [
        f"{info['name']} ({info['ticker']})",
        f"  CIK:            {info['cik']}",
        f"  Industry:       {info['industry']}",
        f"  SIC Code:       {info['sic']}",
        f"  Fiscal Year End: {info['fiscal_year_end']}",
        f"  Tickers:        {', '.join(info['tickers'])}",
    ]
    return "\n".join(lines)


def format_financial_summary(summary: dict) -> str:
    """Format the financial summary into a readable string."""
    lines = []
    for label, key in [
        ("Revenue", "revenue"),
        ("Net Income", "net_income"),
        ("Operating Income", "operating_income"),
        ("Free Cash Flow", "free_cash_flow"),
        ("Op. Cash Flow", "operating_cash_flow"),
        ("CapEx", "capex"),
        ("Total Assets", "total_assets"),
        ("Total Liabilities", "total_liabilities"),
        ("Equity", "stockholders_equity"),
    ]:
        val = summary.get(key)
        lines.append(f"  {label:<20s} {fmt_currency(val, 0) if val else 'N/A'}")
    return "\n".join(lines)
