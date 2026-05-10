#!/bin/bash
# Downloads required Flink connector JARs into ./jars/
# Run once before starting the Flink job: make jars

set -e

FLINK_VERSION="1.17.2"
SCALA_VERSION="2.12"
JAR_DIR="$(dirname "$0")/../jars"
MAVEN="https://repo1.maven.org/maven2"

mkdir -p "$JAR_DIR"

echo "Downloading Flink connector JARs (one-time setup)..."

# Kafka connector
KAFKA_JAR="flink-sql-connector-kafka-${FLINK_VERSION}.jar"
if [ ! -f "$JAR_DIR/$KAFKA_JAR" ]; then
  echo "  → $KAFKA_JAR"
  curl -L --progress-bar \
    "${MAVEN}/org/apache/flink/flink-sql-connector-kafka/${FLINK_VERSION}/${KAFKA_JAR}" \
    -o "$JAR_DIR/$KAFKA_JAR"
else
  echo "  ✓ $KAFKA_JAR (already present)"
fi

# Hadoop S3 filesystem (needed for MinIO s3a:// paths)
S3_JAR="flink-s3-fs-hadoop-${FLINK_VERSION}.jar"
if [ ! -f "$JAR_DIR/$S3_JAR" ]; then
  echo "  → $S3_JAR"
  curl -L --progress-bar \
    "${MAVEN}/org/apache/flink/flink-s3-fs-hadoop/${FLINK_VERSION}/${S3_JAR}" \
    -o "$JAR_DIR/$S3_JAR"
else
  echo "  ✓ $S3_JAR (already present)"
fi

# Parquet format
PARQUET_JAR="flink-parquet-${FLINK_VERSION}.jar"
if [ ! -f "$JAR_DIR/$PARQUET_JAR" ]; then
  echo "  → $PARQUET_JAR"
  curl -L --progress-bar \
    "${MAVEN}/org/apache/flink/flink-parquet/${FLINK_VERSION}/${PARQUET_JAR}" \
    -o "$JAR_DIR/$PARQUET_JAR"
else
  echo "  ✓ $PARQUET_JAR (already present)"
fi

echo ""
echo "✅ JARs ready in $JAR_DIR"
echo "   Run: make flink"
