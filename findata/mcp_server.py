"""
findata MCP Server -- exposes financial data tools via Model Context Protocol.

Run:  fastmcp run findata/mcp_server.py
Test: fastmcp dev findata/mcp_server.py
"""

from fastmcp import FastMCP

mcp = FastMCP("findata")


# ============================================================================
# US Stocks (yfinance) -- no API key
# ============================================================================

@mcp.tool
def stock_quote(ticker: str) -> dict:
    """Get real-time stock quote: price, change, volume, market cap, P/E, EPS, 52-week range, sector."""
    from findata.us_stocks import get_quote
    return get_quote(ticker)


@mcp.tool
def stock_history(ticker: str, period: str = "1mo", interval: str = "1d") -> str:
    """Get OHLCV price history. Period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,ytd,max. Interval: 1m,5m,15m,1h,1d,1wk,1mo."""
    from findata.us_stocks import get_history
    df = get_history(ticker, period=period, interval=interval)
    return df.to_string() if not df.empty else "No data"


@mcp.tool
def stock_financials(ticker: str, statement: str = "all", quarterly: bool = False) -> str:
    """Get financial statements (income/balance/cashflow). Statement: 'income','balance','cashflow','all'."""
    from findata.us_stocks import get_financials
    result = get_financials(ticker, statement=statement, quarterly=quarterly)
    parts = []
    for key, df in result.items():
        if df is not None and not df.empty:
            parts.append(f"--- {key.upper()} ---\n{df.to_string()}")
    return "\n\n".join(parts) if parts else "No data"


@mcp.tool
def stock_analyst_ratings(ticker: str) -> dict:
    """Get analyst recommendations: target prices (high/low/mean/median), recommendation, upgrades/downgrades."""
    from findata.us_stocks import get_analyst_ratings
    result = get_analyst_ratings(ticker)
    if result.get("recommendations") is not None:
        result["recommendations"] = result["recommendations"].to_string()
    if result.get("upgrades_downgrades") is not None:
        result["upgrades_downgrades"] = result["upgrades_downgrades"].to_string()
    return result


@mcp.tool
def stock_compare(tickers: str) -> str:
    """Compare multiple stocks side-by-side. Pass comma-separated tickers like 'AAPL,MSFT,GOOGL'."""
    from findata.us_stocks import compare_peers
    ticker_list = [t.strip() for t in tickers.split(",")]
    df = compare_peers(ticker_list)
    return df.to_string() if not df.empty else "No data"


# ============================================================================
# SEC EDGAR -- no API key
# ============================================================================

@mcp.tool
def sec_company_info(ticker: str) -> dict:
    """Get SEC company info: CIK, industry, SIC code, filer category."""
    from findata.sec_edgar import get_company_info
    return get_company_info(ticker)


@mcp.tool
def sec_filings(ticker: str, form_type: str = "10-K", limit: int = 5) -> str:
    """List SEC filings. Form types: '10-K','10-Q','8-K','4','DEF 14A', etc."""
    from findata.sec_edgar import get_filings
    df = get_filings(ticker, form_type=form_type, limit=limit)
    return df.to_string() if not df.empty else "No filings found"


@mcp.tool
def sec_financials(ticker: str) -> str:
    """Get structured financial data from latest 10-K: revenue, net income, FCF, total assets, equity."""
    from findata.sec_edgar import get_financials, format_financial_summary
    result = get_financials(ticker)
    return format_financial_summary(result["summary"])


@mcp.tool
def sec_insider_trades(ticker: str, limit: int = 10) -> str:
    """Get recent Form 4 insider trading filings for a company."""
    from findata.sec_edgar import get_insider_trades
    df = get_insider_trades(ticker, limit=limit)
    return df.to_string() if not df.empty else "No insider trades found"


# ============================================================================
# Crypto (ccxt + CoinGecko) -- no API key
# ============================================================================

@mcp.tool
def crypto_price(symbol: str = "BTC/USDT", exchange: str = "okx") -> dict:
    """Get real-time crypto price from exchange. Symbols: BTC/USDT, ETH/USDT, SOL/USDT, etc."""
    from findata.crypto import get_ticker
    return get_ticker(symbol, exchange)


@mcp.tool
def crypto_ohlcv(symbol: str = "BTC/USDT", timeframe: str = "1d", limit: int = 30) -> str:
    """Get crypto OHLCV K-line data. Timeframes: 1m,5m,15m,1h,4h,1d,1w."""
    from findata.crypto import get_ohlcv
    df = get_ohlcv(symbol, timeframe, limit)
    return df.to_string() if not df.empty else "No data"


@mcp.tool
def crypto_coin_info(coin_id: str = "bitcoin") -> dict:
    """Get coin info from CoinGecko: price, market cap, supply, 24h/7d/30d change, ATH, categories."""
    from findata.crypto import get_coin_info
    return get_coin_info(coin_id)


