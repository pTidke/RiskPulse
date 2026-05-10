"""
storage/duckdb_query.py

Queries RiskPulse Parquet files written locally by the Faust job.
Uses DuckDB — free, zero config, reads Parquet natively.

Run: python storage/duckdb_query.py
  or: make query
"""

import duckdb
from loguru import logger

LOCAL_PATH = "./data/risk_metrics/**/*.parquet"


def get_con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def session_summary() -> None:
    """VWAP + volatility summary across all windows in the session."""
    con = get_con()
    df = con.execute(f"""
        SELECT
            symbol,
            COUNT(*)                                               AS windows,
            ROUND(AVG(vwap), 2)                                    AS avg_vwap,
            ROUND(MIN(min_price), 2)                               AS session_low,
            ROUND(MAX(max_price), 2)                               AS session_high,
            ROUND(AVG(volatility), 6)                              AS avg_volatility,
            ROUND(MAX(max_price) / NULLIF(MIN(min_price),0) - 1, 4) AS session_range_pct,
            SUM(trade_count)                                       AS total_trades,
            ROUND(SUM(total_volume), 0)                            AS total_volume
        FROM read_parquet('{LOCAL_PATH}')
        GROUP BY symbol
        ORDER BY avg_volatility DESC
    """).df()
    print("\n── Session Summary (sorted by volatility) ──────────────")
    print(df.to_string(index=False))


def latest_vwap() -> None:
    """Most recent 5-min window per symbol."""
    con = get_con()
    df = con.execute(f"""
        SELECT
            symbol,
            window_end,
            ROUND(vwap, 2)       AS vwap,
            ROUND(volatility, 6) AS volatility,
            trade_count,
            ROUND(total_volume, 0) AS total_volume
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY symbol ORDER BY window_end DESC
            ) AS rn
            FROM read_parquet('{LOCAL_PATH}')
        ) t
        WHERE rn = 1
        ORDER BY volatility DESC
    """).df()
    print("\n── Latest VWAP per Symbol ──────────────────────────────")
    print(df.to_string(index=False))


def drawdown_alerts() -> None:
    """Symbols where VWAP dropped >3% from their session high."""
    con = get_con()
    df = con.execute(f"""
        WITH session_highs AS (
            SELECT symbol, MAX(max_price) AS session_high
            FROM read_parquet('{LOCAL_PATH}')
            GROUP BY symbol
        ),
        latest AS (
            SELECT symbol, vwap, window_end,
                   ROW_NUMBER() OVER (
                       PARTITION BY symbol ORDER BY window_end DESC
                   ) AS rn
            FROM read_parquet('{LOCAL_PATH}')
        )
        SELECT
            l.symbol,
            ROUND(l.vwap, 2)                                              AS current_vwap,
            ROUND(sh.session_high, 2)                                     AS session_high,
            ROUND((sh.session_high - l.vwap) / sh.session_high * 100, 2) AS drawdown_pct,
            l.window_end
        FROM latest l
        JOIN session_highs sh ON l.symbol = sh.symbol
        WHERE l.rn = 1
          AND (sh.session_high - l.vwap) / sh.session_high > 0.03
        ORDER BY drawdown_pct DESC
    """).df()

    print("\n── Drawdown Alerts (>3% from session high) ─────────────")
    if df.empty:
        print("   ✅ No active drawdown alerts")
    else:
        print(df.to_string(index=False))


def volatility_by_window() -> None:
    """Volatility trend per symbol across all windows."""
    con = get_con()
    df = con.execute(f"""
        SELECT
            symbol,
            window_start,
            ROUND(vwap, 2)         AS vwap,
            ROUND(volatility, 6)   AS volatility,
            trade_count
        FROM read_parquet('{LOCAL_PATH}')
        ORDER BY symbol, window_start
    """).df()
    print("\n── Volatility Across Windows ───────────────────────────")
    print(df.to_string(index=False))


if __name__ == "__main__":
    logger.info(f"Reading Parquet from: {LOCAL_PATH}")
    try:
        session_summary()
        latest_vwap()
        drawdown_alerts()
        volatility_by_window()
        print()
    except Exception as e:
        logger.error(
            f"Query failed: {e}\n"
            "Is data flowing? Try: make simulate && make flink"
        )