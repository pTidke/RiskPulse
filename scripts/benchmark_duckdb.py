"""
scripts/benchmark_duckdb.py

DuckDB latency benchmark for RiskPulse.

Measures two things:
  1. MART queries  — what the API / RAG / dashboard actually run, against the
     dbt-built DuckDB file (data/riskpulse.duckdb). Captures the impact of
     view vs. table materialization.
  2. SCAN queries  — the same logical query run against a swappable lake source
     ({src}), so Parquet and Iceberg can be compared head-to-head.

For each query it reports cold-start (new connection per run) and warm
(reused connection) latency as p50 / p95 / p99 / mean over N iterations.

Run:  python scripts/benchmark_duckdb.py
      python scripts/benchmark_duckdb.py --sources parquet,iceberg --markdown
      make bench
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb

ROOT         = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))   # importable project modules when run as a script
DUCKDB_PATH  = ROOT / "data" / "riskpulse.duckdb"
PARQUET_GLOB = (ROOT / "data" / "risk_metrics" / "**" / "*.parquet").as_posix()

# ── Mart queries (run against the dbt-built DuckDB file) ───────────────────────
MART_QUERIES = {
    "mart_portfolio_summary": "SELECT * FROM mart_portfolio_summary",
    "mart_volatility_alerts": "SELECT * FROM mart_volatility_alerts",
    "latest_window_per_symbol": """
        SELECT symbol, window_end, vwap, volatility, drawdown_pct, session_high
        FROM (
            SELECT *, row_number() OVER (
                PARTITION BY symbol ORDER BY window_end DESC
            ) AS rn
            FROM fct_vwap_windows
        ) t
        WHERE rn = 1
    """,
}

# ── Lake-format scan queries ({src} swapped per source) ───────────────────────
SCAN_QUERIES = {
    "full_scan_count": "SELECT count(*) FROM {src}",
    "session_summary": """
        SELECT symbol,
               count(*)                  AS windows,
               round(avg(vwap), 2)       AS avg_vwap,
               round(avg(volatility), 6) AS avg_volatility,
               sum(trade_count)          AS total_trades
        FROM {src}
        GROUP BY symbol
        ORDER BY avg_volatility DESC
    """,
    "latest_per_symbol": """
        SELECT symbol, vwap, volatility
        FROM (
            SELECT *, row_number() OVER (
                PARTITION BY symbol ORDER BY window_end DESC
            ) AS rn
            FROM {src}
        ) t
        WHERE rn = 1
    """,
}


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile (p in 0..100)."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _time(con, sql: str, iters: int) -> tuple[list[float], int]:
    times, rows = [], 0
    for _ in range(iters):
        t0 = time.perf_counter()
        res = con.execute(sql).fetchall()
        times.append((time.perf_counter() - t0) * 1000.0)  # ms
        rows = len(res)
    return times, rows


def bench_warm(connect_fn, queries: dict, iters: int, warmup: int) -> dict:
    """Reuse one connection; warmup then measure steady-state latency."""
    con = connect_fn()
    results = {}
    for name, sql in queries.items():
        for _ in range(warmup):
            con.execute(sql).fetchall()
        results[name] = _time(con, sql, iters)
    con.close()
    return results


def bench_cold(connect_fn, queries: dict, iters: int) -> dict:
    """Fresh connection per iteration — captures connect + first-scan cost."""
    results = {}
    for name, sql in queries.items():
        times, rows = [], 0
        for _ in range(iters):
            con = connect_fn()
            t0 = time.perf_counter()
            res = con.execute(sql).fetchall()
            times.append((time.perf_counter() - t0) * 1000.0)
            rows = len(res)
            con.close()
        results[name] = (times, rows)
    return results


def print_table(title: str, cold: dict, warm: dict, markdown: bool) -> None:
    names = list(warm.keys())
    if markdown:
        print(f"\n#### {title}\n")
        print("| Query | Rows | Cold p50 | Cold p95 | Warm p50 | Warm p95 | Warm p99 |")
        print("| ----- | ---: | -------: | -------: | -------: | -------: | -------: |")
        for n in names:
            wt, rows = warm[n]
            ct, _    = cold[n]
            print(
                f"| `{n}` | {rows} "
                f"| {percentile(ct,50):.2f} ms | {percentile(ct,95):.2f} ms "
                f"| {percentile(wt,50):.2f} ms | {percentile(wt,95):.2f} ms "
                f"| {percentile(wt,99):.2f} ms |"
            )
        return

    print(f"\n── {title} " + "─" * max(0, 64 - len(title)))
    hdr = f"{'query':<26}{'rows':>5}{'cold p50':>11}{'cold p95':>11}{'warm p50':>11}{'warm p95':>11}{'warm p99':>11}"
    print(hdr)
    print("─" * len(hdr))
    for n in names:
        wt, rows = warm[n]
        ct, _    = cold[n]
        print(
            f"{n:<26}{rows:>5}"
            f"{percentile(ct,50):>9.2f}ms"
            f"{percentile(ct,95):>9.2f}ms"
            f"{percentile(wt,50):>9.2f}ms"
            f"{percentile(wt,95):>9.2f}ms"
            f"{percentile(wt,99):>9.2f}ms"
        )


def source_expr(name: str) -> str:
    """Return the FROM-clause expression for a named lake source."""
    if name == "parquet":
        return f"read_parquet('{PARQUET_GLOB}')"
    if name == "iceberg":
        from storage.iceberg_lake import scan_expr
        return scan_expr()
    raise ValueError(f"Unknown source: {name}")


def connect_lake(source: str):
    """Connection factory for lake-scan benchmarks (in-memory engine)."""
    def _connect():
        con = duckdb.connect()
        if source == "iceberg":
            from storage.iceberg_lake import configure_duckdb
            configure_duckdb(con)
        return con
    return _connect


def connect_marts_naive():
    """Naive serving connection — unqualified names against the default schema."""
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def connect_marts():
    """Fixed serving connection — marts schema selected up front (see rag_engine)."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    con.execute("USE main_marts")
    return con


