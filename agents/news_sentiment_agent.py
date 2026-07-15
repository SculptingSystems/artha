"""News aggregation and sentiment scoring for a given stock."""
import structlog
from core.llm_client import LLMClient
from tools.news_tools import fetch_news_api

log = structlog.get_logger()


class NewsSentimentAgent:
    NAME = "news_sentiment_agent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, symbol: str, query: str, company_name: str = "") -> dict:
        log.info("agent_start", agent=self.NAME, symbol=symbol)

        articles = fetch_news_api(symbol, company_name, max_articles=15)
        if not articles:
            return {
                "agent": self.NAME,
                "symbol": symbol,
                "articles_found": 0,
                "sentiment": "neutral",
                "analysis": "No recent news found for this company.",
            }

        analysis, sentiment, themes = self._interpret(symbol, query, articles)

        return {
            "agent": self.NAME,
            "symbol": symbol,
            "articles_found": len(articles),
            "articles": articles[:5],
            "sentiment": sentiment,
            "key_themes": themes,
            "analysis": analysis,
        }

    def _interpret(self, symbol: str, query: str, articles: list[dict]) -> tuple[str, str, list]:
        article_text = "\n".join(
            f"- [{a['source']}] {a['title']}: {a['summary']}"
            for a in articles
        )

        prompt = f"""You are a financial news analyst specializing in Indian markets.

Stock: {symbol}
User Query: {query}

Recent News ({len(articles)} articles):
{article_text}

Analyze this news coverage and provide:
1. Overall sentiment: exactly one of [POSITIVE, NEGATIVE, NEUTRAL, MIXED]
2. Key themes (comma-separated, max 4): e.g., "Q4 earnings beat, management change, RBI approval"
3. Analysis: 3-4 sentences summarizing what the news means for the stock.
   Mention specific headlines where relevant. Flag any material risks or catalysts.

Format your response as:
SENTIMENT: <one word>
THEMES: <comma-separated themes>
ANALYSIS: <your analysis>"""

        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            query_id=f"nsa_{symbol}",
        )

        content = response["content"]
        sentiment = "NEUTRAL"
        themes = []
        analysis = content

        for line in content.split("\n"):
            if line.startswith("SENTIMENT:"):
                sentiment = line.replace("SENTIMENT:", "").strip().upper()
            elif line.startswith("THEMES:"):
                themes = [t.strip() for t in line.replace("THEMES:", "").split(",")]
            elif line.startswith("ANALYSIS:"):
                analysis = line.replace("ANALYSIS:", "").strip()

        return analysis, sentiment, themes
