from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import structlog
import time

from agents.orchestrator import Orchestrator
from core.cost_tracker import cost_tracker
from core.memory import AnalysisMemory

log = structlog.get_logger()

app = FastAPI(
    title="Artha",
    description="Indian equity research API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUEST_COUNT = Counter("artha_requests_total", "Total analysis requests", ["status"])
REQUEST_LATENCY = Histogram("artha_request_duration_seconds", "Request latency")

orchestrator = Orchestrator()
memory = AnalysisMemory()


class AnalysisRequest(BaseModel):
    query: str


class HistoryRequest(BaseModel):
    symbol: str


@app.post("/api/v1/analyze")
async def analyze(request: AnalysisRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    start = time.time()
    try:
        result = orchestrator.analyze(request.query)
        REQUEST_COUNT.labels(status="success").inc()
        REQUEST_LATENCY.observe(time.time() - start)
        return result
    except Exception as e:
        REQUEST_COUNT.labels(status="error").inc()
        log.error("analyze_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recall")
async def recall(request: HistoryRequest):
    history = memory.get_history(request.symbol.upper())
    return {"symbol": request.symbol.upper(), "past_analyses": history}


@app.get("/api/v1/cost")
async def cost_summary():
    return cost_tracker.session_summary()


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "artha"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
