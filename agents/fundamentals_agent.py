"""Valuation ratios, profitability, and balance sheet analysis."""
import structlog
from core.llm_client import LLMClient
from tools.nse_tools import get_fundamentals, get_financials_trend

log = structlog.get_logger()

SECTOR_PE = {
    "Technology":           28,
    "Financial Services":   18,
    "Consumer Defensive":   45,
    "Healthcare":           30,
    "Energy":               12,
    "Basic Materials":      10,
    "Industrials":          25,
    "Consumer Cyclical":    35,
    "Communication Services": 22,
    "Utilities":            15,
    "Real Estate":          40,
}


class FundamentalsAgent:
    NAME = "fundamentals_agent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, symbol: str, query: str) -> dict:
        log.info("agent_start", agent=self.NAME, symbol=symbol)

        fundamentals = get_fundamentals(symbol)
        if "error" in fundamentals:
            return {"agent": self.NAME, "error": fundamentals["error"], "data": {}}

        trend = get_financials_trend(symbol)
        sector = fundamentals.get("sector", "")
        sector_pe = SECTOR_PE.get(sector, 25)

        analysis = self._interpret(symbol, query, fundamentals, trend, sector_pe)

        return {
            "agent": self.NAME,
            "symbol": symbol,
            "raw_data": {**fundamentals, "financials_trend": trend},
            "sector_avg_pe": sector_pe,
            "analysis": analysis,
        }

    def _interpret(self, symbol: str, query: str, data: dict, trend: dict, sector_pe: int) -> str:
        pe = data.get("pe_ratio")
        valuation_comment = ""
        if pe and sector_pe:
            if pe < sector_pe * 0.8:
                valuation_comment = f"P/E of {pe}x is ~{round((1 - pe/sector_pe)*100)}% below sector average ({sector_pe}x), potentially undervalued."
            elif pe > sector_pe * 1.2:
                valuation_comment = f"P/E of {pe}x is ~{round((pe/sector_pe - 1)*100)}% above sector average ({sector_pe}x), premium valuation."
            else:
                valuation_comment = f"P/E of {pe}x is in line with sector average ({sector_pe}x), fair value."

        prompt = f"""You are a fundamental analyst covering Indian equity markets (NSE/BSE).

Stock: {symbol} | Sector: {data.get('sector', 'N/A')}
User Query: {query}

Valuation:
- Market Cap: Rs {data.get('market_cap_cr')} Cr
- P/E (TTM): {data.get('pe_ratio')}x | Forward P/E: {data.get('forward_pe')}x
- P/B Ratio: {data.get('pb_ratio')}x | EV/EBITDA: {data.get('ev_ebitda')}x
- {valuation_comment}

Profitability:
- ROE: {data.get('roe_pct')}% | Net Margin: {data.get('net_margin_pct')}%
- Revenue: Rs {data.get('revenue_cr')} Cr | Net Profit: Rs {data.get('net_profit_cr')} Cr
- EPS (TTM): Rs {data.get('eps_ttm')}

Balance Sheet:
- Debt/Equity: {data.get('debt_to_equity')} | Current Ratio: {data.get('current_ratio')}
- Dividend Yield: {data.get('dividend_yield_pct')}%

Write a concise 4-5 sentence fundamental analysis. Assess valuation (cheap/fair/expensive vs sector),
profitability quality, balance sheet strength, and growth trend. Be specific with numbers.
Flag any red flags (high debt, declining margins, etc.)."""

        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            query_id=f"fa_{symbol}",
        )
        return response["content"]
