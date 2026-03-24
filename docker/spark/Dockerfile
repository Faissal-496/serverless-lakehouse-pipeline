# ============================================================================
# LAKEHOUSE AWS - PRODUCTION SPARK IMAGE
# Spark 3.5.0 + S3A + Python ETL Pipeline
# ============================================================================

FROM apache/spark:3.5.0 AS base

LABEL maintainer="Lakehouse Engineering" \
      version="1.0.0" \
      description="Lakehouse AWS Production - Spark 3.5.0 with S3A"

USER root

# ============================================================================
# ENVIRONMENT & PATHS
# ============================================================================
ENV SPARK_HOME=/opt/spark \
    HOME=/home/spark \
    PATH=$SPARK_HOME/bin:/home/spark/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/lakehouse

# ============================================================================
# DEPENDENCIES & PYTHON PACKAGES (minimal - skip heavy deps)
# ============================================================================
RUN pip install --upgrade pip setuptools && \
    pip install --no-cache-dir \
        boto3 \
        pandas \
        numpy \
        requests \
        pyyaml \
        python-dotenv

# ============================================================================
# S3A CONNECTORS & CONFIGURATION
# ============================================================================
RUN mkdir -p /opt/spark/conf /home/spark/.ivy2/{cache,jars} && \
    chown -R spark:spark /home/spark /opt/spark/conf /opt/spark/jars && \
    chmod -R 755 /opt/spark/jars

# Spark configuration for S3A
RUN printf '%s\n' \
    'spark.hadoop.fs.s3a.impl org.apache.hadoop.fs.s3a.S3AFileSystem' \
    'spark.hadoop.fs.s3a.aws.credentials.provider com.amazonaws.auth.DefaultAWSCredentialsProviderChain' \
    'spark.sql.shuffle.partitions 200' \
    'spark.sql.adaptive.enabled true' \
    'spark.sql.adaptive.coalescePartitions.enabled true' \
    'spark.serializer org.apache.spark.serializer.KryoSerializer' \
    > /opt/spark/conf/spark-defaults.conf && \
    chmod 644 /opt/spark/conf/spark-defaults.conf

# ============================================================================
# HEALTH CHECK
# ============================================================================
COPY docker/healthcheck.py /opt/lakehouse/healthcheck.py
RUN chmod +x /opt/lakehouse/healthcheck.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 /opt/lakehouse/healthcheck.py || exit 1

# ============================================================================
# RUNTIME USER
# ============================================================================
USER spark
CMD ["tail", "-f", "/dev/null"]
