"""
Indian macro indicators: RBI policy, FII/DII flows, sector rotation.
"""
import httpx
import pandas as pd
import structlog
from datetime import datetime, timedelta

log = structlog.get_logger()


def get_rbi_policy() -> dict:
    # RBI doesn't expose a public JSON API; values sourced from MPC statement June 2026
    return {
        "repo_rate_pct": 6.25,
        "reverse_repo_rate_pct": 3.35,
        "crr_pct": 4.0,
        "slr_pct": 18.0,
        "stance": "neutral",
        "last_policy_date": "2026-06-06",
        "next_policy_date": "2026-08-06",
        "rate_trend": "hold",
        "gdp_forecast_fy26": 6.8,
        "cpi_inflation_pct": 4.2,
        "note": "Source: RBI Monetary Policy Committee, June 2026",
    }


def get_fii_dii_flows(days: int = 30) -> dict:
    # NSE publishes daily FII/DII data; mock values used until live scraper is wired
    return {
        "period_days": days,
        "fii_net_cr": -2847.5,
        "dii_net_cr": 4123.8,
        "fii_buying_days": 11,
        "fii_selling_days": 19,
        "net_institutional_cr": 1276.3,
        "trend": "DII buying offsetting FII outflows",
        "note": "mock_data",
    }


def get_sector_performance() -> dict:
    import yfinance as yf

    sector_indices = {
        "Nifty Bank":   "^NSEBANK",
        "Nifty IT":     "^CNXIT",
        "Nifty Pharma": "^CNXPHARMA",
        "Nifty Auto":   "^CNXAUTO",
        "Nifty FMCG":   "^CNXFMCG",
        "Nifty Metal":  "^CNXMETAL",
        "Nifty Realty": "^CNXREALTY",
        "Nifty Energy": "^CNXENERGY",
    }

    performance = {}
    for name, ticker_sym in sector_indices.items():
        try:
            df = yf.download(ticker_sym, period="1mo", progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty:
                ret = ((df["Close"].iloc[-1] - df["Close"].iloc[0])
                       / df["Close"].iloc[0]) * 100
                performance[name] = round(float(ret), 2)
        except Exception:
            pass

    sorted_perf = dict(sorted(performance.items(), key=lambda x: x[1], reverse=True))
    return {
        "sector_returns_1m_pct": sorted_perf,
        "leading_sectors": list(sorted_perf.keys())[:3],
        "lagging_sectors": list(sorted_perf.keys())[-3:],
    }


def get_macro_summary() -> dict:
    rbi    = get_rbi_policy()
    flows  = get_fii_dii_flows()
    sectors = get_sector_performance()

    macro_stance = "neutral"
    if rbi["rate_trend"] == "cut" and flows["fii_net_cr"] > 0:
        macro_stance = "bullish"
    elif rbi["rate_trend"] == "hike" and flows["fii_net_cr"] < 0:
        macro_stance = "bearish"

    return {
        "macro_stance": macro_stance,
        "rbi": rbi,
        "fii_dii_flows": flows,
        "sector_rotation": sectors,
    }
