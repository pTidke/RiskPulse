# RiskPulse 📈

> **Real-time portfolio risk intelligence** — streaming market data through Kafka and Faust, transformed by dbt, and queryable in plain English via a LangChain RAG layer backed by Azure OpenAI.

[![Python](https://img.shields.io/badge/Python-3.9-blue?logo=python)](https://python.org)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-3.6-black?logo=apachekafka)](https://kafka.apache.org)
[![Faust](https://img.shields.io/badge/Faust_Streaming-0.11-orange)](https://faust-streaming.github.io/faust)
[![dbt](https://img.shields.io/badge/dbt-1.8-red?logo=dbt)](https://getdbt.com)
[![DuckDB](https://img.shields.io/badge/DuckDB-0.10-yellow)](https://duckdb.org)
[![LangChain](https://img.shields.io/badge/LangChain-RAG-green)](https://langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

---

## What Is This?

RiskPulse is designed to mirror enterprise-grade, real-time risk infrastructure used by large-scale asset management firms—rebuilt with a modern open-source stack and an AI layer on top.

In traditional financial data infrastructures, legacy ETL pipelines are heavily batch-based, forcing portfolio managers to wait hours for critical risk reports. RiskPulse answers the question: *what would that system look like if it ran in real time, cost virtually nothing to operate, and let you ask questions in plain English?*

**Key capabilities:**

- Live price ticks stream through **Apache Kafka** into a **Faust** stream processor
- **5-minute VWAP windows** compute volatility regimes, drawdown alerts, and risk rankings per symbol
- **dbt** builds analytics marts (materialized as tables) with **enforced model contracts** — typed columns plus primary-key / not-null constraints — 10 schema tests, and full lineage docs
- Marts are mirrored to an **Apache Iceberg** table on MinIO (SQLite catalog) and read back through DuckDB, with a reproducible **Parquet-vs-Iceberg latency benchmark** (`make bench`)
- A **LangChain RAG layer** (ChromaDB + Azure GPT-4o-mini) answers natural language questions against live mart data
- Entire stack runs **100% locally for free** — no cloud account required

---

https://github.com/user-attachments/assets/24e8fbce-6639-435c-98a8-aec7495dce21

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
│     Alpaca WebSocket            Portfolio Simulator          │
│     (live equity ticks)        (GBM synthetic data)         │
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
| Storage           | Parquet + Apache Iceberg | Stream lake (Parquet) + Iceberg table on MinIO |
| Warehouse         | DuckDB                   | Zero-config analytical queries          |
| Transformation    | dbt-core + dbt-duckdb    | 4 models, enforced contracts, 10 tests, lineage |
| Vector Store      | ChromaDB                 | Semantic search over mart snapshots     |
| LLM               | Azure OpenAI GPT-4o-mini | Natural language portfolio queries      |
| Orchestration     | LangChain                | RAG pipeline + prompt engineering       |
| API               | FastAPI                  | REST endpoints for RAG + portfolio data |
| Dashboard         | Vite                     | Live risk visualizations (frontend)     |
| DevOps            | Docker Compose           | Full local stack in one command         |
| CI/CD             | GitHub Actions           | dbt test gate on every PR               |
| Benchmark         | DuckDB micro-bench       | Parquet vs Iceberg latency (p50/p95/p99) |
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

**10 schema tests** (`not_null`, `unique`) plus **enforced dbt contracts** on the marts — typed columns with primary-key / not-null constraints, materialized as tables. Query-latency numbers in [docs/benchmarks.md](docs/benchmarks.md).

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

### Prerequisites
- Docker and Docker Compose
- Python 3.9 (required)
- Node.js 18+ (for the dashboard, step 10)
- An Azure OpenAI deployment, needed only for the RAG layer (steps 8 and 9)

### 1. Clone and configure
```bash
git clone https://github.com/pTidke/RiskPulse.git
cd RiskPulse
cp .env.example .env
```
Streaming, dbt, and the dashboard need **no API keys**. The RAG layer does. Before step 8, set your Azure OpenAI values in `.env`: endpoint, API key, deployment name, and API version.

### 2. Start the infrastructure
```bash
make up
```
Kafka, MinIO, ChromaDB, and Grafana start, and the three topics (`market-ticks`, `portfolio-events`, `risk-alerts`) are created automatically. Confirm if you want:
```bash
docker exec riskpulse-kafka kafka-topics --bootstrap-server localhost:9092 --list
```

### 3. Python environment
```bash
python3.9 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
> Run `source .venv/bin/activate` in every new terminal below before using `dbt` or `python`.

### 4. Start the data flow (Terminal 1)
```bash
make simulate
```

### 5. Start the Faust stream processor (Terminal 2)
```bash
python stream_jobs/vwap_job.py worker -l info --without-web
```
Leave it running. **Wait about 5 minutes** so the first 5-minute window closes before you run dbt, otherwise the marts read empty. A few `GroupCoordinatorNotAvailable` lines at startup are normal and clear on their own.

### 6. Build the dbt models (Terminal 3)
```bash
cd riskpulse_dbt
dbt run && dbt test
```
The DuckDB profile ships in `riskpulse_dbt/profiles.yml` (local only, no secrets). If dbt reports a missing or empty profile, create `~/.dbt/profiles.yml`:
```yaml
# the top key must match the `profile:` line in dbt_project.yml
riskpulse_dbt:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: '../data/riskpulse.duckdb'
      threads: 4
```

### 7. (Optional) View the dbt lineage docs (Terminal 3)
```bash
dbt docs generate && dbt docs serve --port 8090
```
Port 8090 is used because Kafka UI already holds 8080. Open http://localhost:8090, and stop it with Ctrl+C.

### 7b. (Optional) Benchmark the query layer + build the Iceberg lakehouse
```bash
make bench        # DuckDB latency: serving marts + Parquet scans
make iceberg      # mirror the Parquet lake into an Iceberg table on MinIO
python scripts/benchmark_duckdb.py --sources parquet,iceberg   # Parquet vs Iceberg
```
Needs the stack up (`make up`) and dbt built (step 6). Methodology and results in
[docs/benchmarks.md](docs/benchmarks.md).

### 8. Ingest the marts into the RAG layer
```bash
cd .. && python rag/rag_engine.py ingest
```
Requires the Azure OpenAI values from step 1.

### 9. Ask questions
```bash
python rag/rag_engine.py query "which stocks are the riskiest right now?"
```

### 10. (Optional) Start the dashboard (Terminal 4)
```bash
# If the dashboard reads live data from the FastAPI backend, start it first
# in its own terminal. ChromaDB holds port 8000, so run the API elsewhere:
#   uvicorn rag.api:app --port 8888
cd frontend && npm install && npm run dev
```
Use a plain `npm install`, **not** `--force`, to avoid a Rollup native-dependency bug. Dashboard at http://localhost:5173.

**Open in browser:**
| Service   | URL                    | Credentials             |
| --------- | ---------------------- | ----------------------- |
| Dashboard | http://localhost:5173  | —                       |
| Kafka UI  | http://localhost:8080  | —                       |
| MinIO     | http://localhost:9001  | minioadmin / minioadmin |
| Grafana   | http://localhost:3000  | admin / riskpulse       |
| dbt docs  | http://localhost:8090  | — (when running)        |

---

## Project Structure

```
riskpulse/
├── producers/
│   ├── alpaca_producer.py      # Live Alpaca WebSocket → Kafka
│   └── portfolio_simulator.py  # GBM synthetic data → Kafka
├── stream_jobs/
│   └── vwap_job.py             # Faust VWAP + risk metrics job
├── storage/
│   ├── duckdb_query.py         # DuckDB queries against Parquet
│   └── iceberg_lake.py         # Iceberg mirror: PyIceberg + SQLite catalog → MinIO
├── riskpulse_dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml            # Local DuckDB profile
│   └── models/
│       ├── staging/
│       │   └── stg_risk_metrics.sql
│       └── marts/
│           ├── fct_vwap_windows.sql
│           ├── mart_portfolio_summary.sql
│           └── mart_volatility_alerts.sql
├── rag/
│   ├── rag_engine.py           # LangChain + ChromaDB + Azure OpenAI (CLI)
│   └── api.py                  # FastAPI REST endpoints
├── frontend/                   # Vite dashboard (risk visualizations)
├── scripts/
│   └── benchmark_duckdb.py     # DuckDB latency benchmark (Parquet vs Iceberg)
├── docs/
│   └── benchmarks.md           # benchmark methodology + results
├── tests/                      # Pipeline tests
├── .github/workflows/          # CI: dbt test gate on every PR
├── docker-compose.yml          # Full local stack
├── Makefile                    # One-command operations
└── .env.example                # Config template
```

---

## Troubleshooting

- **`make up` fails, kafka exits (1)** — usually a stale container or port 9092 in use. Run `docker compose down --remove-orphans`, check `lsof -i :9092`, then `make up`. Read the real cause with `docker logs riskpulse-kafka --tail 40`.
- **Producer: `Unknown topic`** — topics were not created yet. Check `docker logs riskpulse-kafka-init`, or create them by hand with `kafka-topics --create`.
- **dbt: profile not found or empty** — the profile must exist and have content. See step 6.
- **dbt docs: `Address already in use`** — Kafka UI holds 8080. Use `dbt docs serve --port 8090`.
- **RAG: `unexpected keyword argument 'proxies'`** — a version clash between `openai` and `langchain-openai`. Fix with `pip install -U langchain-openai langchain-core`, or pin `openai<1.55`.
- **Dashboard: `Cannot find module @rollup/rollup-darwin-arm64`** — npm optional-dependency bug. From `frontend/`, run `rm -rf node_modules package-lock.json && npm install` (no `--force`).

---

## Cost

| Component                                    | Cost                             |
| -------------------------------------------- | -------------------------------- |
| Kafka, Faust, DuckDB, dbt, ChromaDB, Grafana | **$0 forever** (open source)     |
| Alpaca API (live market data)                | **$0** (free paper trading tier) |
| Azure GPT-4o-mini (RAG queries)              | **~$0.002 per query**            |
| Full project operating cost                  | **~$0–2/month**                  |
