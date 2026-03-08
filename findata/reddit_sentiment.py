"""Reddit sentiment data via public JSON API -- no API key required.

Covers r/wallstreetbets, r/stocks, r/investing, r/CryptoCurrency, etc.
Rate limit: be polite (1 req/sec is safe, Reddit may 429 if hammered).
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import pandas as pd
import requests

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "findata-toolkit/0.1 (research)"})

_LAST_REQUEST_TIME = 0.0
_MIN_INTERVAL = 1.0

FINANCE_SUBREDDITS = [
    "wallstreetbets",
    "stocks",
    "investing",
    "CryptoCurrency",
    "options",
    "StockMarket",
    "ValueInvesting",
    "Superstonk",
]


def _rate_limit():
    """Enforce minimum interval between requests."""
    global _LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - _LAST_REQUEST_TIME
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_REQUEST_TIME = time.time()


def _fetch_json(url: str, params: dict | None = None) -> dict:
    _rate_limit()
    resp = _SESSION.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _parse_post(post_data: dict) -> dict:
    """Extract key fields from a Reddit post's data dict."""
    d = post_data
    created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
    return {
        "title": d.get("title", ""),
        "score": d.get("score", 0),
        "upvote_ratio": d.get("upvote_ratio"),
        "num_comments": d.get("num_comments", 0),
        "author": d.get("author", ""),
        "flair": d.get("link_flair_text", ""),
        "created_utc": created.strftime("%Y-%m-%d %H:%M"),
        "url": f"https://reddit.com{d.get('permalink', '')}",
        "selftext": (d.get("selftext") or "")[:500],
        "subreddit": d.get("subreddit", ""),
        "is_self": d.get("is_self", False),
    }


