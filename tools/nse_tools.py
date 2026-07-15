"""NSE/BSE price data via yfinance (.NS / .BO suffix)."""
import time
import yfinance as yf
import pandas as pd
import structlog

log = structlog.get_logger()

NIFTY50 = "^NSEI"
SENSEX  = "^BSESN"


def _ticker(symbol: str) -> str:
    s = symbol.upper().strip()
    if s.startswith("^"):           # index symbols already have the right format
        return s
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    return f"{s}.NS"


def _download(symbol: str, period: str) -> pd.DataFrame:
    df = yf.download(_ticker(symbol), period=period, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _safe_info(symbol: str) -> dict:
    for attempt in range(3):
        try:
            return yf.Ticker(_ticker(symbol)).info or {}
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                log.warning("info_fetch_failed", symbol=symbol, error=str(e)[:80])
                return {}


def get_price_data(symbol: str, period: str = "1y") -> dict:
    try:
        hist = _download(symbol, period)
    except Exception as e:
        return {"error": f"Failed to fetch price data for {symbol}: {str(e)[:80]}"}

    if hist.empty:
        return {"error": f"No price data found for {symbol}"}

    info = _safe_info(symbol)

    current_price = hist["Close"].iloc[-1]
    start_price   = hist["Close"].iloc[0]
    pct_change    = ((current_price - start_price) / start_price) * 100

    high_52w = hist["Close"].max()
    low_52w  = hist["Close"].min()

    ma_50  = hist["Close"].rolling(50).mean().iloc[-1]  if len(hist) >= 50  else None
    ma_200 = hist["Close"].rolling(200).mean().iloc[-1] if len(hist) >= 200 else None

    rsi = _compute_rsi(hist["Close"])

    # NIFTY 50 benchmark
    nifty_return = None
    try:
        nifty_hist = _download(NIFTY50, period)
        if not nifty_hist.empty:
            nifty_return = round(
                ((nifty_hist["Close"].iloc[-1] - nifty_hist["Close"].iloc[0])
                 / nifty_hist["Close"].iloc[0]) * 100, 2
            )
    except Exception:
        pass

    return {
        "symbol":           symbol.upper(),
        "current_price":    round(float(current_price), 2),
        "currency":         "INR",
        "period_return_pct": round(float(pct_change), 2),
        "nifty50_return_pct": nifty_return,
        "alpha_vs_nifty":   round(float(pct_change) - (nifty_return or 0), 2),
        "high_52w":         round(float(high_52w), 2),
        "low_52w":          round(float(low_52w), 2),
        "ma_50":            round(float(ma_50), 2)  if ma_50  is not None else None,
        "ma_200":           round(float(ma_200), 2) if ma_200 is not None else None,
        "rsi_14":           round(float(rsi), 2)    if rsi    is not None else None,
        "avg_daily_volume": int(hist["Volume"].mean()),
        "company_name":     info.get("longName", symbol),
        "sector":           info.get("sector", ""),
        "industry":         info.get("industry", ""),
    }


def get_fundamentals(symbol: str) -> dict:
    info = _safe_info(symbol)

    if not info or (info.get("trailingPE") is None and info.get("marketCap") is None):
        return {"error": f"Fundamental data unavailable for {symbol}"}

    return {
        "symbol":              symbol.upper(),
        "market_cap_cr":       _to_crores(info.get("marketCap")),
        "pe_ratio":            _safe(info.get("trailingPE")),
        "forward_pe":          _safe(info.get("forwardPE")),
        "pb_ratio":            _safe(info.get("priceToBook")),
        "ev_ebitda":           _safe(info.get("enterpriseToEbitda")),
        "roe_pct":             _safe_pct(info.get("returnOnEquity")),
        "roce_pct":            None,
        "debt_to_equity":      _safe(info.get("debtToEquity")),
        "current_ratio":       _safe(info.get("currentRatio")),
        "revenue_cr":          _to_crores(info.get("totalRevenue")),
        "net_profit_cr":       _to_crores(info.get("netIncomeToCommon")),
        "net_margin_pct":      _safe_pct(info.get("profitMargins")),
        "dividend_yield_pct":  _safe_pct(info.get("dividendYield")),
        "promoter_holding_pct": None,
        "eps_ttm":             _safe(info.get("trailingEps")),
        "book_value":          _safe(info.get("bookValue")),
        "sector":              info.get("sector", ""),
        "industry":            info.get("industry", ""),
    }


def get_financials_trend(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(_ticker(symbol))
        quarterly = ticker.quarterly_financials
        if quarterly is None or quarterly.empty:
            return {"error": "Quarterly financials unavailable"}

        trend = {}
        for row_name, key in [("Total Revenue", "quarterly_revenue_cr"),
                               ("Net Income",    "quarterly_net_profit_cr")]:
            if row_name in quarterly.index:
                trend[key] = {
                    str(col.date()): _to_crores(val)
                    for col, val in quarterly.loc[row_name].items()
                    if pd.notna(val)
                }
        return trend
    except Exception as e:
        log.warning("financials_trend_error", symbol=symbol, error=str(e))
        return {"error": str(e)}


def _compute_rsi(prices: pd.Series, window: int = 14) -> float | None:
    if len(prices) < window + 1:
        return None
    delta = prices.diff()
    gain  = delta.clip(lower=0).rolling(window).mean()
    loss  = (-delta.clip(upper=0)).rolling(window).mean()
    rs    = gain / loss
    return (100 - (100 / (1 + rs))).iloc[-1]


def _safe(val) -> float | None:
    try:
        return round(float(val), 2) if val is not None else None
    except (TypeError, ValueError):
        return None


def _safe_pct(val) -> float | None:
    try:
        return round(float(val) * 100, 2) if val is not None else None
    except (TypeError, ValueError):
        return None


def _to_crores(val) -> float | None:
    try:
        return round(float(val) / 1e7, 2) if val is not None else None
    except (TypeError, ValueError):
        return None
