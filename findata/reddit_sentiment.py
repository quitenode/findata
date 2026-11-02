"""Reddit sentiment data via public JSON API -- no API key required.

Covers r/wallstreetbets, r/stocks, r/investing, r/CryptoCurrency, etc.
Rate limit: be polite (1 req/sec is safe, Reddit may 429 if hammered).
"""

from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
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


_ATOM = "{http://www.w3.org/2005/Atom}"


def _fetch_rss(url: str, params: dict | None = None) -> list[dict]:
    """Fetch a listing from Reddit's Atom feed.

    Reddit answers many .json requests with 403 "Blocked" (datacenter and
    corporate IPs) while the .rss feed of the same listing still works. The feed
    has no score or comment count, so those come back as None.
    """
    for attempt in range(2):
        _rate_limit()
        resp = _SESSION.get(url, params=params, timeout=10)
        if resp.status_code != 429 or attempt:
            break
        # The feed allows roughly one anonymous request per minute; wait out the window once
        wait = resp.headers.get("x-ratelimit-reset") or resp.headers.get("Retry-After") or 10
        time.sleep(min(float(wait), 60) + 1)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    posts = []
    for e in root.iter(f"{_ATOM}entry"):
        link = e.find(f"{_ATOM}link")
        cat = e.find(f"{_ATOM}category")
        when = e.findtext(f"{_ATOM}published") or e.findtext(f"{_ATOM}updated") or ""
        posts.append({
            "title": html.unescape(e.findtext(f"{_ATOM}title") or ""),
            "score": None,
            "upvote_ratio": None,
            "num_comments": None,
            "author": (e.findtext(f"{_ATOM}author/{_ATOM}name") or "").removeprefix("/u/"),
            "flair": "",
            "created_utc": when[:16].replace("T", " "),
            "url": link.get("href", "") if link is not None else "",
            "selftext": "",
            "subreddit": cat.get("term", "") if cat is not None else "",
            "is_self": None,
        })
    return posts


_JSON_BLOCKED = False  # set after the first 403 so later calls go straight to RSS


def _listing(subreddit: str, sort: str, params: dict) -> pd.DataFrame:
    """Posts from /r/<subreddit>/<sort>, via JSON with an RSS fallback."""
    global _JSON_BLOCKED
    base = f"https://www.reddit.com/r/{subreddit}/{sort}"
    if not _JSON_BLOCKED:
        try:
            data = _fetch_json(f"{base}.json", params=params)
            return pd.DataFrame([_parse_post(p["data"]) for p in data["data"]["children"] if p["kind"] == "t3"])
        except requests.HTTPError as e:
            _JSON_BLOCKED = e.response is not None and e.response.status_code == 403
        except (requests.RequestException, ValueError):
            pass
    return pd.DataFrame(_fetch_rss(f"{base}/.rss", params=params))


def _parse_post(post_data: dict) -> dict:
    """Extract key fields from a Reddit post's data dict."""
    d = post_data
    created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
    return {
        "title": html.unescape(d.get("title", "")),  # titles arrive HTML-escaped ("&amp;")
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
    return _listing(subreddit, "hot", {"limit": limit})


def get_new_posts(
    subreddit: str = "wallstreetbets",
    limit: int = 20,
) -> pd.DataFrame:
    """Get newest posts from a subreddit."""
    return _listing(subreddit, "new", {"limit": limit})


def get_top_posts(
    subreddit: str = "wallstreetbets",
    time_filter: str = "week",
    limit: int = 20,
) -> pd.DataFrame:
    """Get top posts from a subreddit.

    Args:
        time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
    """
    return _listing(subreddit, "top", {"limit": limit, "t": time_filter})


def get_rising_posts(
    subreddit: str = "wallstreetbets",
    limit: int = 20,
) -> pd.DataFrame:
    """Get rising posts (trending up) from a subreddit."""
    return _listing(subreddit, "rising", {"limit": limit})


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


# Macro themes for report "Key Factors". Patterns are word-bounded and
# case-insensitive; acronyms are case-sensitive via (?-i:...) so "AI" does not
# match "said" and "Fed" does not match "fed up".
THEME_PATTERNS: dict[str, list[str]] = {
    "oil": [r"\boil\b", r"\bcrude\b", r"(?-i:\bOPEC\b)", r"\bbrent\b"],
    "war/geopolitics": [r"\bwars?\b", r"\bIran\b", r"\bIraq\b", r"\bconflict\b", r"\bsanctions?\b", r"\bmissiles?\b"],
    "Fed/rates": [r"(?-i:\bFed\b)", r"\brate (?:cut|hike)s?\b", r"\binterest rates?\b", r"(?-i:\bFOMC\b)", r"\bPowell\b", r"\binflation\b", r"(?-i:\bCPI\b)"],
    "AI/tech": [r"(?-i:\bAI\b)", r"\bartificial intelligence\b", r"(?-i:\bGPUs?\b)", r"\bchips?\b", r"\bnvidia\b", r"\bsemiconductors?\b"],
    "earnings": [r"\bearnings\b", r"\brevenue\b", r"(?-i:\bEPS\b)", r"\bguidance\b"],
    "recession": [r"\brecession\b", r"\bcrash(?:es|ed)?\b", r"\bcorrection\b", r"\bdownturn\b", r"\bbear market\b"],
    "crypto rally": [r"\bbitcoin rally\b", r"\bcrypto surge\b", r"(?-i:\bBTC\b) pump", r"\bbull run\b"],
}
_THEME_RES = {k: re.compile("|".join(v), re.IGNORECASE) for k, v in THEME_PATTERNS.items()}


def detect_themes(titles: list[str], min_posts: int = 2) -> list[tuple[str, int]]:
    """Return (theme, number of titles mentioning it), most-mentioned first.

    A theme needs at least `min_posts` matching titles to count as dominant.
    """
    counts = {k: sum(1 for t in titles if rx.search(t or "")) for k, rx in _THEME_RES.items()}
    return sorted(((k, c) for k, c in counts.items() if c >= min_posts), key=lambda x: -x[1])


def scan_multiple_subreddits(
    subreddits: list[str] | None = None,
    limit_per_sub: int = 25,
) -> pd.DataFrame:
    """Scan hot posts across multiple finance subreddits and return all combined.

    Uses one multireddit request (/r/a+b+c/hot) rather than one per subreddit,
    since the RSS fallback only allows about one request per minute.
    """
    subs = subreddits or ["wallstreetbets", "stocks", "investing"]
    try:
        df = _listing("+".join(subs), "hot", {"limit": 100})
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    names = {s.lower(): s for s in subs}
    df["subreddit"] = df["subreddit"].str.lower().map(names)
    df = df[df["subreddit"].notna()]
    return df.groupby("subreddit", sort=False).head(limit_per_sub).reset_index(drop=True)


def format_post_summary(posts: pd.DataFrame, max_posts: int = 10) -> str:
    """Format posts DataFrame into a readable summary."""
    lines = []
    for _, row in posts.head(max_posts).iterrows():
        flair = f" [{row['flair']}]" if pd.notna(row.get("flair")) and row.get("flair") else ""
        # Posts from the RSS fallback carry no score / comment count
        score = f"{int(row['score']):>6}" if pd.notna(row.get("score")) else f"{'-':>6}"
        comments = f" | {int(row['num_comments'])} comments" if pd.notna(row.get("num_comments")) else ""
        lines.append(
            f"  [{score}] {row['title'][:65]}{flair}\n"
            f"         r/{row['subreddit']}{comments} | {row['created_utc']}"
        )
    return "\n".join(lines)
