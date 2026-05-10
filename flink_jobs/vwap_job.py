"""
flink_jobs/vwap_job.py  (powered by Faust — Robinhood's stream processor)

Reads market-ticks from Kafka and computes per 5-minute window:
  - VWAP (volume-weighted average price)
  - Min / max price, volatility (std dev), trade count, total volume
  - Drawdown alert when VWAP drops >3% from session high

Writes results to:
  - Parquet files in ./data/risk_metrics/ (queryable by DuckDB)
  - risk-alerts Kafka topic

Run: make flink
  or: python flink_jobs/vwap_job.py worker -l info
"""

import asyncio
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import faust
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
OUTPUT_DIR      = Path("./data/risk_metrics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_SECONDS  = 300   # 5-minute tumbling window
DRAWDOWN_THRESH = 0.03  # 3% drawdown triggers alert

# ── Faust app ─────────────────────────────────────────────────────────────────
app = faust.App(
    "riskpulse-vwap",
    broker=f"kafka://{KAFKA_BOOTSTRAP}",
    value_serializer="raw",
    consumer_auto_offset_reset="latest",
    topic_partitions=3,
)

tick_topic  = app.topic("market-ticks",  value_type=bytes)
alert_topic = app.topic("risk-alerts",   value_type=bytes)

# ── In-memory window state ────────────────────────────────────────────────────
# {symbol: {"prices": [], "sizes": [], "window_start": timestamp}}
_windows: dict = defaultdict(lambda: {
    "prices": [], "sizes": [], "window_start": None
})

# Session highs for drawdown detection
_session_highs: dict = defaultdict(float)


def _current_window_start() -> datetime:
    """Snap current time to the nearest 5-minute boundary."""
    now = datetime.now(timezone.utc)
    snapped = now.replace(
        minute=(now.minute // 5) * 5,
        second=0,
        microsecond=0
    )
    return snapped


def _compute_metrics(symbol: str, prices: list, sizes: list,
                     window_start: datetime, window_end: datetime) -> dict:
    """Compute all risk metrics for a closed window."""
    if not prices:
        return {}

    n        = len(prices)
    total_sz = sum(sizes)
    vwap     = sum(p * s for p, s in zip(prices, sizes)) / total_sz if total_sz else 0
    mean     = sum(prices) / n
    variance = sum((p - mean) ** 2 for p in prices) / n
    vol      = math.sqrt(variance)

    return {
        "symbol":       symbol,
        "window_start": window_start.isoformat(),
        "window_end":   window_end.isoformat(),
        "vwap":         round(vwap, 4),
        "min_price":    round(min(prices), 4),
        "max_price":    round(max(prices), 4),
        "volatility":   round(vol, 6),
        "price_range":  round(max(prices) - min(prices), 4),
        "trade_count":  n,
        "total_volume": round(total_sz, 2),
    }


def _write_parquet(metrics: dict) -> None:
    """Append a window result to a date-partitioned Parquet file."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = OUTPUT_DIR / f"date={date_str}" / "data.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([metrics])
    table = pa.Table.from_pandas(df)

    if out_path.exists():
        existing = pq.read_table(str(out_path))
        combined = pa.concat_tables([existing, table])
        pq.write_table(combined, str(out_path))
    else:
        pq.write_table(table, str(out_path))


def _check_drawdown(symbol: str, vwap: float) -> bool:
    """Update session high and return True if drawdown threshold exceeded."""
    if vwap > _session_highs[symbol]:
        _session_highs[symbol] = vwap
    session_high = _session_highs[symbol]
    if session_high > 0:
        drawdown = (session_high - vwap) / session_high
        return drawdown > DRAWDOWN_THRESH
    return False


async def _flush_window(symbol: str) -> None:
    """Close the current window, compute metrics, write output, emit alert."""
    state = _windows[symbol]
    if not state["prices"]:
        return

    window_start = state["window_start"] or _current_window_start()
    window_end   = datetime.now(timezone.utc)

    metrics = _compute_metrics(
        symbol, state["prices"], state["sizes"],
        window_start, window_end
    )

    # Reset window
    _windows[symbol] = {"prices": [], "sizes": [], "window_start": None}

    # Write to Parquet
    _write_parquet(metrics)

    # Drawdown check → emit alert
    is_drawdown = _check_drawdown(symbol, metrics["vwap"])
    if is_drawdown:
        metrics["alert_type"] = "DRAWDOWN"
        metrics["session_high"] = _session_highs[symbol]
        metrics["drawdown_pct"] = round(
            (_session_highs[symbol] - metrics["vwap"]) / _session_highs[symbol] * 100, 2
        )
        logger.warning(
            f"⚠️  DRAWDOWN ALERT  {symbol:<5}  "
            f"VWAP ${metrics['vwap']:.2f}  "
            f"Session high ${_session_highs[symbol]:.2f}  "
            f"({metrics['drawdown_pct']}% drop)"
        )
        await alert_topic.send(
            key=symbol,
            value=json.dumps(metrics).encode()
        )
    else:
        await alert_topic.send(
            key=symbol,
            value=json.dumps(metrics).encode()
        )

    close_price = state["prices"][-1] if state["prices"] else metrics["vwap"]
    open_price = state["prices"][0] if state["prices"] else metrics["vwap"]
    pnl_dir = "▲" if close_price >= open_price else "▼"
    logger.info(
        f"[WINDOW] {symbol:<5}  VWAP ${metrics['vwap']:>9.2f}  "
        f"Vol {metrics['volatility']:.4f}  "
        f"Trades {metrics['trade_count']:>4}  {pnl_dir}"
    )


# ── Faust agent — consumes market-ticks ──────────────────────────────────────
@app.agent(tick_topic)
async def process_ticks(stream):
    async for raw in stream:
        try:
            tick   = json.loads(raw)
            symbol = tick["symbol"]
            price  = float(tick["price"])
            size   = float(tick["size"])

            state = _windows[symbol]

            # Initialise window start on first tick
            if state["window_start"] is None:
                state["window_start"] = _current_window_start()

            # Check if current tick is outside the current window
            elapsed = (
                datetime.now(timezone.utc) - state["window_start"]
            ).total_seconds()

            if elapsed >= WINDOW_SECONDS:
                await _flush_window(symbol)
                _windows[symbol]["window_start"] = _current_window_start()

            # Accumulate tick into window
            _windows[symbol]["prices"].append(price)
            _windows[symbol]["sizes"].append(size)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Malformed tick skipped: {e}")


# ── Background timer — flushes all windows every 5 minutes ───────────────────
@app.timer(interval=WINDOW_SECONDS)
async def flush_all_windows():
    symbols = list(_windows.keys())
    if not symbols:
        return
    logger.info(f"Timer flush — {len(symbols)} active symbols")
    for symbol in symbols:
        await _flush_window(symbol)


# ── Startup banner ────────────────────────────────────────────────────────────
@app.task
async def startup_banner():
    logger.info("=" * 60)
    logger.info("  RiskPulse — Faust VWAP Stream Processor")
    logger.info("=" * 60)
    logger.info(f"  Kafka:   {KAFKA_BOOTSTRAP}")
    logger.info(f"  Window:  {WINDOW_SECONDS}s (5 minutes)")
    logger.info(f"  Output:  {OUTPUT_DIR.resolve()}")
    logger.info(f"  Alerts:  risk-alerts topic")
    logger.info("=" * 60)
    logger.info("  Kafka UI → http://localhost:8080")
    logger.info("  make query to see DuckDB results")
    logger.info("=" * 60)


if __name__ == "__main__":
    app.main()