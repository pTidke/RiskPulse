"""
scripts/generate_test_data.py

Generates minimal Parquet test data for CI/CD pipelines.
Used by GitHub Actions so dbt can run without a live Faust job.

Run: python scripts/generate_test_data.py
"""

import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

OUTPUT_DIR = Path("./data/risk_metrics/date=2026-05-10")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_TIME = datetime(2026, 5, 10, 5, 10, 0, tzinfo=timezone.utc)

SYMBOLS = [
    ("AAPL", 172.50, 0.0078),
    ("MSFT", 415.00, 0.0126),
    ("NVDA", 820.00, 0.0538),
    ("GOOGL",170.00, 0.0079),
    ("META", 490.00, 0.0159),
    ("TSLA", 195.00, 0.0135),
    ("SPY",  510.00, 0.0119),
    ("QQQ",  440.00, 0.0115),
]

rows = []
for window_idx in range(3):
    w_start = BASE_TIME + timedelta(minutes=5 * window_idx)
    w_end   = w_start + timedelta(minutes=5)
    for sym, base_price, vol in SYMBOLS:
        import random, math
        price = base_price * (1 + random.uniform(-vol, vol))
        rows.append({
            "symbol":       sym,
            "window_start": w_start.isoformat(),
            "window_end":   w_end.isoformat(),
            "vwap":         round(price, 4),
            "min_price":    round(price * 0.9995, 4),
            "max_price":    round(price * 1.0005, 4),
            "volatility":   vol,
            "price_range":  round(price * 0.001, 4),
            "trade_count":  random.randint(250, 400),
            "total_volume": round(random.uniform(60000, 90000), 2),
            "date":         "2026-05-10",
        })

df    = pd.DataFrame(rows)
table = pa.Table.from_pandas(df)
out   = OUTPUT_DIR / "data.parquet"
pq.write_table(table, str(out))

print(f"✅ Generated {len(rows)} rows → {out}")
