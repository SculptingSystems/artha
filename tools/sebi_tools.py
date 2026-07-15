"""
SEBI and NSE regulatory data: bulk deals, block deals, shareholding patterns.
"""
import httpx
import structlog

log = structlog.get_logger()

NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com",
}


def get_bulk_deals(symbol: str) -> list[dict]:
    clean = symbol.upper().replace(".NS", "").replace(".BO", "")
    url = f"{NSE_BASE}/api/bulk-deal-archives?symbol={clean}"

    try:
        with httpx.Client(timeout=10, headers=NSE_HEADERS) as client:
            client.get(NSE_BASE, timeout=5)
            resp = client.get(url)
            resp.raise_for_status()
            deals = resp.json().get("data", [])[:10]
            return [
                {
                    "date":     d.get("BD_DT_DATE", ""),
                    "client":   d.get("BD_CLIENT_NAME", ""),
                    "buy_sell": d.get("BD_BUY_SELL", ""),
                    "quantity": d.get("BD_QTY_TRD", 0),
                    "price":    d.get("BD_TP_WATP", 0),
                }
                for d in deals
            ]
    except Exception as e:
        log.warning("bulk_deals_error", symbol=symbol, error=str(e))
        return _mock_bulk_deals(clean)


def get_shareholding_pattern(symbol: str) -> dict:
    clean = symbol.upper().replace(".NS", "").replace(".BO", "")
    url = (
        f"{NSE_BASE}/api/corporate-shareholding-pattern"
        f"?symbol={clean}&series=EQ&from=&to=&dataType=shareholdings"
    )

    try:
        with httpx.Client(timeout=10, headers=NSE_HEADERS) as client:
            client.get(NSE_BASE, timeout=5)
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            latest = data.get("data", [{}])[0] if data.get("data") else {}
            return {
                "promoter_holding_pct": latest.get("promoterAndPromoterGroupTotal"),
                "fii_holding_pct":      latest.get("foreignPortfolioInvestors"),
                "dii_holding_pct":      latest.get("mutualFunds"),
                "public_holding_pct":   latest.get("publicTotal"),
                "quarter":              latest.get("date", ""),
            }
    except Exception as e:
        log.warning("shareholding_error", symbol=symbol, error=str(e))
        return _mock_shareholding(clean)


def _mock_bulk_deals(symbol: str) -> list[dict]:
    return [
        {
            "date":     "2026-06-15",
            "client":   "ICICI Prudential Mutual Fund",
            "buy_sell": "BUY",
            "quantity": 1500000,
            "price":    0,
            "note":     "mock_data",
        }
    ]


def _mock_shareholding(symbol: str) -> dict:
    defaults = {
        "RELIANCE":  {"promoter": 50.3, "fii": 24.1, "dii": 8.7,  "public": 16.9},
        "TCS":       {"promoter": 72.3, "fii": 13.7, "dii": 5.4,  "public": 8.6},
        "HDFCBANK":  {"promoter": 26.0, "fii": 27.8, "dii": 22.3, "public": 23.9},
        "INFY":      {"promoter": 14.9, "fii": 33.4, "dii": 19.6, "public": 32.1},
        "ICICIBANK": {"promoter": 0.0,  "fii": 44.3, "dii": 27.1, "public": 28.6},
    }
    d = defaults.get(symbol, {"promoter": 45.0, "fii": 20.0, "dii": 15.0, "public": 20.0})
    return {
        "promoter_holding_pct": d["promoter"],
        "fii_holding_pct":      d["fii"],
        "dii_holding_pct":      d["dii"],
        "public_holding_pct":   d["public"],
        "quarter":              "Q4 FY2026",
        "note":                 "mock_data",
    }
