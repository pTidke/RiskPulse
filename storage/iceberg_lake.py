"""
storage/iceberg_lake.py

Apache Iceberg mirror of the RiskPulse risk-metrics lake.

Maintains an Iceberg table (local SQLite catalog + MinIO/S3 warehouse) alongside
the Parquet lake, so the same 5-minute risk-metric windows can be queried as a
versioned lakehouse table — and benchmarked head-to-head against raw Parquet.

Design: decoupled from the Faust hot path. The stream keeps writing Parquet;
this loader refreshes the Iceberg table in batch. Appending to Iceberg per
5-minute window would create a new snapshot + tiny data file each time (the
small-file / metadata-bloat problem) and drag PyIceberg + S3 into the streaming
path — a batch refresh keeps both layers simple and reliable.

Run:  python storage/iceberg_lake.py     # refresh the Iceberg table
      make iceberg
"""

import glob
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

ROOT         = Path(__file__).resolve().parents[1]
PARQUET_GLOB = (ROOT / "data" / "risk_metrics" / "**" / "*.parquet").as_posix()

NAMESPACE = os.getenv("ICEBERG_NAMESPACE", "riskpulse")
TABLE     = os.getenv("ICEBERG_TABLE", "risk_metrics")
IDENT     = f"{NAMESPACE}.{TABLE}"

WAREHOUSE   = os.getenv("ICEBERG_WAREHOUSE", "s3://riskpulse-iceberg")
CATALOG_URI = os.getenv("ICEBERG_CATALOG_URI", f"sqlite:///{ROOT}/data/iceberg/catalog.db")

def _split_endpoint(raw: str) -> tuple:
    """(host:port, url, secure) from an endpoint that may carry a scheme.

    .env ships MINIO_ENDPOINT as http://...; boto3 / PyIceberg want a URL while
    DuckDB's s3_endpoint wants a bare host:port. Normalizing here avoids the
    `http://http://...` class of bug.
    """
    secure = raw.startswith("https://")
    host   = raw.split("://", 1)[-1].rstrip("/")
    return host, f"{'https' if secure else 'http'}://{host}", secure


MINIO_HOST, MINIO_URL, MINIO_SECURE = _split_endpoint(
    os.getenv("MINIO_ENDPOINT", "localhost:9000")
)
MINIO_KEY    = os.getenv("MINIO_ACCESS_KEY", os.getenv("MINIO_USER", "minioadmin"))
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", os.getenv("MINIO_PASSWORD", "minioadmin"))
MINIO_REGION = os.getenv("MINIO_REGION", "us-east-1")

_IS_S3 = WAREHOUSE.startswith("s3://")


def _s3_props() -> dict:
    return {
        "s3.endpoint":          MINIO_URL,
        "s3.access-key-id":     MINIO_KEY,
        "s3.secret-access-key": MINIO_SECRET,
        "s3.path-style-access": "true",   # required for MinIO
        "s3.region":            MINIO_REGION,
    }


def _ensure_bucket() -> None:
    """Create the warehouse bucket on MinIO if it does not exist."""
    if not _IS_S3:
        return
    import boto3
    bucket = WAREHOUSE.replace("s3://", "").split("/")[0]
    s3 = boto3.client(
        "s3", endpoint_url=MINIO_URL,
        aws_access_key_id=MINIO_KEY, aws_secret_access_key=MINIO_SECRET,
        region_name=MINIO_REGION,
    )
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if bucket not in existing:
        s3.create_bucket(Bucket=bucket)
        logger.info(f"Created MinIO bucket: {bucket}")


def get_catalog():
    """SQLite-backed Iceberg catalog pointed at the MinIO/S3 warehouse."""
    from pyiceberg.catalog.sql import SqlCatalog
    # ensure the local catalog directory exists
    local = CATALOG_URI.replace("sqlite:///", "")
    Path(local).parent.mkdir(parents=True, exist_ok=True)
    props = {"uri": CATALOG_URI, "warehouse": WAREHOUSE}
    if _IS_S3:
        props.update(_s3_props())
    return SqlCatalog("riskpulse", **props)


def load_parquet_lake() -> dict:
    """Full-refresh the Iceberg table from the current Parquet lake."""
    files = sorted(glob.glob(PARQUET_GLOB, recursive=True))
    if not files:
        raise FileNotFoundError(
            f"No Parquet at {PARQUET_GLOB} — run the stream first (make simulate && make stream)."
        )
    table = pa.concat_tables([pq.read_table(f) for f in files]).combine_chunks()

    _ensure_bucket()
    cat = get_catalog()
    try:
        cat.create_namespace(NAMESPACE)
    except Exception:
        pass
    # full refresh so the mirror always matches the lake (no append-on-rerun dupes)
    try:
        cat.drop_table(IDENT)
    except Exception:
        pass

    ice = cat.create_table(IDENT, schema=table.schema)
    ice.append(table)
    logger.info(f"Iceberg '{IDENT}': {table.num_rows} rows from {len(files)} Parquet files")
    return {
        "rows": table.num_rows,
        "files": len(files),
        "metadata_location": ice.metadata_location,
    }


def current_metadata_location() -> str:
    """Path to the current Iceberg metadata snapshot (for iceberg_scan)."""
    return get_catalog().load_table(IDENT).metadata_location


def configure_duckdb(con) -> None:
    """Prepare a DuckDB connection to read the Iceberg table from MinIO/S3."""
    for ext in ("httpfs", "iceberg"):
        con.execute(f"INSTALL {ext}")
        con.execute(f"LOAD {ext}")
    if _IS_S3:
        con.execute(f"SET s3_endpoint='{MINIO_HOST}'")
        con.execute(f"SET s3_access_key_id='{MINIO_KEY}'")
        con.execute(f"SET s3_secret_access_key='{MINIO_SECRET}'")
        con.execute(f"SET s3_use_ssl={'true' if MINIO_SECURE else 'false'}")
        con.execute("SET s3_url_style='path'")
        con.execute(f"SET s3_region='{MINIO_REGION}'")


def scan_expr() -> str:
    """DuckDB FROM-clause expression for the current Iceberg snapshot."""
    return f"iceberg_scan('{current_metadata_location()}')"


if __name__ == "__main__":
    info = load_parquet_lake()
    print(
        f"\n✅ Iceberg table '{IDENT}' refreshed — {info['rows']} rows "
        f"from {info['files']} Parquet files"
        f"\n   warehouse: {WAREHOUSE}"
        f"\n   snapshot:  {info['metadata_location']}\n"
    )
