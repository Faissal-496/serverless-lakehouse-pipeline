# Apache Airflow 2.9.0 with Spark Client
FROM apache/airflow:2.9.0

# Set environment
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags
ENV SPARK_HOME=/opt/spark
ENV PATH=$SPARK_HOME/bin:$PATH

# Use Airflow's official method for adding Python packages (must be before USER change)
# NOTE: pyspark NOT needed here - Spark installation includes PySpark
# Airflow only needs spark-submit client to trigger jobs on cluster
# CRITICAL: pyyaml MUST be installed explicitly for lakehouse config loading
ENV _PIP_ADDITIONAL_REQUIREMENTS="pyyaml==6.0.1 pandas==2.0.3 pyarrow==12.0.1 python-json-logger==2.0.7 tenacity==8.2.3 python-dotenv==1.0.0 requests==2.31.0 boto3==1.28.85"

USER root

# Install dependencies (Java, wget)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        default-jre-headless \
        default-jdk-headless \
        wget \
        netcat-traditional && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Spark Client (only for spark-submit binary)
RUN cd /opt && \
    wget -q https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz && \
    tar -xzf spark-3.5.0-bin-hadoop3.tgz && \
    rm spark-3.5.0-bin-hadoop3.tgz && \
    ln -s spark-3.5.0-bin-hadoop3 spark && \
    chmod -R 755 /opt/spark
# resoudre le probleme /opt/spark/bin/load-spark-env.sh: line 68: ps: command not found
RUN apt-get update && apt-get install -y procps

# Explicitly install Python requirements using pip (explicit version pinning)
# This ensures pyyaml and other critical packages are installed correctly
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        pyyaml==6.0.1 \
        pandas==2.0.3 \
        pyarrow==12.0.1 \
        python-json-logger==2.0.7 \
        tenacity==8.2.3 \
        python-dotenv==1.0.0 \
        requests==2.31.0 \
        boto3==1.28.85

# Create startup configuration directory
RUN mkdir -p /opt/airflow/startup

# Create a startup script that configures environment variables
RUN printf '#!/bin/bash\n' > /opt/airflow/startup/configure-env.sh && \
    printf 'export PYTHONPATH="/app/src:${PYTHONPATH:-}"\n' >> /opt/airflow/startup/configure-env.sh && \
    printf 'export APP_ENV="${APP_ENV:-dev}"\n' >> /opt/airflow/startup/configure-env.sh && \
    printf 'export CONFIG_DIR="${CONFIG_DIR:-/app/config}"\n' >> /opt/airflow/startup/configure-env.sh && \
    printf 'export DATA_BASE_PATH="${DATA_BASE_PATH:-/data}"\n' >> /opt/airflow/startup/configure-env.sh && \
    chmod +x /opt/airflow/startup/configure-env.sh

USER airflow

# Add startup script to bashrc
RUN echo 'source /opt/airflow/startup/configure-env.sh' >> ~/.bashrc
