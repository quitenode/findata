# findata

A Python toolkit for financial data acquisition. Covers US stocks, crypto, and Reddit sentiment -- all with zero API keys required.

## Setup

```bash
python3 -m venv findata-env
source findata-env/bin/activate
pip install yfinance edgartools requests pandas ccxt pycoingecko
```

## Modules

| Module | Source | Data | API Key |
|---|---|---|---|
| `us_stocks` | yfinance | Quotes, K-lines, financials, analyst ratings, options | No |
| `sec_edgar` | edgartools | SEC filings (10-K/10-Q/8-K), insider trades, XBRL financials | No |
| `crypto` | ccxt + pycoingecko | Exchange tickers, orderbooks, K-lines, coin info, trending | No |
| `reddit_sentiment` | Reddit JSON API | Hot/top/rising posts, ticker extraction, multi-sub scanning | No |

## Quick Start

### US Stock Analysis

```bash
python examples/analyze_stock.py NVDA
python examples/analyze_stock.py AAPL MSFT GOOGL   # peer comparison
```

### Crypto Analysis

```bash
python examples/analyze_crypto.py bitcoin
python examples/analyze_crypto.py --trending
python examples/analyze_crypto.py --top
python examples/analyze_crypto.py bitcoin ethereum solana   # compare
```

### Reddit Sentiment

```bash
python examples/scan_sentiment.py                    # WSB hot posts
python examples/scan_sentiment.py --search NVDA      # find ticker mentions
python examples/scan_sentiment.py --scan             # multi-sub scan + ticker extraction
```

### As a Library

```python
from findata import us_stocks, sec_edgar, crypto, reddit_sentiment

# US stock quote
quote = us_stocks.get_quote("NVDA")
print(us_stocks.format_quote(quote))

# SEC financials
fin = sec_edgar.get_financials("NVDA")
print(sec_edgar.format_financial_summary(fin["summary"]))

# Crypto ticker
ticker = crypto.get_ticker("BTC/USDT")
print(crypto.format_ticker(ticker))

# Reddit sentiment
posts = reddit_sentiment.get_hot_posts("wallstreetbets", limit=25)
tickers = reddit_sentiment.extract_ticker_mentions(posts)
print(tickers)
```

## API Reference

### us_stocks

- `get_quote(ticker)` -- price, change, volume, market cap, P/E, EPS
- `get_history(ticker, period, interval)` -- OHLCV K-line data
- `get_financials(ticker, statement, quarterly)` -- income / balance / cashflow
- `get_analyst_ratings(ticker)` -- target prices, recommendations, upgrades
- `get_news(ticker)` -- recent headlines
- `get_options_chain(ticker, expiration)` -- calls/puts chain
- `compare_peers(tickers)` -- side-by-side comparison table

### sec_edgar

- `get_company_info(ticker)` -- CIK, industry, SIC, filer category
- `get_filings(ticker, form_type, limit)` -- list 10-K, 10-Q, 8-K, Form 4
- `get_financials(ticker, statement)` -- revenue, net income, FCF, assets from 10-K
- `get_insider_trades(ticker, limit)` -- Form 4 insider transaction filings
- `compare_periods(ticker)` -- key metrics across recent annual periods

### crypto

- `get_ticker(symbol, exchange)` -- real-time price from exchange (default: OKX)
- `get_tickers(symbols, exchange)` -- batch fetch multiple pairs
- `get_ohlcv(symbol, timeframe, limit, exchange)` -- K-line candles
- `get_orderbook(symbol, limit, exchange)` -- bids/asks and spread
- `get_funding_rate(symbol, exchange)` -- perpetual contract funding rate
- `get_coin_info(coin_id)` -- CoinGecko metadata, market cap, supply
- `get_trending()` -- trending coins on CoinGecko
- `get_top_coins(vs_currency, limit)` -- top N by market cap
- `get_coin_history(coin_id, vs_currency, days)` -- historical prices
- `search_coins(query)` -- search by name or symbol

### reddit_sentiment

- `get_hot_posts(subreddit, limit)` -- hot posts
- `get_new_posts(subreddit, limit)` -- newest posts
- `get_top_posts(subreddit, time_filter, limit)` -- top posts by time range
- `get_rising_posts(subreddit, limit)` -- rising/trending posts
- `search_subreddit(subreddit, query, sort, time_filter)` -- search within sub
- `get_post_comments(permalink, limit)` -- top-level comments
- `extract_ticker_mentions(posts, min_mentions)` -- extract stock tickers from titles
- `scan_multiple_subreddits(subreddits, limit_per_sub)` -- aggregate across subs

## Notes

- The crypto module defaults to **OKX** as the exchange. Pass `exchange="bybit"` or `exchange="kraken"` to use others. Binance may be geo-blocked depending on location.
- Reddit's public JSON API has no official rate limit but be polite -- the module enforces 1 request/second.
- SEC EDGAR rate limit is 10 requests/second.
