# ============================================================================
# LAKEHOUSE AWS - PRODUCTION SPARK IMAGE
# Spark 3.5.0 + S3A + Python ETL Pipeline
# ============================================================================

FROM apache/spark:3.5.0

LABEL maintainer="Lakehouse Engineering" \
      version="2.0.0" \
      description="Lakehouse AWS Production - Spark 3.5.0 with S3A + PySpark ETL"

USER root

ENV SPARK_HOME=/opt/spark
ENV HOME=/home/spark
ENV PATH=$SPARK_HOME/bin:/home/spark/.local/bin:$PATH

WORKDIR /opt/lakehouse

# ============================================================================
# System Dependencies + Python
# ============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        curl \
        git \
        wget && \
    python3 -m pip install --upgrade setuptools wheel && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ============================================================================
# Python Dependencies (from requirements/runtime.txt)  
# Install ALL dependencies that might be imported by ETL scripts
# ============================================================================
RUN python3 -m pip install --no-cache-dir --no-deps \
    pyspark==3.5.0 \
    boto3==1.28.85 \
    s3fs==2023.12.1 \
    python-dotenv==1.0.0 \
    pyyaml==6.0.1 \
    requests==2.31.0 \
    tenacity==8.2.3 \
    python-json-logger==2.0.7

# ============================================================================
# S3A CONNECTORS - Download JAR files
# ============================================================================
RUN mkdir -p $SPARK_HOME/jars && \
    curl -fSL -o $SPARK_HOME/jars/hadoop-aws-3.3.4.jar \
        https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -fSL -o $SPARK_HOME/jars/aws-java-sdk-bundle-1.12.262.jar \
        https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    chmod 755 $SPARK_HOME/jars/*.jar

# ============================================================================
# Spark Configuration for S3A + Data Processing
# ============================================================================
RUN mkdir -p $SPARK_HOME/conf && \
    printf '%s\n' \
    'spark.hadoop.fs.s3a.impl org.apache.hadoop.fs.s3a.S3AFileSystem' \
    'spark.hadoop.fs.s3a.aws.credentials.provider com.amazonaws.auth.DefaultAWSCredentialsProviderChain' \
    'spark.sql.shuffle.partitions 200' \
    'spark.sql.adaptive.enabled true' \
    'spark.sql.adaptive.coalescePartitions.enabled true' \
    'spark.serializer org.apache.spark.serializer.KryoSerializer' \
    'spark.driver.memory 2g' \
    'spark.executor.memory 2g' \
    'spark.sql.parquet.compression.codec snappy' \
    > $SPARK_HOME/conf/spark-defaults.conf && \
    chmod 644 $SPARK_HOME/conf/spark-defaults.conf

# ============================================================================
# Setup Spark user and permissions
# ============================================================================
RUN mkdir -p /home/spark/.ivy2/cache \
             /home/spark/.ivy2/jars \
             /opt/lakehouse/data \
             /opt/lakehouse/logs && \
    chown -R spark:spark /home/spark /opt/lakehouse && \
    chmod -R 755 $SPARK_HOME/jars

# ============================================================================
# Runtime Configuration
# ============================================================================
USER spark

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "spark" > /dev/null || exit 1

CMD ["sleep", "infinity"]

# Default command
CMD ["spark-shell"]
