#!/usr/bin/env python3
"""
Comprehensive stock analysis combining yfinance and SEC EDGAR data.

Usage:
    source ../findata-env/bin/activate
    python analyze_stock.py NVDA
    python analyze_stock.py AAPL MSFT GOOGL   # peer comparison
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from findata import us_stocks, sec_edgar
from findata.utils import print_section, df_to_text, fmt_number


def analyze_single(ticker: str) -> None:
    """Run a full analysis on a single ticker."""
    print(f"\n{'#' * 70}")
    print(f"  COMPREHENSIVE ANALYSIS: {ticker.upper()}")
    print(f"{'#' * 70}")

    # --- Market Data (yfinance) ---
    print("\n[1/6] Fetching market quote...")
    quote = us_stocks.get_quote(ticker)
    print_section("MARKET QUOTE", us_stocks.format_quote(quote))

    # --- SEC Company Info ---
    print("\n[2/6] Fetching SEC company info...")
    info = sec_edgar.get_company_info(ticker)
    print_section("SEC COMPANY INFO", sec_edgar.format_company_info(info))

    # --- SEC Financials ---
    print("\n[3/6] Fetching SEC financials (latest 10-K)...")
    fin = sec_edgar.get_financials(ticker)
    print_section(
        "FINANCIAL SUMMARY (SEC 10-K)",
        sec_edgar.format_financial_summary(fin["summary"]),
    )

    # --- Analyst Ratings (yfinance) ---
    print("\n[4/6] Fetching analyst ratings...")
    ratings = us_stocks.get_analyst_ratings(ticker)
    ratings_text = (
        f"  Recommendation:  {ratings.get('recommendation', 'N/A')}\n"
        f"  # Analysts:      {ratings.get('num_analysts', 'N/A')}\n"
        f"  Target Mean:     ${ratings.get('target_mean', 'N/A')}\n"
        f"  Target Median:   ${ratings.get('target_median', 'N/A')}\n"
        f"  Target High:     ${ratings.get('target_high', 'N/A')}\n"
        f"  Target Low:      ${ratings.get('target_low', 'N/A')}"
    )
    print_section("ANALYST RATINGS", ratings_text)

    if ratings.get("upgrades_downgrades") is not None:
        print_section(
            "RECENT UPGRADES / DOWNGRADES",
            df_to_text(ratings["upgrades_downgrades"]),
        )

    # --- Recent Filings ---
    print("\n[5/6] Fetching recent SEC filings...")
    for form in ["10-K", "10-Q", "8-K"]:
        filings_df = sec_edgar.get_filings(ticker, form_type=form, limit=3)
        if not filings_df.empty:
            print_section(f"RECENT {form} FILINGS", df_to_text(filings_df))

    # --- Insider Trades ---
    print("\n[6/6] Fetching insider trades (Form 4)...")
    insiders = sec_edgar.get_insider_trades(ticker, limit=10)
    if not insiders.empty:
        print_section("RECENT INSIDER TRADES (Form 4)", df_to_text(insiders))
    else:
        print_section("RECENT INSIDER TRADES", "(no data)")

    # --- Price History (last 30 days) ---
    hist = us_stocks.get_history(ticker, period="1mo", interval="1d")
    if not hist.empty:
        print_section("PRICE HISTORY (Last 30 Days)", df_to_text(hist))


def compare_tickers(tickers: list[str]) -> None:
    """Side-by-side comparison of multiple tickers."""
    print(f"\n{'#' * 70}")
    print(f"  PEER COMPARISON: {', '.join(t.upper() for t in tickers)}")
    print(f"{'#' * 70}")

    comparison = us_stocks.compare_peers(tickers)
    print_section("PEER COMPARISON", df_to_text(comparison))

    print("\n--- SEC Financial Summaries ---")
    for ticker in tickers:
        try:
            fin = sec_edgar.get_financials(ticker, statement="all")
            print_section(
                f"{ticker.upper()} - SEC 10-K SUMMARY",
                sec_edgar.format_financial_summary(fin["summary"]),
            )
        except Exception as e:
            print(f"\n  {ticker.upper()}: Error fetching SEC data: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_stock.py TICKER [TICKER2 ...]")
        print("  Single:  python analyze_stock.py NVDA")
        print("  Compare: python analyze_stock.py AAPL MSFT GOOGL")
        sys.exit(1)

    tickers = [t.upper() for t in sys.argv[1:]]

    if len(tickers) == 1:
        analyze_single(tickers[0])
    else:
        compare_tickers(tickers)

    print(f"\n{'=' * 70}")
    print("  Analysis complete.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
