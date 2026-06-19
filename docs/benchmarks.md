# RiskPulse — DuckDB Latency Benchmarks

Reproducible latency measurements for the analytical query layer, captured with
[`scripts/benchmark_duckdb.py`](../scripts/benchmark_duckdb.py) (`make bench`).

**Method.** Each query is timed over many iterations on a single machine.
*Cold* uses a fresh DuckDB connection per run (connect + first-scan cost);
*warm* reuses one connection after a warmup (steady-state execution). Figures
are wall-clock milliseconds: `duckdb 0.10.3`, warm iters = 200, cold iters = 30.
Absolute numbers are hardware-dependent — the **deltas between rows** are the point.

Two suites:
- **Serving-layer mart queries** — exactly what the API / RAG / dashboard run
  against the dbt-built DuckDB file (marts materialized as `table` with enforced
  contracts).
- **Lake scans** — the same logical query against a swappable source, so
  **Parquet vs Iceberg** can be compared head-to-head.

---

## Serving-layer mart queries

> **Finding: a ~20× win hiding in the connection setup.** dbt builds the marts in
> the `main_marts` schema, but a DuckDB connection's default schema is `main`.
> Leaving table names unqualified forces DuckDB to resolve them *across schemas*
> on a file-backed database — ~11 ms **per query**. Selecting the schema up front
> (`USE main_marts`, now done in `connect_marts()`) drops that to ~0.5 ms. The API
> and RAG layer previously paid this on every request.

### Naive — unqualified names, default `main` schema

| Query | Rows | Cold p50 | Cold p95 | Warm p50 | Warm p95 | Warm p99 |
| ----- | ---: | -------: | -------: | -------: | -------: | -------: |
| `mart_portfolio_summary` | 8 | 11.66 ms | 13.04 ms | 10.70 ms | 11.57 ms | 11.80 ms |
| `mart_volatility_alerts` | 3 | 11.11 ms | 11.51 ms | 11.27 ms | 14.00 ms | 15.00 ms |
| `latest_window_per_symbol` | 8 | 10.33 ms | 10.77 ms | 10.38 ms | 11.03 ms | 11.21 ms |

### Fixed — schema selected up front (`USE main_marts`, read-only)

| Query | Rows | Cold p50 | Cold p95 | Warm p50 | Warm p95 | Warm p99 |
| ----- | ---: | -------: | -------: | -------: | -------: | -------: |
| `mart_portfolio_summary` | 8 | 0.62 ms | 0.72 ms | **0.51 ms** | 0.55 ms | 0.58 ms |
| `mart_volatility_alerts` | 3 | 0.38 ms | 0.41 ms | **0.31 ms** | 0.33 ms | 0.36 ms |
| `latest_window_per_symbol` | 8 | 1.11 ms | 1.25 ms | **0.96 ms** | 1.04 ms | 1.08 ms |

**~11–36× lower latency** per query, just from qualifying the schema — no data or
hardware change.

> **Why `table` instead of `view`.** The marts are materialized as tables, so a
> serving query is a precomputed lookup (~0.5 ms) rather than a re-run of the
> `stg → fct → mart` DAG over Parquet on every call. The cost a view would pay is
> visible in the lake-scan numbers below (and it grows with data volume); the
> table cost stays flat.

---

## Lake scans

The same logical queries against (a) the local Parquet lake and (b) the Iceberg
table on MinIO. Data is identical (the Iceberg table is a faithful snapshot of
the lake); the difference is purely the storage/format path.

### Parquet (`read_parquet` over the local date-partitioned lake)

| Query | Rows | Cold p50 | Cold p95 | Warm p50 | Warm p95 | Warm p99 |
| ----- | ---: | -------: | -------: | -------: | -------: | -------: |
| `full_scan_count` | 1 | 1.24 ms | 1.46 ms | 1.19 ms | 1.45 ms | 1.71 ms |
| `session_summary` | 8 | 2.43 ms | 2.76 ms | 2.26 ms | 2.41 ms | 2.59 ms |
| `latest_per_symbol` | 8 | 3.00 ms | 3.33 ms | 2.91 ms | 3.30 ms | 3.48 ms |

### Iceberg (`iceberg_scan` over MinIO / S3)

| Query | Rows | Cold p50 | Cold p95 | Warm p50 | Warm p95 | Warm p99 |
| ----- | ---: | -------: | -------: | -------: | -------: | -------: |
| `full_scan_count` | 1 | 9.85 ms | 16.67 ms | 7.91 ms | 9.84 ms | 11.64 ms |
| `session_summary` | 8 | 11.63 ms | 15.67 ms | 9.90 ms | 11.28 ms | 13.12 ms |
| `latest_per_symbol` | 8 | 11.97 ms | 13.58 ms | 10.68 ms | 12.27 ms | 14.66 ms |

**Iceberg-on-MinIO is ~4–8× slower than local Parquet** — each scan makes S3
round-trips for the table metadata, manifest list, manifests, then data files,
versus a single local-disk read. That latency buys the lakehouse properties
(snapshots / time-travel, schema evolution, hidden partitioning, ACID commits);
for a low-latency *serving* path, the precomputed DuckDB marts (~0.5 ms above)
are the right tool. Different layers, different jobs.

> Reproduce: `make iceberg && make bench` (the Iceberg suite needs the stack up
> and the table loaded; `python scripts/benchmark_duckdb.py --sources parquet,iceberg`).
