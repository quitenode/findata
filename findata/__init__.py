"""
findata - A Python toolkit for financial data acquisition.

No-key modules (work immediately):
    us_stocks          - US stock data via yfinance
    sec_edgar          - SEC EDGAR filings and insider trading
    crypto             - Crypto via ccxt + pycoingecko
    reddit_sentiment   - Reddit financial sentiment

API-key modules (free keys required):
    macro              - FRED macro economy data (FRED_API_KEY)
    forex              - OANDA forex/commodities (OANDA_API_KEY)
    news               - NewsAPI global news (NEWSAPI_API_KEY)
    finnhub_data       - Finnhub quotes/news/insider (FINNHUB_API_KEY)
    polygon_io         - Polygon.io market data (POLYGON_API_KEY)
    fmp                - FMP fundamentals/DCF/congress (FMP_API_KEY)

Shared:
    utils              - Formatting helpers
"""

__version__ = "0.3.0"
