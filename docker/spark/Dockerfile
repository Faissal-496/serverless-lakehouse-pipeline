# ============================================================================
# LAKEHOUSE AWS - PRODUCTION SPARK IMAGE
# Spark 3.5.0 + S3A + Python ETL Pipeline
# ============================================================================

FROM apache/spark:3.5.0 AS base

LABEL maintainer="Lakehouse Engineering" \
      version="1.0.0" \
      description="Lakehouse AWS Production - Spark 3.5.0 with S3A" \
      org.opencontainers.image.source="https://github.com/yourorg/lakehouse-aws"

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
# DEPENDENCIES & PYTHON PACKAGES
# ============================================================================
COPY requirements/runtime.txt /tmp/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools && \
    pip install -r /tmp/requirements.txt

# ============================================================================
# S3A CONNECTORS & CONFIGURATION
# ============================================================================
RUN mkdir -p /opt/spark/conf /home/spark/.ivy2/{cache,jars} && \
    curl -fsSL -o /opt/spark/jars/hadoop-aws-3.3.4.jar \
        https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -fsSL -o /opt/spark/jars/aws-java-sdk-bundle-1.12.262.jar \
        https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    chown -R spark:spark /home/spark /opt/spark/conf /opt/spark/jars && \
    chmod -R 755 /opt/spark/jars && \
    chmod 644 /opt/spark/jars/*

# Spark configuration
RUN printf '%s\n' \
    'spark.jars.packages com.crealytics:spark-excel_2.12:3.5.1_0.20.4' \
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
