# ── Stage 0: Docker CLI binary ────────────────────────────────────────────────
# Copy only the docker binary from the official Docker image.
# Avoids apt repository configuration entirely — works regardless of Debian release.
FROM docker:27-cli AS docker-cli


# ── Stage 1: Python 3.11 runtime ──────────────────────────────────────────────
# python:3.11-slim-bookworm builds Python with --enable-shared against Debian
# bookworm (glibc 2.36). Debian trixie ships glibc 2.41, which is ABI-
# backward-compatible → binary and shared library run without issue on trixie.
FROM python:3.11-slim-bookworm AS python311


# ── Stage 2: Jenkins CI Agent (Debian trixie + JDK17) ─────────────────────────
FROM jenkins/agent:latest-jdk17

LABEL version="2.1.0" \
      description="Lakehouse Jenkins Agent — Spark 3.5.0 + Python 3.11 + full CI toolchain" \
      maintainer="lakehouse-team"

USER root

# PySpark 3.5.0 supports Python 3.8–3.11 only (not 3.12/3.13).
# SPARK_HOME makes pyspark use the full Spark binary (with S3A JARs) at runtime.
ENV SPARK_HOME=/opt/spark \
    PYSPARK_PYTHON=/usr/local/bin/python3.11 \
    PYSPARK_DRIVER_PYTHON=/usr/local/bin/python3.11

ENV PATH="${SPARK_HOME}/bin:${PATH}"

# ── 1. Docker CLI (multi-stage — no apt repo setup required) ──────────────────
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

# ── 2. Python 3.11 runtime (multi-stage — from official Python Docker image) ──
# Copy the binary, shared library, and standard library from the python311 stage.
# pip is bootstrapped via ensurepip (bundled wheels shipped in the stdlib).
COPY --from=python311 /usr/local/bin/python3.11           /usr/local/bin/python3.11
COPY --from=python311 /usr/local/lib/python3.11           /usr/local/lib/python3.11
COPY --from=python311 /usr/local/lib/libpython3.11.so.1.0 /usr/local/lib/libpython3.11.so.1.0

# ── 3. System packages + Python 3.11 shared library runtime dependencies ──────
# These packages exist in Debian trixie (same names, newer versions).
# libssl3, libffi8, zlib1g, libexpat1 satisfy all Python 3.11 .so dependencies.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl wget git procps \
        libssl3 libffi8 zlib1g libexpat1 libbz2-1.0 liblzma5 && \
    echo "/usr/local/lib" > /etc/ld.so.conf.d/python311.conf && \
    ldconfig && \
    ln -sf /usr/local/bin/python3.11 /usr/local/bin/python3 && \
    ln -sf /usr/local/bin/python3.11 /usr/local/bin/python && \
    python3.11 -m ensurepip --upgrade && \
    python3.11 -m pip install --upgrade pip --quiet && \
    python3.11 --version && pip3 --version && \
    rm -rf /var/lib/apt/lists/*

# ── 4. Apache Spark 3.5.0 + S3A connectors ────────────────────────────────────
RUN cd /opt && \
    wget -q https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz && \
    tar -xzf spark-3.5.0-bin-hadoop3.tgz && \
    rm spark-3.5.0-bin-hadoop3.tgz && \
    ln -s spark-3.5.0-bin-hadoop3 spark && \
    chmod -R 755 /opt/spark && \
    wget -q -O /opt/spark/jars/hadoop-aws-3.3.4.jar \
        https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    wget -q -O /opt/spark/jars/aws-java-sdk-bundle-1.12.565.jar \
        https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.565/aws-java-sdk-bundle-1.12.565.jar && \
    chmod 644 /opt/spark/jars/hadoop-aws-3.3.4.jar \
              /opt/spark/jars/aws-java-sdk-bundle-1.12.565.jar

# ── 5. Python toolchain (CI linters + PySpark + runtime deps) ─────────────────
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
