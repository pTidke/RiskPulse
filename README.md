# RiskPulse 📈

> **Real-time portfolio risk intelligence** — streaming market data through Kafka and Faust, transformed by dbt, and queryable in plain English via a LangChain RAG layer backed by Azure OpenAI.

[![Python](https://img.shields.io/badge/Python-3.9-blue?logo=python)](https://python.org)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-2.8-black?logo=apachekafka)](https://kafka.apache.org)
[![Faust](https://img.shields.io/badge/Faust_Streaming-0.11-orange)](https://faust-streaming.github.io/faust)
[![dbt](https://img.shields.io/badge/dbt-1.8-red?logo=dbt)](https://getdbt.com)
[![DuckDB](https://img.shields.io/badge/DuckDB-0.10-yellow)](https://duckdb.org)
[![LangChain](https://img.shields.io/badge/LangChain-RAG-green)](https://langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

---

## What Is This?

RiskPulse is a **senior data engineering portfolio project** that mirrors the kind of real-time risk infrastructure I architected at TresVista for a $550B AUM client — but rebuilt with a modern open-source stack and an AI layer on top.

At TresVista, our ETL pipelines were batch-based: portfolio managers waited hours for risk reports. RiskPulse answers the question: _what would that system look like if it ran in real time, cost nothing to operate, and let you ask questions in plain English?_

**Key capabilities:**

- Live price ticks stream through **Apache Kafka** into a **Faust** stream processor
- **5-minute VWAP windows** compute volatility regimes, drawdown alerts, and risk rankings per symbol
- **dbt** builds clean analytics marts with 10 schema tests and full lineage documentation
- A **LangChain RAG layer** (ChromaDB + Azure GPT-4o-mini) answers natural language questions against live mart data
- Entire stack runs **100% locally for free** — no cloud account required

---

## Demo

```
$ python rag/rag_engine.py query "which stocks are the riskiest right now?"

🤖 RiskPulse: The riskiest stocks right now are:
  1. NVDA — Volatility: 0.086, Regime: HIGH, Alert: HIGHEST_VOL
  2. META — Volatility: 0.035, Regime: MEDIUM, Alert: WATCH
  3. TSLA — Volatility: 0.033, Regime: MEDIUM, Alert: WATCH
NVDA is flagged highest — its 5-min VWAP of $820.05 shows the widest
price range in the session at $0.37, significantly above SPY and QQQ.
```

```
$ python rag/rag_engine.py query "should I be worried about drawdown risks?"

🤖 RiskPulse: Current drawdowns are minimal across the portfolio.
NVDA and META are on WATCH given elevated volatility ranks (#1 and #2).
No position has breached the 3% drawdown threshold from session high.
Recommend monitoring NVDA given its HIGH volatility regime designation.
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                           │
│  Alpaca WebSocket    Coinbase API    Portfolio Simulator     │
│  (live equity ticks) (crypto feed)  (GBM synthetic data)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      APACHE KAFKA                           │
│   market-ticks   │  portfolio-events  │   risk-alerts       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              FAUST STREAM PROCESSOR                         │
│   5-min VWAP  │  Drawdown Detection  │  Volatility Regime   │
└──────────┬────────────────────────────────────┬────────────┘
           │                                    │
           ▼                                    ▼
┌──────────────────────┐            ┌───────────────────────┐
│  Parquet / Delta     │            │  risk-alerts (Kafka)  │
│  Lake (local / S3)   │            │  downstream consumers │
└──────────┬───────────┘            └───────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                        dbt + DuckDB                         │
│  stg_risk_metrics → fct_vwap_windows → mart_portfolio       │
│                                      → mart_alerts          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              LangChain RAG Layer                            │
│   ChromaDB (vector store)  +  Azure GPT-4o-mini             │
│   FastAPI endpoint  →  natural language portfolio Q&A       │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer             | Technology               | Purpose                                 |
| ----------------- | ------------------------ | --------------------------------------- |
| Messaging         | Apache Kafka             | 3 topics, event-driven architecture     |
| Stream Processing | Faust Streaming          | Stateful 5-min windowed aggregations    |
| Storage           | Parquet + Delta Lake     | Date-partitioned lakehouse format       |
| Warehouse         | DuckDB                   | Zero-config analytical queries          |
| Transformation    | dbt-core + dbt-duckdb    | 4 models, 10 schema tests, lineage docs |
| Vector Store      | ChromaDB                 | Semantic search over mart snapshots     |
| LLM               | Azure OpenAI GPT-4o-mini | Natural language portfolio queries      |
| Orchestration     | LangChain                | RAG pipeline + prompt engineering       |
| API               | FastAPI                  | REST endpoints for RAG + portfolio data |
| DevOps            | Docker Compose           | Full local stack in one command         |
| CI/CD             | GitHub Actions           | dbt test gate on every PR               |
| Data Source       | Alpaca Markets API       | Free real-time equity tick data         |

---

## dbt Lineage

```
stg_risk_metrics              ← raw Parquet → deduplicated + typed
        │
        ▼
fct_vwap_windows              ← session high, drawdown %, volatility rank
        │                ╲
        ▼                 ▼
mart_portfolio_summary    mart_volatility_alerts
(per-symbol rollup +      (active DRAWDOWN /
 volatility regime)        HIGHEST_VOL / WATCH flags)
```

**10 schema tests** covering: `not_null`, `unique`, and referential integrity across all 4 models.

---

## Faust Risk Metrics

Per 5-minute tumbling window, per symbol:

| Metric                    | Description                                               |
| ------------------------- | --------------------------------------------------------- |
| `vwap`                    | Volume-weighted average price — Σ(price × size) / Σ(size) |
| `volatility`              | Population standard deviation of prices in window         |
| `min_price` / `max_price` | Intra-window range                                        |
| `session_high`            | Running max across all windows                            |
| `drawdown_pct`            | (session_high − vwap) / session_high × 100                |
| `volatility_regime`       | HIGH / MEDIUM / LOW classification                        |

Drawdown alert fires when `drawdown_pct > 3%` → emits to `risk-alerts` Kafka topic.

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/pTidke/riskpulse.git
cd riskpulse
cp .env.example .env          # no API keys needed for simulator mode

# 2. Start all Docker services
make up

# 3. Install Python dependencies (Python 3.9 required)
python3.9 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Start simulated data flow (Terminal 1)
make simulate

# 5. Start Faust stream processor (Terminal 2)
python flink_jobs/vwap_job.py worker -l info --without-web

# 6. Run dbt models (after ~5 min for first window)
cd riskpulse_dbt && dbt run && dbt test

# 7. Ingest into RAG layer
cd .. && python rag/rag_engine.py ingest

# 8. Ask questions
python rag/rag_engine.py query "which stocks are the riskiest right now?"
```

**Open in browser:**
| Service | URL | Credentials |
|---|---|---|
| Kafka UI | http://localhost:8080 | — |
| MinIO | http://localhost:9001 | minioadmin / minioadmin |
| Grafana | http://localhost:3000 | admin / riskpulse |

---

## Project Structure

```
riskpulse/
├── producers/
│   ├── alpaca_producer.py       # Live Alpaca WebSocket → Kafka
│   └── portfolio_simulator.py  # GBM synthetic data → Kafka
├── flink_jobs/
│   └── vwap_job.py             # Faust VWAP + risk metrics job
├── storage/
│   └── duckdb_query.py         # DuckDB queries against Parquet
├── riskpulse_dbt/
│   └── models/
│       ├── staging/
│       │   └── stg_risk_metrics.sql
│       └── marts/
│           ├── fct_vwap_windows.sql
│           ├── mart_portfolio_summary.sql
│           └── mart_volatility_alerts.sql
├── rag/
│   ├── rag_engine.py           # LangChain + ChromaDB + Azure OpenAI
│   └── api.py                  # FastAPI REST endpoints
├── docker-compose.yml          # Full local stack
├── Makefile                    # One-command operations
└── .env.example                # Config template
```

---

## Cost

| Component                                    | Cost                             |
| -------------------------------------------- | -------------------------------- |
| Kafka, Faust, DuckDB, dbt, ChromaDB, Grafana | **$0 forever** (open source)     |
| Alpaca API (live market data)                | **$0** (free paper trading tier) |
| Azure GPT-4o-mini (RAG queries)              | **~$0.002 per query**            |
| Full project operating cost                  | **~$0–2/month**                  |

---

## Background

Built by **Prajwal Tidke** — Senior Data Engineer with 5+ years building production ETL systems at LTIMindtree and TresVista (CPPIB, $550B AUM). Currently completing MS Big Data Analytics at SDSU (4.0 GPA) and researching LLM applications at LINC Lab.

This project bridges my batch ETL background with modern streaming + AI — the stack I would have built at TresVista if we'd had a real-time layer.

- 🔗 [LinkedIn](https://linkedin.com/in/ptidke9)
- 🌐 [Portfolio](https://prajwaltidke.me)
- 💻 [GitHub](https://github.com/pTidke)
