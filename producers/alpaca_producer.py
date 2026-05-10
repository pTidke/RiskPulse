"""
producers/alpaca_producer.py

Streams real-time equity tick data from Alpaca WebSocket → Kafka market-ticks topic.
Uses Alpaca's FREE paper trading account (no real money required).

Setup:
  1. Sign up at alpaca.markets (free)
  2. Generate paper trading API keys
  3. Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env

Run: python producers/alpaca_producer.py
  or: make alpaca
"""

import json
import os
import signal
import sys
from datetime import timezone
from dotenv import load_dotenv
from loguru import logger
from confluent_kafka import Producer
from alpaca.data.live import StockDataStream
from alpaca.data.models import Trade

load_dotenv()

KAFKA_TOPIC = "market-ticks"

# Symbols to stream — adjust to your portfolio
SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL",
    "META", "TSLA", "SPY", "QQQ",
]

producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "client.id": "alpaca-market-producer",
    "acks": "1",
    "linger.ms": 10,
    "batch.size": 32768,
    "compression.type": "snappy",
})


def delivery_report(err, msg):
    if err is not None:
        logger.warning(f"Delivery failed [{msg.key()}]: {err}")


def on_trade(trade: Trade):
    """Fires on every incoming tick from Alpaca WebSocket."""
    payload = {
        "symbol":     trade.symbol,
        "price":      float(trade.price),
        "size":       float(trade.size),
        "timestamp":  trade.timestamp.astimezone(timezone.utc).isoformat(),
        "source":     "alpaca",
        "exchange":   getattr(trade, "exchange", "unknown"),
        "conditions": getattr(trade, "conditions", []),
    }

    producer.produce(
        topic=KAFKA_TOPIC,
        key=trade.symbol.encode("utf-8"),
        value=json.dumps(payload).encode("utf-8"),
        on_delivery=delivery_report,
    )
    producer.poll(0)  # non-blocking delivery callback flush

    logger.info(
        f"[ALPACA] {trade.symbol:<5} @ ${trade.price:>9.2f} "
        f"× {trade.size:>6.1f}  ({trade.exchange})"
    )


def main():
    api_key    = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key or api_key == "your_api_key_here":
        logger.error(
            "Alpaca API keys not set. Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env\n"
            "Get free paper trading keys at: https://alpaca.markets\n"
            "To run with simulated data instead: make simulate"
        )
        sys.exit(1)

    logger.info(f"Alpaca producer starting → topic: {KAFKA_TOPIC}")
    logger.info(f"Symbols: {SYMBOLS}")

    wss = StockDataStream(api_key, secret_key)
    wss.subscribe_trades(on_trade, *SYMBOLS)

    def shutdown(sig, frame):
        logger.info("Shutting down producer...")
        producer.flush(timeout=15)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    wss.run()


if __name__ == "__main__":
    main()
