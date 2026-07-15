"""RSS and NewsAPI fetching for Indian equity news."""
import re
import feedparser
import httpx
import structlog

from core.config import get_settings

log = structlog.get_logger()

RSS_FEEDS = {
    "economic_times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "moneycontrol":   "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "business_standard": "https://www.business-standard.com/rss/markets-106.rss",
}


def fetch_news_rss(symbol: str, company_name: str = "", max_articles: int = 15) -> list[dict]:
    keywords = {symbol.upper().replace(".NS", "").replace(".BO", "")}
    if company_name:
        keywords.update(company_name.lower().split())

    articles = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                text = f"{title} {summary}".lower()

                if any(kw.lower() in text for kw in keywords):
                    articles.append({
                        "source": source,
                        "title": title,
                        "summary": _clean(summary),
                        "published": entry.get("published", ""),
                        "link": entry.get("link", ""),
                    })
        except Exception as e:
            log.warning("rss_fetch_error", source=source, error=str(e))

    return articles[:max_articles]


def fetch_news_api(symbol: str, company_name: str = "", max_articles: int = 15) -> list[dict]:
    settings = get_settings()
    if not settings.news_api_key or settings.news_api_key.startswith("dummy"):
        log.info("newsapi_key_missing_using_rss")
        return fetch_news_rss(symbol, company_name, max_articles)

    query = company_name or symbol.replace(".NS", "").replace(".BO", "")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f"{query} India stock",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "apiKey": settings.news_api_key,
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "source": a["source"]["name"],
                    "title": a["title"],
                    "summary": _clean(a.get("description", "")),
                    "published": a["publishedAt"],
                    "link": a["url"],
                }
                for a in data.get("articles", [])
            ]
    except Exception as e:
        log.warning("newsapi_error", error=str(e))
        return fetch_news_rss(symbol, company_name, max_articles)


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return " ".join(text.split())[:400]
