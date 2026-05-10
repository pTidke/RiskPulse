#!/bin/bash
# =============================================================================
#  RiskPulse — Full Setup Script
#  Installs all dependencies, starts Docker, creates topics, runs first test
#
#  Usage: bash scripts/setup.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${AMBER}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "  ██████╗ ██╗███████╗██╗  ██╗██████╗ ██╗   ██╗██╗     ███████╗███████╗"
echo "  ██╔══██╗██║██╔════╝██║ ██╔╝██╔══██╗██║   ██║██║     ██╔════╝██╔════╝"
echo "  ██████╔╝██║███████╗█████╔╝ ██████╔╝██║   ██║██║     ███████╗█████╗  "
echo "  ██╔══██╗██║╚════██║██╔═██╗ ██╔═══╝ ██║   ██║██║     ╚════██║██╔══╝  "
echo "  ██║  ██║██║███████║██║  ██╗██║     ╚██████╔╝███████╗███████║███████╗"
echo "  ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝      ╚═════╝ ╚══════╝╚══════╝╚══════╝"
echo ""
echo "  Real-Time Portfolio Risk Intelligence"
echo "  github.com/pTidke/riskpulse"
echo ""

# ── Check prerequisites ────────────────────────────────────────────────────
info "Checking prerequisites..."

command -v python3.9 >/dev/null 2>&1 || error "Python 3.9 not found. Install from python.org"
command -v docker    >/dev/null 2>&1 || error "Docker not found. Install Docker Desktop from docker.com"
command -v make      >/dev/null 2>&1 || error "make not found. Install via Xcode tools: xcode-select --install"

PYTHON_VERSION=$(python3.9 --version | cut -d' ' -f2)
DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
success "Python $PYTHON_VERSION"
success "Docker $DOCKER_VERSION"

# ── Check Docker is running ───────────────────────────────────────────────
if ! docker info >/dev/null 2>&1; then
  error "Docker Desktop is not running. Please start it and try again."
fi
success "Docker Desktop running"

# ── Virtual environment ───────────────────────────────────────────────────
info "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
  python3.9 -m venv .venv
  success "Created .venv"
else
  success ".venv already exists"
fi

source .venv/bin/activate
pip install --upgrade pip setuptools wheel -q
success "pip up to date"

# ── Install dependencies ──────────────────────────────────────────────────
info "Installing Python dependencies..."
pip install -r requirements.txt -q
success "Dependencies installed"

# ── Pre-commit hooks ──────────────────────────────────────────────────────
info "Installing pre-commit hooks..."
pip install pre-commit -q
pre-commit install -q
success "Pre-commit hooks installed"

# ── .env setup ────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn ".env created from template — add your API keys before running producers"
else
  success ".env already exists"
fi

# ── Create data directories ───────────────────────────────────────────────
mkdir -p data/risk_metrics jars
success "Data directories ready"

# ── Start Docker stack ────────────────────────────────────────────────────
info "Starting Docker services..."
docker compose up -d --quiet-pull
success "Docker services started"

# ── Wait for Kafka ────────────────────────────────────────────────────────
info "Waiting for Kafka to be healthy..."
RETRIES=20
until docker exec riskpulse-kafka kafka-broker-api-versions \
    --bootstrap-server localhost:9092 >/dev/null 2>&1; do
  RETRIES=$((RETRIES-1))
  if [ $RETRIES -eq 0 ]; then
    error "Kafka did not become healthy in time. Check: docker compose logs kafka"
  fi
  sleep 3
done
success "Kafka healthy"

# ── Create Kafka topics ───────────────────────────────────────────────────
info "Creating Kafka topics..."
for TOPIC in market-ticks portfolio-events risk-alerts; do
  docker exec riskpulse-kafka kafka-topics \
    --bootstrap-server localhost:9092 \
    --create --if-not-exists \
    --topic $TOPIC \
    --partitions 3 \
    --replication-factor 1 >/dev/null 2>&1
  success "Topic: $TOPIC"
done

# ── Run tests ─────────────────────────────────────────────────────────────
info "Running unit tests..."
pip install pytest -q
pytest tests/ -q --tb=short
success "All tests passing"

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           RiskPulse is ready to run!                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Start data flow (Terminal 1):"
echo "     source .venv/bin/activate && make simulate"
echo ""
echo "  2. Start stream processor (Terminal 2):"
echo "     source .venv/bin/activate"
echo "     python flink_jobs/vwap_job.py worker -l info --without-web"
echo ""
echo "  3. After 5 minutes, run dbt:"
echo "     cd riskpulse_dbt && dbt run && dbt test"
echo ""
echo "  4. Ingest into RAG and query:"
echo "     cd .. && python rag/rag_engine.py ingest"
echo "     python rag/rag_engine.py query 'which stocks are riskiest?'"
echo ""
echo "  Kafka UI  → http://localhost:8080"
echo "  MinIO     → http://localhost:9001"
echo "  Grafana   → http://localhost:3000"
echo ""
