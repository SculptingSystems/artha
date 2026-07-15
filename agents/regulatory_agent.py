"""SEBI bulk deals, shareholding pattern, and risk flag detection."""
import structlog
from core.llm_client import LLMClient
from tools.sebi_tools import get_bulk_deals, get_shareholding_pattern

log = structlog.get_logger()


class RegulatoryAgent:
    NAME = "regulatory_agent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, symbol: str, query: str) -> dict:
        log.info("agent_start", agent=self.NAME, symbol=symbol)

        shareholding = get_shareholding_pattern(symbol)
        bulk_deals = get_bulk_deals(symbol)

        flags = self._detect_flags(shareholding, bulk_deals)
        analysis = self._interpret(symbol, query, shareholding, bulk_deals, flags)

        return {
            "agent": self.NAME,
            "symbol": symbol,
            "shareholding": shareholding,
            "bulk_deals": bulk_deals,
            "risk_flags": flags,
            "analysis": analysis,
        }

    def _detect_flags(self, shareholding: dict, bulk_deals: list) -> list[str]:
        flags = []

        promoter = shareholding.get("promoter_holding_pct") or 0
        if promoter < 20:
            flags.append(f"Low promoter holding ({promoter}%) - check founder alignment")
        elif promoter > 75:
            flags.append(f"High promoter holding ({promoter}%) - minority shareholder risk")

        fii = shareholding.get("fii_holding_pct") or 0
        if fii < 5:
            flags.append("Low FII holding - not on global institutional radar")
        elif fii > 40:
            flags.append(f"High FII holding ({fii}%) - watch for global risk-off selling")

        sells = [d for d in bulk_deals if "sell" in str(d.get("buy_sell", "")).lower()]
        if len(sells) > 2:
            flags.append(f"{len(sells)} recent bulk sell transactions - institutional distribution")

        return flags

    def _interpret(self, symbol: str, query: str, shareholding: dict, bulk_deals: list, flags: list) -> str:
        deals_text = "\n".join(
            f"  - {d.get('date')}: {d.get('client')} {d.get('buy_sell')} {d.get('quantity'):,} shares"
            for d in bulk_deals[:5]
        ) if bulk_deals else "  No recent bulk deals"

        prompt = f"""You are a SEBI regulatory analyst covering Indian equity markets.

Stock: {symbol}
User Query: {query}

Shareholding Pattern (latest quarter):
- Promoter Holding: {shareholding.get('promoter_holding_pct')}%
- FII Holding: {shareholding.get('fii_holding_pct')}%
- DII Holding: {shareholding.get('dii_holding_pct')}%
- Public: {shareholding.get('public_holding_pct')}%

Recent Bulk/Block Deals:
{deals_text}

Risk Flags Detected:
{chr(10).join(f'  ⚠ {f}' for f in flags) if flags else '  None detected'}

Write a concise 3-4 sentence regulatory analysis. Comment on:
- Promoter holding quality and any pledging concerns
- Institutional (FII/DII) interest as a confidence signal
- What bulk deal activity suggests about institutional conviction
- Overall regulatory risk level: LOW / MEDIUM / HIGH"""

        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            query_id=f"ra_{symbol}",
        )
        return response["content"]
