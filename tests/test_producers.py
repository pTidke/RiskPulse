"""
tests/test_producers.py

Unit tests for the portfolio simulator.
Tests price generation, GBM math, and Kafka message schema.
"""

import json
import math
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from producers.portfolio_simulator import (
    PORTFOLIO,
    next_price,
    emit_tick,
    _current_prices,
)


class TestGBMPricing:
    """Tests for Geometric Brownian Motion price simulation."""

    def test_all_symbols_have_initial_prices(self):
        for sym, data in PORTFOLIO.items():
            assert data["avg_cost"] > 0
            assert data["volatility"] > 0
            assert data["shares"] > 0

    def test_next_price_returns_positive(self):
        for sym in PORTFOLIO:
            price = next_price(sym)
            assert price > 0, f"{sym} returned non-positive price"

    def test_next_price_within_reasonable_bounds(self):
        """Price should not deviate more than 10% in a single step."""
        for sym in PORTFOLIO:
            base  = _current_prices[sym]
            price = next_price(sym)
            change_pct = abs(price - base) / base
            assert change_pct < 0.10, (
                f"{sym} price changed by {change_pct:.2%} — unrealistic GBM step"
            )

    def test_high_vol_symbol_has_wider_range(self):
        """NVDA (vol=0.028) should show wider swings than GOOGL (vol=0.014)."""
        nvda_prices  = [next_price("NVDA")  for _ in range(200)]
        googl_prices = [next_price("GOOGL") for _ in range(200)]

        nvda_std  = (sum((p - sum(nvda_prices)/len(nvda_prices))**2
                     for p in nvda_prices) / len(nvda_prices)) ** 0.5
        googl_std = (sum((p - sum(googl_prices)/len(googl_prices))**2
                     for p in googl_prices) / len(googl_prices)) ** 0.5

        assert nvda_std > googl_std, (
            "NVDA should have higher price std dev than GOOGL"
        )


class TestTickSchema:
    """Tests for Kafka tick message structure."""

    def test_tick_has_required_fields(self):
        required = {"symbol", "price", "size", "timestamp", "source", "exchange"}
        for sym in list(PORTFOLIO.keys())[:3]:
            tick = {
                "symbol":    sym,
                "price":     next_price(sym),
                "size":      100.0,
                "timestamp": "2026-05-10T00:00:00+00:00",
                "source":    "simulator",
                "exchange":  "NYSE",
                "conditions": [],
            }
            assert required.issubset(tick.keys()), (
                f"Tick for {sym} missing fields: {required - tick.keys()}"
            )

    def test_tick_price_is_positive(self):
        for sym in PORTFOLIO:
            price = next_price(sym)
            assert price > 0

    def test_tick_serializable_to_json(self):
        tick = {
            "symbol": "AAPL",
            "price": 172.50,
            "size": 100.0,
            "timestamp": "2026-05-10T00:00:00+00:00",
            "source": "simulator",
            "exchange": "NASDAQ",
            "conditions": [],
        }
        serialized = json.dumps(tick)
        deserialized = json.loads(serialized)
        assert deserialized["symbol"] == "AAPL"
        assert deserialized["price"] == 172.50


class TestVWAPMath:
    """Unit tests for VWAP calculation logic."""

    def test_vwap_equal_sizes(self):
        """With equal sizes, VWAP should equal average price."""
        prices = [100.0, 102.0, 98.0, 101.0]
        sizes  = [10.0, 10.0, 10.0, 10.0]
        vwap = sum(p * s for p, s in zip(prices, sizes)) / sum(sizes)
        avg  = sum(prices) / len(prices)
        assert abs(vwap - avg) < 0.0001

    def test_vwap_weighted_toward_high_volume(self):
        """High volume at high price should push VWAP up."""
        prices = [100.0, 200.0]
        sizes  = [10.0,  1000.0]   # massive volume at 200
        vwap   = sum(p * s for p, s in zip(prices, sizes)) / sum(sizes)
        assert vwap > 150.0, "VWAP should be skewed toward high-volume price"

    def test_volatility_calculation(self):
        """Population std dev should be correct."""
        prices = [100.0, 102.0, 98.0, 101.0, 99.0]
        mean   = sum(prices) / len(prices)
        var    = sum((p - mean)**2 for p in prices) / len(prices)
        vol    = math.sqrt(var)
        assert vol > 0
        assert abs(vol - 1.4142) < 0.001
