# RiskPulse — Architecture Deep Dive

## Overview

RiskPulse is a streaming data platform for real-time portfolio risk intelligence.
It processes market tick data through a Kafka → Faust → dbt → RAG pipeline,
producing VWAP windows, volatility regimes, and drawdown alerts — all queryable
in plain English via a LangChain RAG layer.

---

## Component Details

### 1. Data Producers

**Portfolio Simulator** (`producers/portfolio_simulator.py`)
- Generates synthetic price ticks using Geometric Brownian Motion (GBM)
- Parameters: drift=8% annual, per-symbol volatility (NVDA=0.028, SPY=0.008)
- Emits to `market-ticks` and `portfolio-events` Kafka topics
- Rate: ~10–15 ticks/second across 8 symbols

**Alpaca Producer** (`producers/alpaca_producer.py`)
- Connects to Alpaca WebSocket for live equity tick data
- Subscribes to AAPL, MSFT, NVDA, GOOGL, META, TSLA, SPY, QQQ
- Requires free Alpaca paper trading account
- Active during US market hours (9:30am–4pm ET)

---

### 2. Kafka Topics

| Topic | Producer | Consumer | Partitions |
|---|---|---|---|
| `market-ticks` | Simulator / Alpaca | Faust VWAP job | 3 |
| `portfolio-events` | Simulator | Future: alerting service | 3 |
| `risk-alerts` | Faust VWAP job | Future: notification service | 3 |

Message format: JSON with fields `symbol`, `price`, `size`, `timestamp`, `source`, `exchange`.

---

### 3. Faust Stream Processor (`stream_jobs/vwap_job.py`)

**Window type:** 5-minute tumbling (non-overlapping)

**Metrics computed per window per symbol:**

```
VWAP         = Σ(price × size) / Σ(size)
Volatility   = population standard deviation of prices
Session High = running max(max_price) across all windows
Drawdown %   = (session_high - vwap) / session_high × 100
```

**Alert logic:**
- `drawdown_pct > 3%` → emits `DRAWDOWN` alert to `risk-alerts` topic
- Results written to `./data/risk_metrics/date=YYYY-MM-DD/data.parquet`

---

### 4. dbt Models

```
Parquet Files (raw)
      │
      ▼
stg_risk_metrics          SQL view — dedup via ROW_NUMBER() OVER (PARTITION BY symbol, window_start)
      │
      ▼
fct_vwap_windows          SQL view — adds session_high (running window max), drawdown_pct, volatility_rank
      │              ╲
      ▼               ▼
mart_portfolio_summary    mart_volatility_alerts
  Per-symbol rollup         Active alerts only
  + volatility regime       DRAWDOWN / HIGHEST_VOL / WATCH
  (HIGH/MEDIUM/LOW)
```

**Schema tests:** 10 total — `not_null` and `unique` across all 4 models.

---

### 5. RAG Layer

**Ingestion flow:**
1. Load `mart_portfolio_summary`, `mart_volatility_alerts`, `fct_vwap_windows` from DuckDB
2. Format each row as a structured text document (symbol, metrics, regime)
3. Embed documents using ChromaDB's default embedding model (all-MiniLM-L6-v2)
4. Store in local ChromaDB persistent collection `riskpulse_portfolio`

**Query flow:**
1. Embed user question using same model
2. Retrieve top-5 most semantically similar documents from ChromaDB
3. Inject retrieved context into system prompt
4. Call Azure GPT-4o-mini with context + question
5. Return structured plain English answer

**FastAPI endpoints:**
- `POST /query` — RAG query
- `POST /ingest` — refresh ChromaDB
- `GET  /portfolio` — raw mart data (no LLM)
- `GET  /health` — health check

---

### 6. Storage

| Layer | Technology | Format | Location |
|---|---|---|---|
| Raw streaming output | Parquet | Columnar | `./data/risk_metrics/` |
| Analytics warehouse | DuckDB | In-process | `./data/riskpulse.duckdb` |
| Vector store | ChromaDB | HNSW index | `./data/chromadb/` |

---

## Design Decisions

**Why Faust over Kafka Streams?**
Faust is Python-native (no JVM), built by Robinhood for financial data, and
integrates cleanly with the existing Python stack. Kafka Streams would require
a separate Java service.

**Why DuckDB over Snowflake?**
DuckDB is free, file-based, and has near-identical SQL to Snowflake.
The dbt-duckdb adapter means all models are instantly portable to Snowflake —
just swap the `profiles.yml` target.

**Why local ChromaDB over a hosted vector DB?**
Cost ($0 vs $50+/month) and simplicity. For production, Pinecone or Weaviate
would be a direct drop-in swap via LangChain's vectorstore abstraction.

**Why Azure OpenAI over direct OpenAI?**
Enterprise credential management, regional data residency, and rate limit
controls — the same reasons production fintech deployments prefer Azure OpenAI.
