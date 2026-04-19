# Apache Airflow 2.9.0 with Spark Client
FROM apache/airflow:2.9.0

# Set environment
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags
ENV SPARK_HOME=/opt/spark
ENV PATH=$SPARK_HOME/bin:$PATH

# Packages installed via Airflow's recommended mechanism (startup-time install).
# Only include packages not already provided by Airflow 2.9.0 deps.
ENV _PIP_ADDITIONAL_REQUIREMENTS="pyyaml==6.0.1 python-json-logger==2.0.7 tenacity==8.2.3 python-dotenv==1.0.0 apache-airflow-providers-amazon>=8.19.0"

USER root

# System dependencies: Java for the driver JVM, procps for spark-submit ps check
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        default-jre-headless \
        default-jdk-headless \
        wget \
        netcat-traditional \
        procps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Spark client (spark-submit binary only - not a cluster node).
# Pre-bake S3A JARs in the same RUN layer as the Spark install.
# In --deploy-mode client the driver JVM runs on this container; it needs
# hadoop-aws and aws-java-sdk on its classpath to resolve s3a:// URIs.
# Same JAR versions as the Spark worker image to avoid classpath conflicts.
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

# Startup environment script used by bash sessions
RUN mkdir -p /opt/airflow/startup && \
    printf '#!/bin/bash\n' > /opt/airflow/startup/configure-env.sh && \
    printf 'export PYTHONPATH="/app/src:${PYTHONPATH:-}"\n' >> /opt/airflow/startup/configure-env.sh && \
    printf 'export APP_ENV="${APP_ENV:-dev}"\n' >> /opt/airflow/startup/configure-env.sh && \
    printf 'export CONFIG_DIR="${CONFIG_DIR:-/app/config}"\n' >> /opt/airflow/startup/configure-env.sh && \
    printf 'export DATA_BASE_PATH="${DATA_BASE_PATH:-/data}"\n' >> /opt/airflow/startup/configure-env.sh && \
    chmod +x /opt/airflow/startup/configure-env.sh

USER airflow

RUN echo 'source /opt/airflow/startup/configure-env.sh' >> ~/.bashrc

# ============================================================================
# Install lakehouse Python package
# ============================================================================
COPY --chown=airflow:0 pyproject.toml setup.cfg /opt/lakehouse-pkg/
COPY --chown=airflow:0 src/ /opt/lakehouse-pkg/src/
RUN pip install --no-cache-dir -e /opt/lakehouse-pkg