@mcp.tool
def crypto_trending() -> list:
    """Get trending coins on CoinGecko right now."""
    from findata.crypto import get_trending
    return get_trending()


@mcp.tool
def crypto_top_coins(limit: int = 20) -> str:
    """Get top coins by market cap."""
    from findata.crypto import get_top_coins
    df = get_top_coins(limit=limit)
    return df.to_string() if not df.empty else "No data"


# ============================================================================
# Reddit Sentiment -- no API key
# ============================================================================

@mcp.tool
def reddit_hot_posts(subreddit: str = "wallstreetbets", limit: int = 15) -> str:
    """Get hot posts from a finance subreddit. Subreddits: wallstreetbets, stocks, investing, options, CryptoCurrency."""
    from findata.reddit_sentiment import get_hot_posts, format_post_summary
    df = get_hot_posts(subreddit, limit=limit)
    return format_post_summary(df, max_posts=limit)


@mcp.tool
def reddit_search(query: str, subreddit: str = "wallstreetbets", time_filter: str = "week") -> str:
    """Search within a subreddit for a ticker or topic. Time: hour,day,week,month,year,all."""
    from findata.reddit_sentiment import search_subreddit, format_post_summary
    df = search_subreddit(subreddit, query, time_filter=time_filter)
    return format_post_summary(df) if not df.empty else "No results"


@mcp.tool
def reddit_ticker_mentions(subreddits: str = "wallstreetbets,stocks,investing", limit_per_sub: int = 25) -> str:
    """Scan multiple subreddits and extract most-mentioned stock tickers from post titles."""
    from findata.reddit_sentiment import scan_multiple_subreddits, extract_ticker_mentions
    subs = [s.strip() for s in subreddits.split(",")]
    posts = scan_multiple_subreddits(subs, limit_per_sub=limit_per_sub)
    tickers = extract_ticker_mentions(posts, min_mentions=2)
    return tickers.to_string() if not tickers.empty else "No tickers with 2+ mentions"


# ============================================================================
# Macro Economy (FRED) -- requires FRED_API_KEY
# ============================================================================

@mcp.tool
def macro_dashboard() -> str:
    """Get a snapshot of 12 key macro indicators: Fed funds rate, CPI, unemployment, GDP, oil, VIX, etc."""
    from findata.macro import get_macro_dashboard, format_dashboard
    return format_dashboard(get_macro_dashboard())


@mcp.tool
def macro_yield_curve() -> str:
    """Get current US Treasury yield curve (1M to 30Y) and check for inversion (recession warning)."""
    from findata.macro import get_yield_curve, format_yield_curve
    return format_yield_curve(get_yield_curve())


@mcp.tool
def macro_series(series_id: str, limit: int = 12) -> str:
    """Get a FRED time series by ID. Common: FEDFUNDS, DGS10, CPIAUCSL, UNRATE, VIXCLS, DCOILWTICO."""
    from findata.macro import get_series
    s = get_series(series_id, limit=limit)
    return s.to_string()


# ============================================================================
# FMP (Financial Modeling Prep) -- requires FMP_API_KEY
# ============================================================================

@mcp.tool
def fmp_dcf(ticker: str) -> dict:
    """Get DCF (Discounted Cash Flow) intrinsic value estimate for a stock."""
    from findata.fmp import get_dcf
    return get_dcf(ticker)


@mcp.tool
def fmp_congress_trades(limit: int = 20) -> str:
    """Get recent US Congress stock trading disclosures (House + Senate combined)."""
    from findata.fmp import get_congress_trades, get_senate_trades
    import pandas as pd
    house = get_congress_trades(limit=limit)
    senate = get_senate_trades(limit=limit)
    combined = pd.concat([house, senate], ignore_index=True) if not house.empty or not senate.empty else pd.DataFrame()
    return combined.to_string() if not combined.empty else "No data"


@mcp.tool
def fmp_insider_trades(ticker: str, limit: int = 15) -> str:
    """Get insider trading data (CEO/CFO buying/selling) for a stock."""
    from findata.fmp import get_insider_trades
    df = get_insider_trades(ticker, limit=limit)
    return df.to_string() if not df.empty else "No data"


# ============================================================================
# News (NewsAPI) -- requires NEWSAPI_API_KEY
# ============================================================================

@mcp.tool
def news_search(query: str, days_back: int = 7, page_size: int = 10) -> str:
    """Search global news by keyword. Example queries: 'NVIDIA earnings', 'oil prices', 'Fed rate'."""
    from findata.news import search_news, format_articles
    df = search_news(query, days_back=days_back, page_size=page_size)
    return format_articles(df) if not df.empty else "No articles found"


@mcp.tool
def news_headlines(country: str = "us", category: str = "business") -> str:
    """Get top business headlines. Categories: business, technology, health, science, sports, general."""
    from findata.news import get_top_headlines, format_articles
    df = get_top_headlines(country=country, category=category, page_size=10)
    return format_articles(df) if not df.empty else "No headlines"


if __name__ == "__main__":
    mcp.run()