def get_hot_posts(
    subreddit: str = "wallstreetbets",
    limit: int = 20,
) -> pd.DataFrame:
    """Get hot posts from a subreddit."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    data = _fetch_json(url, params={"limit": limit})
    posts = [_parse_post(p["data"]) for p in data["data"]["children"] if p["kind"] == "t3"]
    return pd.DataFrame(posts)


def get_new_posts(
    subreddit: str = "wallstreetbets",
    limit: int = 20,
) -> pd.DataFrame:
    """Get newest posts from a subreddit."""
    url = f"https://www.reddit.com/r/{subreddit}/new.json"
    data = _fetch_json(url, params={"limit": limit})
    posts = [_parse_post(p["data"]) for p in data["data"]["children"] if p["kind"] == "t3"]
    return pd.DataFrame(posts)


def get_top_posts(
    subreddit: str = "wallstreetbets",
    time_filter: str = "week",
    limit: int = 20,
) -> pd.DataFrame:
    """Get top posts from a subreddit.

    Args:
        time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
    """
    url = f"https://www.reddit.com/r/{subreddit}/top.json"
    data = _fetch_json(url, params={"limit": limit, "t": time_filter})
    posts = [_parse_post(p["data"]) for p in data["data"]["children"] if p["kind"] == "t3"]
    return pd.DataFrame(posts)


def get_rising_posts(
    subreddit: str = "wallstreetbets",
    limit: int = 20,
) -> pd.DataFrame:
    """Get rising posts (trending up) from a subreddit."""
    url = f"https://www.reddit.com/r/{subreddit}/rising.json"
    data = _fetch_json(url, params={"limit": limit})
    posts = [_parse_post(p["data"]) for p in data["data"]["children"] if p["kind"] == "t3"]
    return pd.DataFrame(posts)


def search_subreddit(
    subreddit: str = "wallstreetbets",
    query: str = "NVDA",
    sort: str = "relevance",
    time_filter: str = "week",
    limit: int = 15,
) -> pd.DataFrame:
    """Search within a subreddit.

    Args:
        sort: 'relevance', 'hot', 'top', 'new', 'comments'
        time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
    """
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "restrict_sr": "on",
        "sort": sort,
        "t": time_filter,
        "limit": limit,
    }
    data = _fetch_json(url, params=params)
    posts = [_parse_post(p["data"]) for p in data["data"]["children"] if p["kind"] == "t3"]
    return pd.DataFrame(posts)


def get_post_comments(
    permalink: str,
    limit: int = 20,
) -> list[dict]:
    """Get top-level comments from a post.

    Args:
        permalink: Reddit permalink path, e.g. '/r/wallstreetbets/comments/abc123/...'
    """
    if permalink.startswith("https://reddit.com"):
        permalink = permalink.replace("https://reddit.com", "")
    url = f"https://www.reddit.com{permalink}.json"
    data = _fetch_json(url, params={"limit": limit})

    if not isinstance(data, list) or len(data) < 2:
        return []

    comments = []
    for c in data[1]["data"]["children"]:
        if c["kind"] != "t1":
            continue
        cd = c["data"]
        comments.append({
            "author": cd.get("author", ""),
            "score": cd.get("score", 0),
            "body": (cd.get("body") or "")[:400],
            "created_utc": datetime.fromtimestamp(
                cd.get("created_utc", 0), tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M"),
        })
    return comments[:limit]


_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")

_COMMON_WORDS = {
    "I", "A", "THE", "TO", "IS", "IN", "IT", "AND", "OR", "FOR", "ON", "AT",
    "BE", "AS", "SO", "IF", "DO", "NO", "UP", "BY", "OF", "AN", "AM", "PM",
    "DD", "YOLO", "HODL", "FUD", "FOMO", "ATH", "DCA", "IPO", "ETF", "SEC",
    "CEO", "CFO", "CTO", "WSB", "IMO", "LOL", "OMG", "WTF", "LFG", "TBH",
    "RIP", "OG", "FYI", "AMA", "ETA", "AI", "USA", "USD", "EU", "UK", "GDP",
    "CPI", "NYSE", "ALL", "NEW", "NOW", "BIG", "PUT", "CALL", "SELL", "BUY",
    "MY", "NOT", "ARE", "HAS", "WAS", "HIS", "HER", "OUT", "OLD", "TOP",
    "ANY", "OUR", "MAY", "WAY", "DAY", "DIP", "RUN", "RED", "EOD", "ATM",
    "OTM", "ITM", "IV", "PE", "EPS", "ROE", "RSI", "SMA", "EMA",
    "US", "GO", "UP", "TD", "VS", "YO", "YOY", "RE", "IRS", "PP",
    "OR", "AN", "AM", "PM", "NO", "SO", "DO", "WE", "HE", "WHO", "WHAT",
    "HOW", "WHY", "THIS", "THAT", "WILL", "JUST", "LIKE", "BEEN", "BEEN",
    "MUCH", "THAN", "MORE", "MOST", "ONLY", "ALSO", "OVER", "VERY",
    "INTO", "SOME", "TIME", "YEAR", "LONG", "BACK", "EVEN", "MAKE",
    "WEEK", "STILL", "NEXT", "LAST", "GOOD", "BEST", "HIGH", "LOW",
    "FREE", "HOLD", "POST", "LOVE", "HATE", "KEEP", "HELP", "LOOK",
    "THINK", "KNOW", "WANT", "NEED", "RATE", "DOWN", "CASH", "GAIN",
    "LOSS", "TAX", "FED", "DOW", "BEAR", "BULL", "MOON", "PUMP", "DUMP",
    "OTC", "ETF", "NFT", "APR", "APY", "DEBT", "FUND", "BOND", "RISK",
    "EDIT", "UPDATE", "READ", "LINK", "SHARE", "SAVE", "OPEN", "CLOSE",
    "VOL", "ROTH", "IRA", "YTD", "QTD", "REAL", "HOPE",
}


def extract_ticker_mentions(
    posts: pd.DataFrame,
    min_mentions: int = 2,
) -> pd.DataFrame:
    """Extract and count stock ticker mentions from post titles.

    Filters out common English words and acronyms.
    """
    counts: dict[str, int] = {}
    for title in posts["title"]:
        matches = _TICKER_RE.findall(title)
        seen_in_post = set()
        for m in matches:
            if m not in _COMMON_WORDS and m not in seen_in_post:
                counts[m] = counts.get(m, 0) + 1
                seen_in_post.add(m)

    rows = [
        {"ticker": t, "mentions": c}
        for t, c in sorted(counts.items(), key=lambda x: -x[1])
        if c >= min_mentions
    ]
    return pd.DataFrame(rows)


def scan_multiple_subreddits(
    subreddits: list[str] | None = None,
    limit_per_sub: int = 25,
) -> pd.DataFrame:
    """Scan hot posts across multiple finance subreddits and return all combined."""
    subs = subreddits or ["wallstreetbets", "stocks", "investing"]
    all_posts = []
    for sub in subs:
        try:
            df = get_hot_posts(sub, limit=limit_per_sub)
            all_posts.append(df)
        except Exception:
            continue
    if not all_posts:
        return pd.DataFrame()
    return pd.concat(all_posts, ignore_index=True)


def format_post_summary(posts: pd.DataFrame, max_posts: int = 10) -> str:
    """Format posts DataFrame into a readable summary."""
    lines = []
    for _, row in posts.head(max_posts).iterrows():
        flair = f" [{row['flair']}]" if row.get("flair") else ""
        lines.append(
            f"  [{row['score']:>6}] {row['title'][:65]}{flair}\n"
            f"         r/{row['subreddit']} | {row['num_comments']} comments | {row['created_utc']}"
        )
    return "\n".join(lines)
