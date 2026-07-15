"""Runs all agents in parallel and writes the investment memo."""
import re
import concurrent.futures
import structlog

from core.llm_client import LLMClient
from core.memory import AnalysisMemory
from core.cost_tracker import cost_tracker
from agents.market_data_agent import MarketDataAgent
from agents.fundamentals_agent import FundamentalsAgent
from agents.news_sentiment_agent import NewsSentimentAgent
from agents.regulatory_agent import RegulatoryAgent
from agents.macro_agent import MacroAgent

log = structlog.get_logger()

# Common Indian stock symbols for query parsing
KNOWN_SYMBOLS = {
    "reliance": "RELIANCE", "ril": "RELIANCE",
    "tcs": "TCS", "tata consultancy": "TCS",
    "infosys": "INFY", "infy": "INFY",
    "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK", "hdfc": "HDFCBANK",
    "icici bank": "ICICIBANK", "icici": "ICICIBANK",
    "wipro": "WIPRO",
    "bajaj finance": "BAJFINANCE", "bajfinance": "BAJFINANCE",
    "kotak": "KOTAKBANK", "kotak bank": "KOTAKBANK",
    "sbi": "SBIN", "state bank": "SBIN",
    "itc": "ITC",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI",
    "asian paints": "ASIANPAINT",
    "sun pharma": "SUNPHARMA",
    "titan": "TITAN",
    "adani ports": "ADANIPORTS",
    "adani enterprises": "ADANIENT",
    "l&t": "LT", "larsen": "LT",
    "hcl tech": "HCLTECH", "hcl": "HCLTECH",
    "nifty": "^NSEI", "sensex": "^BSESN",
}


