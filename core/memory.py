"""ChromaDB store for past analyses. Recalled on follow-up queries for the same symbol."""
import json
import uuid
from datetime import datetime
from pathlib import Path

import chromadb
import structlog

log = structlog.get_logger()

CHROMA_PATH = Path("chroma_db")


class AnalysisMemory:
    def __init__(self):
        self._client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self._collection = self._client.get_or_create_collection(
            name="artha_analyses",
            metadata={"hnsw:space": "cosine"},
        )

    def save(self, symbol: str, query: str, memo: dict) -> str:
        doc_id = str(uuid.uuid4())
        document = f"Symbol: {symbol}\nQuery: {query}\nAnalysis: {json.dumps(memo)}"
        self._collection.add(
            documents=[document],
            metadatas=[{
                "symbol": symbol,
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "verdict": memo.get("verdict", ""),
            }],
            ids=[doc_id],
        )
        log.info("memory_saved", symbol=symbol, doc_id=doc_id)
        return doc_id

    def recall(self, query: str, symbol: str | None = None, n_results: int = 3) -> list[dict]:
        where = {"symbol": symbol} if symbol else None
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )
        except Exception:
            return []

        memories = []
        for i, doc in enumerate(results["documents"][0]):
            memories.append({
                "document": doc,
                "metadata": results["metadatas"][0][i],
            })
        return memories

    def get_history(self, symbol: str) -> list[dict]:
        try:
            results = self._collection.get(where={"symbol": symbol})
            return [
                {"document": d, "metadata": m}
                for d, m in zip(results["documents"], results["metadatas"])
            ]
        except Exception:
            return []
