"""RBI policy, FII/DII flows, and sector rotation signals."""
import structlog
from core.llm_client import LLMClient
from tools.macro_tools import get_macro_summary
from tools.nse_tools import get_fundamentals

log = structlog.get_logger()


class MacroAgent:
    NAME = "macro_agent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, symbol: str, query: str) -> dict:
        log.info("agent_start", agent=self.NAME, symbol=symbol)

        macro = get_macro_summary()
        fundamentals = get_fundamentals(symbol)
        sector = fundamentals.get("sector", "Unknown")

        analysis = self._interpret(symbol, query, sector, macro)

        return {
            "agent": self.NAME,
            "symbol": symbol,
            "sector": sector,
            "macro_data": macro,
            "analysis": analysis,
        }

    def _interpret(self, symbol: str, query: str, sector: str, macro: dict) -> str:
        rbi = macro["rbi"]
        flows = macro["fii_dii_flows"]
        rotation = macro["sector_rotation"]

        leading = ", ".join(rotation.get("leading_sectors", []))
        lagging = ", ".join(rotation.get("lagging_sectors", []))

        prompt = f"""You are a macro strategist at an Indian asset management company.

Stock: {symbol} | Sector: {sector}
User Query: {query}

RBI Monetary Policy:
- Repo Rate: {rbi.get('repo_rate_pct')}% | Stance: {rbi.get('stance')}
- Rate Trend: {rbi.get('rate_trend')} | CPI Inflation: {rbi.get('cpi_inflation_pct')}%
- GDP Forecast FY26: {rbi.get('gdp_forecast_fy26')}%
- Next Policy Date: {rbi.get('next_policy_date')}

FII/DII Flows (last 30 days):
- FII Net: Rs {flows.get('fii_net_cr')} Cr ({flows.get('fii_buying_days')} buy days, {flows.get('fii_selling_days')} sell days)
- DII Net: Rs {flows.get('dii_net_cr')} Cr
- Overall Trend: {flows.get('trend')}

Sector Rotation (1-month returns):
- Leading sectors: {leading}
- Lagging sectors: {lagging}
- Overall Macro Stance: {macro.get('macro_stance').upper()}

Write a concise 3-4 sentence macro analysis for {symbol}.
Specifically address:
1. How RBI rate stance impacts this company's sector
2. Whether FII flows are a tailwind or headwind
3. Whether this stock's sector is in favor or out of favor right now
4. Overall macro verdict: TAILWIND / HEADWIND / NEUTRAL"""

        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            query_id=f"ma_{symbol}",
        )
        return response["content"]
