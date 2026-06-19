"""
tests/test_iceberg.py

Tests for the Iceberg lake mirror (storage/iceberg_lake.py):
  - MinIO endpoint normalization (pure logic, always runs)
  - PyIceberg write -> DuckDB read round-trip on a local-filesystem warehouse
    (no MinIO needed; skips cleanly if pyiceberg / the duckdb iceberg extension
    are unavailable, so it never breaks CI)
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from storage.iceberg_lake import _split_endpoint


class TestEndpointNormalization:
    def test_strips_http_scheme(self):
        host, url, secure = _split_endpoint("http://localhost:9000")
        assert host == "localhost:9000"
        assert url == "http://localhost:9000"
        assert secure is False

    def test_bare_host_gets_http_url(self):
        host, url, secure = _split_endpoint("localhost:9000")
        assert host == "localhost:9000"
        assert url == "http://localhost:9000"
        assert secure is False

    def test_https_marked_secure(self):
        host, url, secure = _split_endpoint("https://minio.example.com")
        assert host == "minio.example.com"
        assert url == "https://minio.example.com"
        assert secure is True

    def test_trailing_slash_trimmed(self):
        host, url, _ = _split_endpoint("http://localhost:9000/")
        assert host == "localhost:9000"
        assert url == "http://localhost:9000"


class TestIcebergRoundTrip:
    """Local-FS warehouse round-trip — no MinIO required."""

    def test_write_then_duckdb_read(self, tmp_path):
        pytest.importorskip("pyiceberg")
        import duckdb
        import pyarrow as pa
        from pyiceberg.catalog.sql import SqlCatalog

        wh = tmp_path / "wh"
        wh.mkdir()
        cat = SqlCatalog("t", uri=f"sqlite:///{wh}/catalog.db", warehouse=str(wh))
        cat.create_namespace("ns")

        tbl = pa.table({
            "symbol":      ["AAPL", "NVDA", "AAPL"],
            "vwap":        [172.5, 820.0, 173.0],
            "trade_count": [10, 20, 30],
        })
        ice = cat.create_table("ns.t", schema=tbl.schema)
        ice.append(tbl)

        # PyIceberg can read what it wrote
        assert ice.scan().to_arrow().num_rows == 3

        # DuckDB can read the same table via iceberg_scan (plain metadata path)
        con = duckdb.connect()
        try:
            con.execute("INSTALL iceberg")
            con.execute("LOAD iceberg")
        except Exception:
            pytest.skip("duckdb iceberg extension unavailable")

        meta = ice.metadata_location.replace("file://", "")
        total = con.execute(f"SELECT count(*) FROM iceberg_scan('{meta}')").fetchone()[0]
        aapl  = con.execute(
            f"SELECT count(*) FROM iceberg_scan('{meta}') WHERE symbol = 'AAPL'"
        ).fetchone()[0]
        assert total == 3
        assert aapl == 2
