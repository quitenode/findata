# findata -- Financial Data MCP Skill

A financial data toolkit exposing 25 tools via MCP (Model Context Protocol). Covers US stocks, SEC filings, crypto, macro economy, news, Reddit sentiment, and alternative data.

## Tools

### US Stocks (no API key)

| Tool | Description |
|------|-------------|
| `stock_quote` | Real-time quote: price, change, volume, market cap, P/E, sector |
| `stock_history` | OHLCV price history (1min to monthly, up to max history) |
| `stock_financials` | Income statement, balance sheet, cash flow |
| `stock_analyst_ratings` | Target prices, recommendations, upgrades/downgrades |
| `stock_compare` | Side-by-side comparison of multiple tickers |

### SEC EDGAR (no API key)

| Tool | Description |
|------|-------------|
| `sec_company_info` | CIK, industry, SIC code, filer category |
| `sec_filings` | List 10-K, 10-Q, 8-K, Form 4 filings with SEC URLs |
| `sec_financials` | Revenue, net income, FCF, assets from latest 10-K |
| `sec_insider_trades` | Form 4 insider transaction filings |

### Crypto (no API key)

| Tool | Description |
|------|-------------|
| `crypto_price` | Real-time price from exchange (BTC/USDT, ETH/USDT, etc.) |
| `crypto_ohlcv` | K-line candle data (1min to weekly) |
| `crypto_coin_info` | CoinGecko metadata: market cap, supply, 24h/7d/30d change |
| `crypto_trending` | Trending coins on CoinGecko |
| `crypto_top_coins` | Top N coins by market cap |

### Reddit Sentiment (no API key)

| Tool | Description |
|------|-------------|
| `reddit_hot_posts` | Hot posts from WSB, r/stocks, r/investing, etc. |
| `reddit_search` | Search within a subreddit for a ticker or topic |
| `reddit_ticker_mentions` | Scan multiple subs and extract most-mentioned tickers |

### Macro Economy (requires FRED_API_KEY)

| Tool | Description |
|------|-------------|
| `macro_dashboard` | 12 key indicators: Fed rate, CPI, unemployment, GDP, oil, VIX |
| `macro_yield_curve` | Treasury yield curve (1M-30Y) with inversion detection |
| `macro_series` | Any of 800,000+ FRED time series by ID |

### FMP Alternative Data (requires FMP_API_KEY)

| Tool | Description |
|------|-------------|
| `fmp_dcf` | DCF intrinsic value estimate |
| `fmp_congress_trades` | US Congress/Senate stock trading disclosures |
| `fmp_insider_trades` | Insider trading (CEO/CFO buying/selling) |

### News (requires NEWSAPI_API_KEY)

| Tool | Description |
|------|-------------|
| `news_search` | Search global news by keyword |
| `news_headlines` | Top headlines by country and category |

## Example Queries

When connected to an AI agent (OpenClaw, Claude, Cursor), you can ask:

- "What's the current price of NVDA?"
- "Show me AAPL's financial statements"
- "Compare MSFT, GOOGL, and AMZN"
- "What are insiders trading at Tesla?"
- "What's trending on r/wallstreetbets?"
- "Show me the yield curve -- is it inverted?"
- "What are congress members buying?"
- "Search news about oil prices"
- "Get BTC price and 30-day chart"

## Setup

### MCP Server (standalone)

```bash
cd /mnt/raid/michael/findata
source findata-env/bin/activate
fastmcp run findata/mcp_server.py
```

### OpenClaw Integration

Add to `~/.mcporter/mcporter.json`:

```json
{
  "mcpServers": {
    "findata": {
      "command": "/mnt/raid/michael/findata/findata-env/bin/python3",
      "args": ["/mnt/raid/michael/findata/findata/mcp_server.py"]
    }
  }
}
```

### API Keys (optional, for macro/fmp/news tools)

```bash
export FRED_API_KEY="..."
export FMP_API_KEY="..."
export NEWSAPI_API_KEY="..."
```

The 14 tools for stocks, SEC, crypto, and Reddit work without any API keys.
