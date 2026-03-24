# ============================================================================
# LAKEHOUSE AWS - PRODUCTION SPARK IMAGE
# Spark 3.5.0 + S3A + Python ETL Pipeline
# ============================================================================

FROM apache/spark:3.5.0

LABEL maintainer="Lakehouse Engineering" \
      version="1.0.0" \
      description="Lakehouse AWS Production - Spark 3.5.0 with S3A"

USER root

# ============================================================================
# BASIC DEPENDENCIES ONLY (skip pip to avoid Python version conflicts)
# ============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ============================================================================
# S3A CONFIGURATION (Spark handles boto3 internally)
# ============================================================================

# Spark configuration for S3A
RUN mkdir -p /opt/spark/conf && \
    printf '%s\n' \
    'spark.hadoop.fs.s3a.impl org.apache.hadoop.fs.s3a.S3AFileSystem' \
    'spark.hadoop.fs.s3a.aws.credentials.provider com.amazonaws.auth.DefaultAWSCredentialsProviderChain' \
    'spark.sql.shuffle.partitions 200' \
    'spark.sql.adaptive.enabled true' \
    'spark.sql.adaptive.coalescePartitions.enabled true' \
    'spark.serializer org.apache.spark.serializer.KryoSerializer' \
    > /opt/spark/conf/spark-defaults.conf && \
    chmod 644 /opt/spark/conf/spark-defaults.conf

# Set Spark home
ENV SPARK_HOME=/opt/spark \
    PATH=$SPARK_HOME/bin:$PATH

WORKDIR /opt/lakehouse

USER spark

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "org.apache.spark.deploy.SparkSubmit" > /dev/null || exit 1

# Default command
CMD ["spark-shell"]
