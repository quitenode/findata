"""Global financial news via NewsAPI.

Search news by keyword, category, country, and language.
Requires: NEWSAPI_API_KEY environment variable (free 100 req/day at https://newsapi.org/register)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
from newsapi import NewsApiClient

from .utils import safe_get

_client: NewsApiClient | None = None


def _get_client() -> NewsApiClient:
    global _client
    if _client is None:
        key = os.environ.get("NEWSAPI_API_KEY")
        if not key:
            raise RuntimeError(
                "NEWSAPI_API_KEY not set. Get a free key at "
                "https://newsapi.org/register\n"
                "Then: export NEWSAPI_API_KEY='your_key'"
            )
        _client = NewsApiClient(api_key=key)
    return _client


def search_news(
    query: str,
    language: str = "en",
    sort_by: str = "relevancy",
    days_back: int = 7,
    page_size: int = 20,
) -> pd.DataFrame:
    """Search for news articles by keyword.

    Args:
        query: search query (e.g. 'NVIDIA', 'interest rate', 'bitcoin crash')
        sort_by: 'relevancy', 'popularity', 'publishedAt'
        days_back: how many days back to search
        page_size: number of results (max 100)
    """
    client = _get_client()
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    resp = client.get_everything(
        q=query,
        language=language,
        sort_by=sort_by,
        from_param=from_date,
        page_size=page_size,
    )
    return _parse_articles(resp.get("articles", []))


def get_top_headlines(
    country: str = "us",
    category: str | None = "business",
    query: str | None = None,
    page_size: int = 20,
) -> pd.DataFrame:
    """Get top headlines by country and category.

    Args:
        country: 2-letter country code (us, gb, cn, jp, de, etc.)
        category: 'business', 'entertainment', 'general', 'health',
                  'science', 'sports', 'technology'
        query: optional keyword filter
    """
    client = _get_client()
    kwargs = {"country": country, "page_size": page_size}
    if category:
        kwargs["category"] = category
    if query:
        kwargs["q"] = query

    resp = client.get_top_headlines(**kwargs)
    return _parse_articles(resp.get("articles", []))


def get_news_sources(
    category: str | None = "business",
    language: str = "en",
    country: str | None = None,
) -> pd.DataFrame:
    """Get available news sources."""
    client = _get_client()
    kwargs = {"language": language}
    if category:
        kwargs["category"] = category
    if country:
        kwargs["country"] = country

    resp = client.get_sources(**kwargs)
    sources = resp.get("sources", [])
    rows = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "category": s.get("category"),
            "language": s.get("language"),
            "country": s.get("country"),
            "url": s.get("url"),
        }
        for s in sources
    ]
    return pd.DataFrame(rows)


def _parse_articles(articles: list[dict]) -> pd.DataFrame:
    rows = []
    for a in articles:
        rows.append({
            "title": a.get("title", ""),
            "source": safe_get(a, "source", "name", default=""),
            "author": a.get("author", ""),
            "published": a.get("publishedAt", "")[:16],
            "description": (a.get("description") or "")[:200],
            "url": a.get("url", ""),
        })
    return pd.DataFrame(rows)


def format_articles(df: pd.DataFrame, max_articles: int = 10) -> str:
    """Format articles DataFrame into readable text."""
    lines = []
    for _, row in df.head(max_articles).iterrows():
        lines.append(
            f"  [{row['source']}] {row['title']}\n"
            f"    {row['published']} | {row['author']}\n"
            f"    {row['url']}"
        )
    return "\n\n".join(lines)
