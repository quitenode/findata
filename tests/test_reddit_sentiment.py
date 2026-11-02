import pandas as pd
import pytest
import requests

from findata import reddit_sentiment as rs

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <author><name>/u/alice</name></author>
    <category term="wallstreetbets" label="r/wallstreetbets"/>
    <link href="https://www.reddit.com/r/wallstreetbets/comments/1/a/"/>
    <published>2026-10-31T16:03:00+00:00</published>
    <title>NVDA earnings &amp;amp; the Fed</title>
  </entry>
  <entry>
    <author><name>/u/bob</name></author>
    <category term="Stocks" label="r/Stocks"/>
    <link href="https://www.reddit.com/r/stocks/comments/2/b/"/>
    <updated>2026-10-31T17:00:00+00:00</updated>
    <title>Oil above $100 again</title>
  </entry>
</feed>"""


class FakeResp:
    def __init__(self, status=200, body=b"", payload=None, headers=None):
        self.status_code, self.content, self._payload = status, body, payload
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._payload


@pytest.fixture
def fake_reddit(monkeypatch):
    """Route _SESSION.get to canned responses; records requested URLs."""
    calls = []
    monkeypatch.setattr(rs, "_rate_limit", lambda: None)
    monkeypatch.setattr(rs, "_JSON_BLOCKED", False)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)

    def install(responder):
        def get(url, params=None, timeout=None):
            calls.append(url)
            return responder(url)
        monkeypatch.setattr(rs._SESSION, "get", get)
        return calls
    return install


def test_detect_themes_uses_word_boundaries_and_case():
    titles = [
        "He said it again, wait for it",       # 'ai' inside words must not count
        "I'm fed up with this toil",           # lower-case 'fed', 'oil' inside 'toil'
        "Toward a better portfolio",           # 'war' inside 'toward'
        "AI capex is huge",
        "Nvidia guidance beats on AI demand",
        "Fed holds rates; Powell speaks",
        "Powell says inflation is sticky",
    ]
    themes = dict(rs.detect_themes(titles))
    assert themes == {"AI/tech": 2, "Fed/rates": 2}


def test_detect_themes_min_posts():
    assert rs.detect_themes(["Oil spikes"]) == []
    assert rs.detect_themes(["Oil spikes"], min_posts=1) == [("oil", 1)]


def test_rss_fallback_on_403(fake_reddit):
    calls = fake_reddit(lambda url: FakeResp(403) if url.endswith(".json") else FakeResp(body=ATOM.encode()))
    df = rs.get_hot_posts("wallstreetbets", limit=5)
    assert calls == ["https://www.reddit.com/r/wallstreetbets/hot.json",
                     "https://www.reddit.com/r/wallstreetbets/hot/.rss"]
    assert df["title"].tolist() == ["NVDA earnings & the Fed", "Oil above $100 again"]
    assert df["author"].tolist() == ["alice", "bob"]
    assert df["created_utc"].tolist() == ["2026-10-31 16:03", "2026-10-31 17:00"]
    assert df["score"].isna().all()

    # After a 403 the JSON endpoint is skipped
    rs.get_hot_posts("stocks")
    assert calls[-1] == "https://www.reddit.com/r/stocks/hot/.rss"


def test_json_path_unchanged(fake_reddit):
    payload = {"data": {"children": [{"kind": "t3", "data": {
        "title": "TSLA &amp; RIVN to the moon", "score": 42, "num_comments": 7, "permalink": "/r/x/1",
        "subreddit": "wallstreetbets", "created_utc": 0}}]}}
    fake_reddit(lambda url: FakeResp(payload=payload))
    df = rs.get_hot_posts("wallstreetbets")
    assert df.loc[0, "score"] == 42 and df.loc[0, "url"] == "https://reddit.com/r/x/1"
    assert df.loc[0, "title"] == "TSLA & RIVN to the moon"


def test_rss_retries_once_after_429(fake_reddit):
    state = {"rss": 0}

    def responder(url):
        if url.endswith(".json"):
            return FakeResp(403)
        state["rss"] += 1
        return FakeResp(429, headers={"x-ratelimit-reset": "5"}) if state["rss"] == 1 else FakeResp(body=ATOM.encode())
    fake_reddit(responder)
    assert len(rs.get_hot_posts("wallstreetbets")) == 2
    assert state["rss"] == 2


def test_scan_uses_one_multireddit_request(fake_reddit):
    calls = fake_reddit(lambda url: FakeResp(403) if url.endswith(".json") else FakeResp(body=ATOM.encode()))
    df = rs.scan_multiple_subreddits(["wallstreetbets", "stocks", "investing"], limit_per_sub=1)
    assert calls[-1] == "https://www.reddit.com/r/wallstreetbets+stocks+investing/hot/.rss"
    # Feed casing ("Stocks") is mapped back to the requested name
    assert df["subreddit"].tolist() == ["wallstreetbets", "stocks"]


def test_scan_returns_empty_on_failure(fake_reddit):
    fake_reddit(lambda url: FakeResp(500))
    assert rs.scan_multiple_subreddits(["stocks"]).empty


def test_extract_ticker_mentions_skips_common_words():
    posts = pd.DataFrame({"title": ["NVDA and AMD rally", "Buy NVDA NOW", "THE END"]})
    got = dict(zip(*rs.extract_ticker_mentions(posts, min_mentions=1).to_dict("list").values()))
    assert got == {"NVDA": 2, "AMD": 1, "END": 1}


def test_format_post_summary_without_scores():
    posts = pd.DataFrame([{"title": "Hello", "score": None, "num_comments": None, "flair": "",
                           "subreddit": "stocks", "created_utc": "2026-10-31 17:00"}])
    out = rs.format_post_summary(posts)
    assert "[     -] Hello" in out and "comments" not in out
