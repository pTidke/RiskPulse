"""
rag/api.py

RiskPulse FastAPI — exposes the RAG layer as a REST API.

Endpoints:
  POST /query     — ask a question about the portfolio
  POST /ingest    — refresh ChromaDB with latest dbt mart data
  GET  /health    — health check
  GET  /portfolio — current portfolio summary (no LLM needed)

Run: uvicorn rag.api:app --reload --port 8888
  or: make api
"""

import os
import duckdb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from rag.rag_engine import ingest, query

load_dotenv()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/riskpulse.duckdb")

app = FastAPI(
    title="RiskPulse API",
    description="Real-time portfolio risk intelligence powered by Kafka + Faust + dbt + RAG",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    answer: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "RiskPulse RAG API",
        "duckdb": DUCKDB_PATH,
    }


@app.post("/ingest")
def ingest_data():
    """Refresh ChromaDB with latest dbt mart data."""
    try:
        ingest()
        return {"status": "ok", "message": "ChromaDB ingestion complete"}
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
def query_portfolio(req: QueryRequest):
    """Ask a natural language question about the portfolio."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        answer = query(req.question)
        return QueryResponse(question=req.question, answer=answer)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/portfolio")
def portfolio_summary():
    """Return current portfolio summary directly from DuckDB — no LLM needed."""
    try:
        con = duckdb.connect(DUCKDB_PATH)
        summary = con.execute("SELECT * FROM mart_portfolio_summary").df()
        alerts  = con.execute("SELECT * FROM mart_volatility_alerts").df()
        return {
            "portfolio": summary.to_dict(orient="records"),
            "alerts":    alerts.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