def main() -> None:
    ap = argparse.ArgumentParser(description="RiskPulse DuckDB latency benchmark")
    ap.add_argument("--iters",   type=int, default=200, help="warm iterations per query")
    ap.add_argument("--cold",    type=int, default=30,  help="cold iterations per query")
    ap.add_argument("--warmup",  type=int, default=10,  help="warmup runs before warm timing")
    ap.add_argument("--sources", default="parquet",
                    help="comma-separated lake sources for scan queries (parquet,iceberg)")
    ap.add_argument("--markdown", action="store_true", help="emit Markdown tables")
    ap.add_argument("--skip-marts", action="store_true", help="skip the mart-query suite")
    args = ap.parse_args()

    if not args.markdown:
        print("=" * 78)
        print("  RiskPulse — DuckDB Latency Benchmark")
        print(f"  duckdb {duckdb.__version__} │ warm iters={args.iters} "
              f"(warmup {args.warmup}) │ cold iters={args.cold}")
        print("=" * 78)

    # 1) Mart queries — naive vs schema-qualified serving connection
    if not args.skip_marts:
        if not DUCKDB_PATH.exists():
            print(f"⚠️  {DUCKDB_PATH} not found — run `cd riskpulse_dbt && dbt run` first.")
        else:
            for label, factory in [
                ("naive (unqualified, default schema)", connect_marts_naive),
                ("fixed (USE main_marts)",              connect_marts),
            ]:
                cold = bench_cold(factory, MART_QUERIES, args.cold)
                warm = bench_warm(factory, MART_QUERIES, args.iters, args.warmup)
                print_table(f"Mart queries — {label}", cold, warm, args.markdown)

    # 2) Lake-format scan queries (Parquet vs Iceberg)
    for source in [s.strip() for s in args.sources.split(",") if s.strip()]:
        try:
            src = source_expr(source)
            queries = {n: sql.format(src=src) for n, sql in SCAN_QUERIES.items()}
            factory = connect_lake(source)
            cold = bench_cold(factory, queries, args.cold)
            warm = bench_warm(factory, queries, args.iters, args.warmup)
            print_table(f"Lake scan — {source}", cold, warm, args.markdown)
        except Exception as e:
            print(f"\n⚠️  source '{source}' skipped: {e}")


if __name__ == "__main__":
    main()
