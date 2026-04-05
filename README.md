# findata

A Python toolkit for financial data acquisition covering US stocks, crypto, forex, macro economy, news, and Reddit sentiment. 14 data sources, 10 modules.

## Setup

```bash
python3 -m venv findata-env
source findata-env/bin/activate
pip install yfinance edgartools requests pandas ccxt pycoingecko \
            fredapi oandapyV20 newsapi-python finnhub-python polygon-api-client
```

## Modules

### No API key required (work immediately)

| Module | Source | Data |
|---|---|---|
| `us_stocks` | yfinance | Quotes, K-lines, financials, analyst ratings, options |
| `sec_edgar` | edgartools | SEC filings (10-K/10-Q/8-K), insider trades, XBRL financials |
| `crypto` | ccxt + pycoingecko | Exchange tickers, orderbooks, K-lines, coin info, trending |
| `reddit_sentiment` | Reddit JSON API | Hot/top/rising posts, ticker extraction, multi-sub scanning |

### Free API key required

| Module | Source | Key env var | Free tier | Signup |
|---|---|---|---|---|
| `macro` | FRED | `FRED_API_KEY` | 120 req/min | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `forex` | OANDA | `OANDA_API_KEY` + `OANDA_ACCOUNT_ID` | Practice account | [oanda.com](https://www.oanda.com/register) |
| `news` | NewsAPI | `NEWSAPI_API_KEY` | 100 req/day | [newsapi.org](https://newsapi.org/register) |
| `finnhub_data` | Finnhub | `FINNHUB_API_KEY` | 60 req/min | [finnhub.io](https://finnhub.io/register) |
| `polygon_io` | Polygon.io | `POLYGON_API_KEY` | 5 req/min | [polygon.io](https://polygon.io/pricing) |
| `fmp` | FMP | `FMP_API_KEY` | 250 req/day | [financialmodelingprep.com](https://site.financialmodelingprep.com/register) |

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

### macro (FRED)

- `list_common_series()` -- 18 key macro series IDs and descriptions
- `get_series(series_id, start, end, limit)` -- fetch any FRED time series
- `get_series_info(series_id)` -- metadata about a series
- `search_series(query, limit)` -- search 800K+ FRED series
- `get_macro_dashboard()` -- snapshot of 12 key indicators
- `get_yield_curve()` -- current yield curve + inversion detection
- `get_recession_indicators()` -- Sahm rule, 10Y-2Y spread, unemployment

### forex (OANDA)

- `get_price(instrument)` -- real-time bid/ask for any instrument
- `get_prices_batch(instruments)` -- batch price fetch
- `get_candles(instrument, granularity, count)` -- OHLCV from 5-second to monthly
- `get_order_book(instrument)` -- pending order distribution
- `get_position_book(instrument)` -- open position distribution (retail sentiment)
- `get_account_info()` -- account balance and margin
- `get_forex_dashboard()` -- major pairs + gold + oil + BTC snapshot

### news (NewsAPI)

- `search_news(query, language, sort_by, days_back)` -- search articles by keyword
- `get_top_headlines(country, category, query)` -- top headlines by country/category
- `get_news_sources(category, language, country)` -- available news sources

### finnhub_data

- `get_quote(ticker)` -- real-time quote
- `get_company_profile(ticker)` -- industry, market cap, IPO date
- `get_company_news(ticker, days_back)` -- company-specific news
- `get_analyst_recommendations(ticker)` -- buy/hold/sell trends
- `get_price_target(ticker)` -- analyst consensus target
- `get_insider_transactions(ticker)` -- Form 4 insider trades
- `get_earnings_calendar(start, end)` -- upcoming earnings dates
- `get_basic_financials(ticker)` -- P/E, ROE, margins, beta
- `get_market_status()` -- exchange open/close status

### polygon_io

- `get_ticker_details(ticker)` -- company info, market cap, employees
- `get_daily_bars(ticker, days)` -- daily OHLCV with VWAP
- `get_intraday_bars(ticker, multiplier, timespan)` -- minute/hour bars
- `get_previous_close(ticker)` -- last trading day's data
- `get_grouped_daily(date)` -- all tickers for one day (market snapshot)
- `search_tickers(query, market)` -- search stocks/crypto/fx
- `get_related_companies(ticker)` -- peer companies
- `get_stock_splits(ticker)` -- split history
- `get_dividends(ticker)` -- dividend history

### fmp (Financial Modeling Prep)

- `get_profile(ticker)` / `get_quote(ticker)` -- company data and quotes
- `get_income_statement(ticker)` / `get_balance_sheet(ticker)` / `get_cash_flow(ticker)` -- financial statements
- `get_dcf(ticker)` -- DCF intrinsic value estimate
- `get_analyst_estimates(ticker)` -- EPS/revenue estimates
- `get_insider_trades(ticker)` -- insider trading data
- `get_senate_trades()` / `get_congress_trades()` -- politician stock trades
- `get_institutional_holders(ticker)` -- 13F institutional holdings
- `get_technical_indicators(ticker, indicator)` -- RSI, SMA, EMA, MACD
- `get_esg_score(ticker)` -- ESG scores
- `get_market_gainers()` / `get_market_losers()` / `get_market_most_active()` -- market movers
- `get_sector_performance()` -- sector heatmap

## API Key Setup

Set environment variables for modules that require them:

```bash
export FRED_API_KEY="your_key"
export OANDA_API_KEY="your_key"
export OANDA_ACCOUNT_ID="your_account_id"
export NEWSAPI_API_KEY="your_key"
export FINNHUB_API_KEY="your_key"
export POLYGON_API_KEY="your_key"
export FMP_API_KEY="your_key"
```

Add to `~/.bashrc` to persist across sessions.

## Dashboard

Live dashboard: **https://quitenode.github.io/findata/**

- Live price ticker (BTC, ETH, SOL, SPY, QQQ, NVDA) -- updates every 30 seconds
- Charts, sector heatmap, Reddit sentiment
- Daily prediction reports (EN/CN toggle)

### Automation (GitHub Actions)

| Workflow | Schedule | What it does |
|---|---|---|
| **Daily Prediction** | 6:30 AM PT, Mon-Fri | Full report (EN/CN markdown + PDF), updates dashboard |
| **Data Refresh** | Every 15 min during market hours | Updates `data.json` for the dashboard |

All times are Pacific Time. Reports are saved to `predictions/YYYY-MM-DD/`.

## Notes

- The crypto module defaults to **OKX** as the exchange. Pass `exchange="bybit"` or `exchange="kraken"` to use others. Binance may be geo-blocked depending on location.
- Reddit's public JSON API has no official rate limit but be polite -- the module enforces 1 request/second.
- SEC EDGAR rate limit is 10 requests/second.
- FMP uses the new `/stable/` endpoints (old `/api/v3/` deprecated 2025-08-31).
- OANDA uses practice environment by default (real-time prices, virtual balance).
