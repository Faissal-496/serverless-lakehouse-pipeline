FROM jenkins/agent:latest-jdk17

LABEL version="2.0.0" \
      description="Lakehouse Jenkins Agent — Spark 3.5.0 + Python 3.11 + full CI toolchain" \
      maintainer="lakehouse-team"

USER root

# ── Environment ──────────────────────────────────────────────────────────────
# PySpark 3.5.0 supports Python 3.8–3.11 only (not 3.12/3.13).
# SPARK_HOME points to the full Spark binary so pyspark uses its JARs at runtime.
ENV SPARK_HOME=/opt/spark \
    PYSPARK_PYTHON=/usr/bin/python3.11 \
    PYSPARK_DRIVER_PYTHON=/usr/bin/python3.11

ENV PATH="${SPARK_HOME}/bin:${PATH}"

# ── 1. System dependencies + Docker CLI ──────────────────────────────────────
# docker.io from Debian main repos: simpler, no external repo setup needed,
# provides docker CLI (login, build, push) fully sufficient for CI.
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release \
        software-properties-common wget procps git \
        docker.io && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ── 2. Python 3.11 (explicit pin — Spark 3.5.0 NOT compatible with Python 3.12/3.13) ─
# Debian bookworm: python3.11 in main repos.
# Ubuntu (≥22.04): available from deadsnakes PPA.
RUN apt-get update -qq && \
    if [ "$(. /etc/os-release && echo $ID)" = "ubuntu" ]; then \
        add-apt-repository -y ppa:deadsnakes/ppa && apt-get update -qq; \
    fi && \
    apt-get install -y --no-install-recommends \
        python3.11 python3.11-dev python3.11-venv && \
    # Bootstrap pip for Python 3.11 explicitly
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 && \
    # Make python3/python point to 3.11 (overrides default 3.12/3.13 in base)
    ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ── 3. Spark 3.5.0 binary + S3A connectors (mirrors docker/airflow/Dockerfile) ─
RUN cd /opt && \
    wget -q https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz && \
    tar -xzf spark-3.5.0-bin-hadoop3.tgz && \
    rm spark-3.5.0-bin-hadoop3.tgz && \
    ln -s spark-3.5.0-bin-hadoop3 spark && \
    chmod -R 755 /opt/spark && \
    # S3A JARs — same versions as Spark cluster (docker/spark/Dockerfile.base)
    wget -q -O /opt/spark/jars/hadoop-aws-3.3.4.jar \
        https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    wget -q -O /opt/spark/jars/aws-java-sdk-bundle-1.12.565.jar \
        https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.565/aws-java-sdk-bundle-1.12.565.jar && \
    chmod 644 /opt/spark/jars/hadoop-aws-3.3.4.jar \
              /opt/spark/jars/aws-java-sdk-bundle-1.12.565.jar

# ── 4. Python CI + PySpark + runtime dependencies ────────────────────────────
# pyspark==3.5.0 provides Python bindings; at runtime SPARK_HOME makes it use
# the /opt/spark binary (with S3A JARs) instead of pip-bundled JARs.
RUN python3.11 -m pip install --no-cache-dir \
    pyspark==3.5.0 \
    autoflake==2.2.1 \
    black==23.12.0 \
    flake8==6.1.0 \
    pytest==7.4.3 \
    pytest-cov==4.1.0 \
    pyyaml==6.0.1 \
    python-dotenv==1.0.0 \
    tenacity==8.2.3 \
    boto3 \
    python-json-logger==2.0.7 \
    pandas \
    pyarrow \
    build \
    setuptools \
    wheel \
    awscli

USER jenkins
