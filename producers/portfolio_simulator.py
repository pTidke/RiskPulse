"""
producers/portfolio_simulator.py

Simulates a live portfolio producing TWO Kafka streams simultaneously:
  - market-ticks:      synthetic price ticks (works like a real feed)
  - portfolio-events:  buy/sell/rebalance events

Requires no API keys. Great for local dev and CI testing.
Mimics a $10M institutional portfolio with realistic price drift.

Run: python producers/portfolio_simulator.py
  or: make simulate
"""

import json
import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from loguru import logger
from confluent_kafka import Producer

load_dotenv()

TICK_TOPIC   = "market-ticks"
EVENTS_TOPIC = "portfolio-events"

# Demo portfolio — modify to taste
PORTFOLIO = {
    "AAPL": {"shares": 500,  "avg_cost": 172.50, "volatility": 0.015},
    "MSFT": {"shares": 300,  "avg_cost": 415.00, "volatility": 0.012},
    "NVDA": {"shares": 150,  "avg_cost": 820.00, "volatility": 0.028},
    "GOOGL": {"shares": 200, "avg_cost": 170.00, "volatility": 0.014},
    "META":  {"shares": 180, "avg_cost": 490.00, "volatility": 0.020},
    "TSLA":  {"shares": 100, "avg_cost": 195.00, "volatility": 0.035},
    "SPY":   {"shares": 400, "avg_cost": 510.00, "volatility": 0.008},
    "QQQ":   {"shares": 250, "avg_cost": 440.00, "volatility": 0.010},
}

EVENT_TYPES = ["BUY", "SELL", "REBALANCE", "DIVIDEND"]
WEIGHTS     = [0.40,  0.35,  0.15,         0.10]

# Track simulated "current price" per symbol with GBM drift
_current_prices = {sym: d["avg_cost"] for sym, d in PORTFOLIO.items()}

producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "client.id": "portfolio-simulator",
    "acks": "1",
    "linger.ms": 5,
})


def delivery_report(err, msg):
    if err is not None:
        logger.warning(f"Delivery failed [{msg.topic()}]: {err}")


def next_price(symbol: str) -> float:
    """Geometric Brownian Motion step — realistic price path simulation."""
    data  = PORTFOLIO[symbol]
    dt    = 1 / 252 / 6.5 / 3600  # 1-second step in trading-year terms
    drift = 0.08 * dt              # ~8% annual drift
    vol   = data["volatility"] * math.sqrt(dt)
    shock = random.gauss(0, 1)
    _current_prices[symbol] *= math.exp(drift + vol * shock)
    return round(_current_prices[symbol], 2)


def emit_tick(symbol: str) -> dict:
    price = next_price(symbol)
    size  = round(random.uniform(10, 500), 2)
    tick  = {
        "symbol":    symbol,
        "price":     price,
        "size":      size,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source":    "simulator",
        "exchange":  random.choice(["NYSE", "NASDAQ", "ARCA"]),
        "conditions": [],
    }
    producer.produce(
        topic=TICK_TOPIC,
        key=symbol.encode(),
        value=json.dumps(tick).encode(),
        on_delivery=delivery_report,
    )
    return tick


def emit_portfolio_event(symbol: str) -> dict:
    pos        = PORTFOLIO[symbol]
    price      = _current_prices[symbol]
    event_type = random.choices(EVENT_TYPES, weights=WEIGHTS)[0]
    shares     = random.randint(1, max(1, pos["shares"] // 8))
    unrealized = (price - pos["avg_cost"]) * pos["shares"]

    event = {
        "event_type":   event_type,
        "symbol":       symbol,
        "shares":       shares,
        "price":        round(price, 2),
        "notional":     round(shares * price, 2),
        "portfolio_id": "DEMO-PORTFOLIO-001",
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "avg_cost":       pos["avg_cost"],
            "total_shares":   pos["shares"],
            "unrealized_pnl": round(unrealized, 2),
            "pnl_pct":        round((price / pos["avg_cost"] - 1) * 100, 2),
        },
    }
    producer.produce(
        topic=EVENTS_TOPIC,
        key=symbol.encode(),
        value=json.dumps(event).encode(),
        on_delivery=delivery_report,
    )
    return event


def main():
    logger.info(f"Portfolio simulator starting")
    logger.info(f"  Tick topic:   {TICK_TOPIC}")
    logger.info(f"  Events topic: {EVENTS_TOPIC}")
    logger.info(f"  Symbols:      {list(PORTFOLIO.keys())}")
    logger.info("  Kafka UI → http://localhost:8080")

    tick_counter  = 0
    event_counter = 0

    def shutdown(sig, frame):
        logger.info(
            f"Shutting down | {tick_counter} ticks, {event_counter} events sent"
        )
        producer.flush(timeout=10)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        # Emit 3–5 ticks per cycle across random symbols
        tick_symbols = random.choices(list(PORTFOLIO.keys()), k=random.randint(3, 5))
        for sym in tick_symbols:
            tick = emit_tick(sym)
            tick_counter += 1
            logger.debug(
                f"[TICK]  {sym:<5} @ ${tick['price']:>9.2f} × {tick['size']:>6.1f}"
            )

        # Every ~10 cycles emit a portfolio event
        if random.random() < 0.10:
            sym   = random.choice(list(PORTFOLIO.keys()))
            event = emit_portfolio_event(sym)
            event_counter += 1
            pnl   = event["metadata"]["unrealized_pnl"]
            pnl_s = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
            logger.info(
                f"[EVENT] {event['event_type']:<9} {sym:<5} "
                f"× {event['shares']:>3} @ ${event['price']:.2f} "
                f"  PnL: {pnl_s}"
            )

        producer.poll(0)

        # Status summary every 100 ticks
        if tick_counter % 100 == 0:
            total_value = sum(
                _current_prices[s] * PORTFOLIO[s]["shares"]
                for s in PORTFOLIO
            )
            logger.info(
                f"── {tick_counter:,} ticks │ {event_counter:,} events │ "
                f"Portfolio: ${total_value:,.0f} ──"
            )

        time.sleep(random.uniform(0.1, 0.4))


if __name__ == "__main__":
    main()