class Orchestrator:
    def __init__(self):
        self.llm = LLMClient()
        self.memory = AnalysisMemory()
        self.market_agent = MarketDataAgent(self.llm)
        self.fundamentals_agent = FundamentalsAgent(self.llm)
        self.news_agent = NewsSentimentAgent(self.llm)
        self.regulatory_agent = RegulatoryAgent(self.llm)
        self.macro_agent = MacroAgent(self.llm)

    def analyze(self, query: str) -> dict:
        log.info("orchestrator_start", query=query)

        symbol = self._extract_symbol(query)
        if not symbol:
            return {
                "error": "Could not identify a stock symbol in your query.",
                "hint": "Try: 'Analyze TCS' or 'Should I buy Reliance Industries?'",
            }

        past_analyses = self.memory.recall(query=query, symbol=symbol, n_results=2)

        results = self._run_agents_parallel(symbol, query)

        memo = self._synthesize(query, symbol, results, past_analyses)

        self.memory.save(symbol=symbol, query=query, memo=memo)

        memo["cost_summary"] = cost_tracker.session_summary()
        log.info("orchestrator_complete", symbol=symbol, verdict=memo.get("verdict"))
        return memo

    def _run_agents_parallel(self, symbol: str, query: str) -> dict:
        tasks = {
            "market":      lambda: self.market_agent.run(symbol, query),
            "fundamentals": lambda: self.fundamentals_agent.run(symbol, query),
            "news":        lambda: self.news_agent.run(symbol, query),
            "regulatory":  lambda: self.regulatory_agent.run(symbol, query),
            "macro":       lambda: self.macro_agent.run(symbol, query),
        }

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(fn): name for name, fn in tasks.items()}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result(timeout=30)
                    log.info("agent_complete", agent=name)
                except Exception as e:
                    log.error("agent_failed", agent=name, error=str(e))
                    results[name] = {"agent": name, "error": str(e), "analysis": "Unavailable."}

        return results

    def _synthesize(self, query: str, symbol: str, results: dict, past_analyses: list) -> dict:
        market = results.get("market", {})
        fundamentals = results.get("fundamentals", {})
        news = results.get("news", {})
        regulatory = results.get("regulatory", {})
        macro = results.get("macro", {})

        price = market.get("raw_data", {}).get("current_price", "N/A")
        period_return = market.get("raw_data", {}).get("period_return_pct", "N/A")
        nifty_return = market.get("raw_data", {}).get("nifty50_return_pct", "N/A")
        pe = fundamentals.get("raw_data", {}).get("pe_ratio", "N/A")
        roe = fundamentals.get("raw_data", {}).get("roe_pct", "N/A")
        promoter = regulatory.get("shareholding", {}).get("promoter_holding_pct", "N/A")
        sentiment = news.get("sentiment", "NEUTRAL")
        risk_flags = regulatory.get("risk_flags", [])
        macro_stance = macro.get("macro_data", {}).get("macro_stance", "neutral")

        past_context = ""
        if past_analyses:
            past_context = "\n\nPast Analyses in Memory:\n" + "\n---\n".join(
                f"[{p['metadata'].get('timestamp', '')}] {p['document'][:300]}"
                for p in past_analyses
            )

        prompt = f"""You are the chief investment analyst at an Indian wealth management firm.
Five specialist agents have analyzed {symbol}. Synthesize their findings into a final investment memo.

User Query: {query}

AGENT FINDINGS SUMMARY:

1. MARKET DATA:
{market.get('analysis', 'N/A')}
Price: Rs {price} | 1Y Return: {period_return}% vs NIFTY: {nifty_return}%

2. FUNDAMENTALS:
{fundamentals.get('analysis', 'N/A')}
P/E: {pe}x | ROE: {roe}%

3. NEWS & SENTIMENT: {sentiment}
{news.get('analysis', 'N/A')}
Key Themes: {', '.join(news.get('key_themes', []))}

4. REGULATORY:
{regulatory.get('analysis', 'N/A')}
Promoter Holding: {promoter}%
Risk Flags: {'; '.join(risk_flags) if risk_flags else 'None'}

5. MACRO:
{macro.get('analysis', 'N/A')}
Macro Stance: {macro_stance.upper()}
{past_context}

Now write a structured investment memo with these exact sections:

VERDICT: [BUY / HOLD / SELL / AVOID] — one word only

SUMMARY: 2-3 sentences. Overall conclusion on the stock.

BULL_CASE:
- Point 1
- Point 2
- Point 3

BEAR_CASE:
- Point 1
- Point 2
- Point 3

RISKS:
- Risk 1
- Risk 2

RECOMMENDATION: 2 sentences. Specific actionable advice. Include price context."""

        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            query_id=f"synth_{symbol}",
        )

        parsed = self._parse_memo(response["content"])

        return {
            "symbol": symbol,
            "query": query,
            "verdict": parsed.get("verdict", "HOLD"),
            "summary": parsed.get("summary", ""),
            "bull_case": parsed.get("bull_case", []),
            "bear_case": parsed.get("bear_case", []),
            "risks": parsed.get("risks", []),
            "recommendation": parsed.get("recommendation", ""),
            "agent_analyses": {
                "market": market.get("analysis", ""),
                "fundamentals": fundamentals.get("analysis", ""),
                "news": news.get("analysis", ""),
                "regulatory": regulatory.get("analysis", ""),
                "macro": macro.get("analysis", ""),
            },
            "data_snapshot": {
                "price": price,
                "period_return_pct": period_return,
                "nifty50_return_pct": nifty_return,
                "pe_ratio": pe,
                "roe_pct": roe,
                "promoter_holding_pct": promoter,
                "news_sentiment": sentiment,
                "news_themes": news.get("key_themes", []),
                "macro_stance": macro_stance,
                "risk_flags": risk_flags,
            },
        }

    def _parse_memo(self, content: str) -> dict:
        result = {}
        lines = content.strip().split("\n")
        current_section = None
        current_list = []

        for line in lines:
            line = line.strip()
            if line.startswith("VERDICT:"):
                result["verdict"] = line.replace("VERDICT:", "").strip().split()[0].upper()
            elif line.startswith("SUMMARY:"):
                result["summary"] = line.replace("SUMMARY:", "").strip()
                current_section = "summary_cont"
            elif line.startswith("BULL_CASE:"):
                current_section = "bull_case"
                current_list = []
            elif line.startswith("BEAR_CASE:"):
                result["bull_case"] = current_list
                current_section = "bear_case"
                current_list = []
            elif line.startswith("RISKS:"):
                result["bear_case"] = current_list
                current_section = "risks"
                current_list = []
            elif line.startswith("RECOMMENDATION:"):
                result["risks"] = current_list
                result["recommendation"] = line.replace("RECOMMENDATION:", "").strip()
                current_section = "recommendation_cont"
            elif line.startswith("- ") and current_section in ("bull_case", "bear_case", "risks"):
                current_list.append(line[2:].strip())
            elif current_section == "summary_cont" and line and not line.startswith("-"):
                result["summary"] = result.get("summary", "") + " " + line
            elif current_section == "recommendation_cont" and line:
                result["recommendation"] = result.get("recommendation", "") + " " + line

        if current_section == "risks":
            result["risks"] = current_list

        return result

    def _extract_symbol(self, query: str) -> str | None:
        query_lower = query.lower()

        for keyword, symbol in KNOWN_SYMBOLS.items():
            if keyword in query_lower:
                return symbol

        nse_suffixed = re.findall(r'([A-Z]{2,12})\.NS', query.upper())
        if nse_suffixed:
            return nse_suffixed[0]

        NOISE = {"NSE", "BSE", "IPO", "FII", "DII", "RBI", "SEBI", "GDP", "CPI", "MCX", "MF"}
        caps_tokens = re.findall(r'\b([A-Z]{2,12})\b', query)
        for m in caps_tokens:
            if m not in NOISE:
                return m

        return None
