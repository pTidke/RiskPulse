.PHONY: up down logs producers stream simulate query clean help

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
	@echo "   Next: make simulate && make stream"

down:
	docker compose down

logs:
	docker compose logs -f kafka

# ── Data Producers ────────────────────────────────────────────────────────────
simulate:
	@echo "Starting portfolio simulator (Ctrl+C to stop)..."
	python producers/portfolio_simulator.py

alpaca:
	@echo "Starting Alpaca live producer (requires API keys in .env)..."
	python producers/alpaca_producer.py

# ── Stream Job ─────────────────────────────────────────────────────────────────
stream:
	@echo "Starting Faust VWAP stream processor..."
	python stream_jobs/vwap_job.py worker -l info --without-web

# ── DuckDB Query ──────────────────────────────────────────────────────────────
query:
	python storage/duckdb_query.py

# ── dbt ───────────────────────────────────────────────────────────────────────
dbt-run:
	cd riskpulse_dbt && dbt run

dbt-test:
	cd riskpulse_dbt && dbt test

dbt-docs:
	cd riskpulse_dbt && dbt docs generate && dbt docs serve

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	docker compose down -v
	rm -rf data/ __pycache__ **/__pycache__

help:
	@echo ""
	@echo "  make up        — start all Docker services"
	@echo "  make simulate  — run portfolio event simulator → Kafka"
	@echo "  make alpaca    — run live Alpaca tick producer → Kafka"
	@echo "  make stream    — start Faust VWAP streaming job"
	@echo "  make query     — query risk metrics via DuckDB"
	@echo "  make dbt-run   — run dbt models"
	@echo "  make dbt-test  — run dbt schema tests"
	@echo "  make down      — stop all services"
	@echo "  make clean     — stop + wipe all volumes"
	@echo ""
