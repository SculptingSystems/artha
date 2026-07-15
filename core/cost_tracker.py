from dataclasses import dataclass, field
from datetime import datetime, timezone
import structlog

log = structlog.get_logger()

PRICING = {
    "claude-sonnet-4-6":   {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5":    {"input": 0.25, "output": 1.25},
    "gpt-4o":              {"input": 2.5,  "output": 10.0},
    "gpt-4o-mini":         {"input": 0.15, "output": 0.60},
}


@dataclass
class QueryCost:
    query_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> str:
        return (
            f"[{self.model}] in={self.input_tokens} out={self.output_tokens} "
            f"cost=${self.cost_usd:.4f}"
        )


class CostTracker:
    def __init__(self):
        self._queries: list[QueryCost] = []

    def record(self, query_id: str, model: str, input_tokens: int, output_tokens: int) -> QueryCost:
        rates = PRICING.get(model, {"input": 3.0, "output": 15.0})
        cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

        entry = QueryCost(
            query_id=query_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )
        self._queries.append(entry)
        log.info("cost_tracked", **entry.__dict__ | {"timestamp": str(entry.timestamp)})
        return entry

    def session_total(self) -> float:
        return sum(q.cost_usd for q in self._queries)

    def session_summary(self) -> dict:
        return {
            "total_queries": len(self._queries),
            "total_input_tokens": sum(q.input_tokens for q in self._queries),
            "total_output_tokens": sum(q.output_tokens for q in self._queries),
            "total_cost_usd": round(self.session_total(), 4),
        }


cost_tracker = CostTracker()
