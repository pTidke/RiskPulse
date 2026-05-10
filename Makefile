.PHONY: up down logs producers flink simulate query clean jars help

# ── Infrastructure ────────────────────────────────────────────────────────────
up:
	docker compose up -d
	@echo ""
	@echo "✅  RiskPulse stack is running"
	@echo ""
	@echo "   Kafka UI   → http://localhost:8080"
	@echo "   MinIO      → http://localhost:9001  (minioadmin / minioadmin)"
	@echo "   Grafana    → http://localhost:3000  (admin / riskpulse)"
	@echo "   ChromaDB   → http://localhost:8000"
	@echo "   Schema Reg → http://localhost:8081"
	@echo ""
	@echo "   Next: make jars && make simulate && make flink"

down:
	docker compose down

logs:
	docker compose logs -f kafka

# ── JAR setup (one-time) ──────────────────────────────────────────────────────
jars:
	bash scripts/download_jars.sh

# ── Data Producers ────────────────────────────────────────────────────────────
simulate:
	@echo "Starting portfolio simulator (Ctrl+C to stop)..."
	python producers/portfolio_simulator.py

alpaca:
	@echo "Starting Alpaca live producer (requires API keys in .env)..."
	python producers/alpaca_producer.py

# ── Flink Job ─────────────────────────────────────────────────────────────────
flink:
	@echo "Submitting VWAP job to Flink..."
	python flink_jobs/vwap_job.py

# ── DuckDB Query ──────────────────────────────────────────────────────────────
query:
	python storage/duckdb_query.py

# ── dbt ───────────────────────────────────────────────────────────────────────
dbt-run:
	cd dbt && dbt run

dbt-test:
	cd dbt && dbt test

dbt-docs:
	cd dbt && dbt docs generate && dbt docs serve

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	docker compose down -v
	rm -rf data/ __pycache__ **/__pycache__

help:
	@echo ""
	@echo "  make up        — start all Docker services"
	@echo "  make jars      — download Flink connector JARs (one-time)"
	@echo "  make simulate  — run portfolio event simulator → Kafka"
	@echo "  make alpaca    — run live Alpaca tick producer → Kafka"
	@echo "  make flink     — start Flink VWAP streaming job"
	@echo "  make query     — query risk metrics via DuckDB"
	@echo "  make dbt-run   — run dbt models"
	@echo "  make dbt-test  — run dbt schema tests"
	@echo "  make down      — stop all services"
	@echo "  make clean     — stop + wipe all volumes"
	@echo ""
