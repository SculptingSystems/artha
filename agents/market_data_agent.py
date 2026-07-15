"""Price action, technicals, and NIFTY 50 benchmark comparison."""
import structlog
from core.llm_client import LLMClient
from tools.nse_tools import get_price_data

log = structlog.get_logger()


class MarketDataAgent:
    NAME = "market_data_agent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, symbol: str, query: str) -> dict:
        log.info("agent_start", agent=self.NAME, symbol=symbol)

        raw = get_price_data(symbol, period="1y")
        if "error" in raw:
            return {"agent": self.NAME, "error": raw["error"], "data": {}}

        analysis = self._interpret(symbol, query, raw)

        return {
            "agent": self.NAME,
            "symbol": symbol,
            "raw_data": raw,
            "analysis": analysis,
        }

    def _interpret(self, symbol: str, query: str, data: dict) -> str:
        prompt = f"""You are a technical analyst covering Indian equity markets.

Stock: {symbol}
User Query: {query}

Market Data:
- Current Price: Rs {data.get('current_price')}
- 1Y Return: {data.get('period_return_pct')}% vs NIFTY 50: {data.get('nifty50_return_pct')}%
- Alpha vs NIFTY: {data.get('alpha_vs_nifty')}%
- 52-Week High: Rs {data.get('high_52w')} | Low: Rs {data.get('low_52w')}
- 50-Day MA: Rs {data.get('ma_50')} | 200-Day MA: Rs {data.get('ma_200')}
- RSI (14): {data.get('rsi_14')}
- Avg Daily Volume: {data.get('avg_daily_volume'):,}

Write a concise 3-4 sentence technical analysis. Comment on trend, momentum (RSI),
relative performance vs benchmark, and any notable technical levels. Be specific with numbers."""

        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            query_id=f"mda_{symbol}",
        )
        return response["content"]
