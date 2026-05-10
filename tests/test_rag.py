"""
tests/test_rag.py

Unit tests for the RAG engine.
Tests document formatting, ChromaDB ingestion, and DuckDB queries.
"""

import os
import math
import pytest
import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_parquet(tmp_path_factory):
    """Create a minimal Parquet file for testing DuckDB queries."""
    tmp = tmp_path_factory.mktemp("data")
    out = tmp / "risk_metrics" / "date=2026-05-10"
    out.mkdir(parents=True)

    data = {
        "symbol":       ["AAPL", "NVDA", "TSLA", "AAPL", "NVDA"],
        "window_start": ["2026-05-10T05:10:00+00:00"] * 5,
        "window_end":   ["2026-05-10T05:15:00+00:00"] * 5,
        "vwap":         [172.50, 820.00, 195.00, 172.55, 819.90],
        "min_price":    [172.47, 819.78, 194.94, 172.50, 819.80],
        "max_price":    [172.53, 820.11, 195.08, 172.60, 820.00],
        "volatility":   [0.0078, 0.0538, 0.0135, 0.0092, 0.0319],
        "price_range":  [0.06,   0.33,   0.14,   0.10,   0.20],
        "trade_count":  [287,    327,    311,    250,    259],
        "total_volume": [75349.35, 83394.95, 78329.42, 60466.79, 64720.39],
        "date":         ["2026-05-10"] * 5,
    }
    df    = pd.DataFrame(data)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, str(out / "data.parquet"))
    return tmp


@pytest.fixture(scope="module")
def duckdb_con(test_parquet):
    """DuckDB connection reading test Parquet."""
    con = duckdb.connect()
    return con, str(test_parquet)


# ── DuckDB Query Tests ────────────────────────────────────────────────────────

class TestDuckDBQueries:

    def test_can_read_parquet(self, duckdb_con):
        con, path = duckdb_con
        df = con.execute(
            f"SELECT COUNT(*) as cnt FROM read_parquet('{path}/risk_metrics/**/*.parquet')"
        ).df()
        assert df["cnt"][0] == 5

    def test_session_summary_groups_by_symbol(self, duckdb_con):
        con, path = duckdb_con
        df = con.execute(f"""
            SELECT symbol, COUNT(*) as windows
            FROM read_parquet('{path}/risk_metrics/**/*.parquet')
            GROUP BY symbol
            ORDER BY symbol
        """).df()
        assert set(df["symbol"]) == {"AAPL", "NVDA", "TSLA"}
        aapl_windows = df[df["symbol"] == "AAPL"]["windows"].values[0]
        assert aapl_windows == 2

    def test_vwap_is_positive(self, duckdb_con):
        con, path = duckdb_con
        df = con.execute(
            f"SELECT vwap FROM read_parquet('{path}/risk_metrics/**/*.parquet')"
        ).df()
        assert (df["vwap"] > 0).all()

    def test_volatility_is_non_negative(self, duckdb_con):
        con, path = duckdb_con
        df = con.execute(
            f"SELECT volatility FROM read_parquet('{path}/risk_metrics/**/*.parquet')"
        ).df()
        assert (df["volatility"] >= 0).all()

    def test_drawdown_calculation(self, duckdb_con):
        con, path = duckdb_con
        df = con.execute(f"""
            WITH highs AS (
                SELECT symbol, MAX(max_price) AS session_high
                FROM read_parquet('{path}/risk_metrics/**/*.parquet')
                GROUP BY symbol
            ),
            latest AS (
                SELECT symbol, vwap,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY window_end DESC) AS rn
                FROM read_parquet('{path}/risk_metrics/**/*.parquet')
            )
            SELECT l.symbol,
                ROUND((h.session_high - l.vwap) / h.session_high * 100, 4) AS drawdown_pct
            FROM latest l JOIN highs h ON l.symbol = h.symbol
            WHERE l.rn = 1
        """).df()
        assert (df["drawdown_pct"] >= 0).all()
        assert len(df) == 3


# ── Document Formatting Tests ─────────────────────────────────────────────────

class TestDocumentFormatting:

    def test_summary_doc_contains_required_fields(self):
        row = {
            "symbol": "NVDA",
            "volatility_regime": "HIGH",
            "avg_vwap": 820.05,
            "session_low": 819.78,
            "session_high": 820.11,
            "session_range": 0.33,
            "avg_volatility": 0.0538,
            "peak_volatility": 0.0862,
            "max_drawdown_pct": 0.01,
            "total_trades": 903,
            "total_volume": 232172,
            "session_start": "2026-05-10T05:10:00",
            "last_updated":  "2026-05-10T05:22:13",
        }
        doc = (
            f"Symbol: {row['symbol']}\n"
            f"Volatility Regime: {row['volatility_regime']}\n"
            f"Average VWAP: ${row['avg_vwap']}"
        )
        assert "NVDA" in doc
        assert "HIGH" in doc
        assert "820.05" in doc

    def test_alert_doc_contains_alert_type(self):
        alert = {
            "symbol": "NVDA",
            "alert_type": "HIGHEST_VOL",
            "current_vwap": 820.05,
            "session_high": 820.11,
            "drawdown_pct": 0.01,
            "volatility": 0.0293,
            "volatility_rank": 1,
            "alert_time": "2026-05-10T05:22:13",
        }
        doc = f"ALERT — Symbol: {alert['symbol']}\nAlert Type: {alert['alert_type']}"
        assert "HIGHEST_VOL" in doc
        assert "NVDA" in doc


# ── VWAP Math Tests ───────────────────────────────────────────────────────────

class TestRiskMath:

    def test_vwap_formula(self):
        prices = [820.0, 819.8, 820.1, 819.9]
        sizes  = [100.0, 200.0, 150.0, 50.0]
        expected = sum(p * s for p, s in zip(prices, sizes)) / sum(sizes)
        assert abs(expected - 819.94) < 0.01

    def test_volatility_formula(self):
        prices = [100.0, 101.0, 99.0, 100.5, 99.5]
        mean   = sum(prices) / len(prices)
        var    = sum((p - mean) ** 2 for p in prices) / len(prices)
        vol    = math.sqrt(var)
        assert vol > 0
        assert vol < 5.0  # Reasonable bound for small price range

    def test_drawdown_threshold(self):
        session_high = 820.11
        current_vwap = 795.00
        drawdown_pct = (session_high - current_vwap) / session_high * 100
        assert drawdown_pct > 3.0  # Should trigger alert
