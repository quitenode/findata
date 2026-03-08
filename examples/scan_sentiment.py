#!/usr/bin/env python3
"""
Reddit financial sentiment scanner -- no API key required.

Usage:
    source ../findata-env/bin/activate
    python scan_sentiment.py                     # WSB hot posts + ticker mentions
    python scan_sentiment.py wallstreetbets      # specific subreddit
    python scan_sentiment.py --search NVDA       # search for a ticker across subs
    python scan_sentiment.py --scan              # scan multiple subs, extract tickers
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from findata import reddit_sentiment as reddit
from findata.utils import print_section, df_to_text


def scan_subreddit(subreddit: str = "wallstreetbets") -> None:
    """Full sentiment scan of a single subreddit."""
    print(f"\n{'#' * 70}")
    print(f"  REDDIT SENTIMENT: r/{subreddit}")
    print(f"{'#' * 70}")

    # Hot posts
    print("\n[1/4] Fetching hot posts...")
    hot = reddit.get_hot_posts(subreddit, limit=25)
    print_section(f"HOT POSTS -- r/{subreddit}", reddit.format_post_summary(hot, max_posts=10))

    # Ticker mentions from hot posts
    print("\n[2/4] Extracting ticker mentions...")
    tickers = reddit.extract_ticker_mentions(hot, min_mentions=1)
    if not tickers.empty:
        print_section("TICKER MENTIONS (from hot posts)", df_to_text(tickers.head(20)))
    else:
        print_section("TICKER MENTIONS", "(no tickers found)")

    # Rising posts
    print("\n[3/4] Fetching rising posts...")
    try:
        rising = reddit.get_rising_posts(subreddit, limit=10)
        print_section(f"RISING POSTS -- r/{subreddit}", reddit.format_post_summary(rising, max_posts=5))
    except Exception as e:
        print(f"  (Rising posts not available: {e})")

    # Top posts this week
    print("\n[4/4] Fetching top posts this week...")
    top = reddit.get_top_posts(subreddit, time_filter="week", limit=10)
    print_section(f"TOP POSTS THIS WEEK -- r/{subreddit}", reddit.format_post_summary(top, max_posts=5))


def search_ticker(ticker: str) -> None:
    """Search for a specific ticker across multiple finance subreddits."""
    print(f"\n{'#' * 70}")
    print(f"  SEARCHING FOR: ${ticker}")
    print(f"{'#' * 70}")

    for sub in ["wallstreetbets", "stocks", "investing", "options"]:
        print(f"\n[Searching r/{sub} for '{ticker}'...]")
        try:
            results = reddit.search_subreddit(
                subreddit=sub,
                query=ticker,
                sort="new",
                time_filter="week",
                limit=10,
            )
            if not results.empty:
                print_section(
                    f"r/{sub} -- '{ticker}' mentions",
                    reddit.format_post_summary(results, max_posts=5),
                )
            else:
                print(f"  (no results in r/{sub})")
        except Exception as e:
            print(f"  (error searching r/{sub}: {e})")


def multi_sub_scan() -> None:
    """Scan multiple subreddits and aggregate ticker mentions."""
    print(f"\n{'#' * 70}")
    print(f"  MULTI-SUBREDDIT SENTIMENT SCAN")
    print(f"{'#' * 70}")

    subs = ["wallstreetbets", "stocks", "investing"]
    print(f"\n[Scanning: {', '.join('r/' + s for s in subs)}...]")

    all_posts = reddit.scan_multiple_subreddits(subs, limit_per_sub=25)
    print(f"\n  Total posts collected: {len(all_posts)}")

    # Per-subreddit summary
    for sub in subs:
        sub_posts = all_posts[all_posts["subreddit"] == sub]
        if not sub_posts.empty:
            print_section(f"r/{sub} ({len(sub_posts)} posts)", reddit.format_post_summary(sub_posts, max_posts=3))

    # Aggregate ticker mentions
    tickers = reddit.extract_ticker_mentions(all_posts, min_mentions=2)
    if not tickers.empty:
        print_section("AGGREGATED TICKER MENTIONS (2+ mentions)", df_to_text(tickers.head(25)))
    else:
        print_section("TICKER MENTIONS", "(no tickers with 2+ mentions)")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--search":
        if len(sys.argv) < 3:
            print("Usage: python scan_sentiment.py --search TICKER")
            sys.exit(1)
        search_ticker(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "--scan":
        multi_sub_scan()
    elif len(sys.argv) > 1:
        scan_subreddit(sys.argv[1])
    else:
        scan_subreddit("wallstreetbets")

    print(f"\n{'=' * 70}")
    print("  Scan complete.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
