import json
from datetime import datetime, timedelta, timezone

import pandas as pd

import daily_prediction
import update_dashboard
from findata import us_stocks


def _write_snapshot(tmp_path, fetched):
    path = tmp_path / "data.json"
    data = {"reddit": [{"subreddit": "stocks", "posts": [{"title": "x"}]}]}
    if fetched is not None:
        data["reddit_fetched"] = fetched
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_load_fresh_reddit_keeps_recent_snapshot(tmp_path):
    fetched = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="minutes")
    reddit, when = update_dashboard.load_fresh_reddit(_write_snapshot(tmp_path, fetched))
    assert reddit[0]["subreddit"] == "stocks" and when == fetched


def test_load_fresh_reddit_drops_stale_or_undated_snapshot(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(timespec="minutes")
    assert update_dashboard.load_fresh_reddit(_write_snapshot(tmp_path, old)) == ([], None)
    assert update_dashboard.load_fresh_reddit(_write_snapshot(tmp_path, None)) == ([], None)
    assert update_dashboard.load_fresh_reddit(str(tmp_path / "missing.json")) == ([], None)


def test_load_fresh_reddit_max_age(tmp_path):
    fetched = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="minutes")
    path = _write_snapshot(tmp_path, fetched)
    assert update_dashboard.load_fresh_reddit(path, timedelta(hours=2)) == ([], None)


def test_compute_technicals():
    closes = [100 + i for i in range(60)]  # steady uptrend
    t = update_dashboard._compute_technicals(closes, closes, closes, [1000] * 60)
    assert t["rsi"]["value"] == 100.0 and t["rsi"]["signal"] == "bearish"  # overbought
    assert t["sma20"]["signal"] == t["sma50"]["signal"] == "bullish"
    assert t["macd"]["signal"] == "bullish"
    assert t["high_3m"]["value"] == 159 and t["low_3m"]["value"] == 100


def test_sanitize_for_json_replaces_nan():
    clean = update_dashboard.sanitize_for_json({"a": float("nan"), "b": [1.5, float("inf")]})
    assert json.dumps(clean, allow_nan=False) == '{"a": null, "b": [1.5, null]}'


def test_post_line_with_and_without_score():
    row = pd.Series({"title": "Hello", "score": 12, "flair": "News"})
    assert daily_prediction.post_line(row, "pts") == "- [   12 pts] Hello `News`"
    row = pd.Series({"title": "Hello", "score": float("nan"), "flair": float("nan")})
    assert daily_prediction.post_line(row, "pts") == "- Hello"


def test_get_news_falls_back_to_search(monkeypatch):
    class Ticker:
        news = []

    class Search:
        def __init__(self, query, news_count=8):
            self.news = [
                {"title": "Other", "publisher": "B", "link": "https://b", "providerPublishTime": 2, "relatedTickers": ["MSFT", "NVDA"]},
                {"title": "Mine", "publisher": "A", "link": "https://a", "providerPublishTime": 1, "relatedTickers": ["NVDA"]},
            ]
    monkeypatch.setattr(us_stocks.yf, "Ticker", lambda t: Ticker())
    monkeypatch.setattr(us_stocks.yf, "Search", Search)
    news = us_stocks.get_news("NVDA")
    assert [n["title"] for n in news] == ["Mine", "Other"]
    assert news[0]["publisher"] == "A" and news[0]["link"] == "https://a"


def test_get_news_nested_shape(monkeypatch):
    class Ticker:
        news = [{"content": {"title": "T", "provider": {"displayName": "Reuters"},
                             "canonicalUrl": {"url": "https://r"}, "pubDate": "2026-10-31T00:00:00Z"}}]
    monkeypatch.setattr(us_stocks.yf, "Ticker", lambda t: Ticker())
    n = us_stocks.get_news("NVDA")[0]
    assert (n["publisher"], n["link"], n["published"]) == ("Reuters", "https://r", "2026-10-31T00:00:00Z")
