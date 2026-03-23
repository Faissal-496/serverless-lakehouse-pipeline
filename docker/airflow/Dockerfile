# Apache Airflow 2.7.3 Runtime Image
# Includes Spark integration for distributed task execution

FROM apache/airflow:2.7.3

# Set environment
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags
ENV AIRFLOW__CORE__PLUGINS_FOLDER=$AIRFLOW_HOME/plugins
ENV PATH=$AIRFLOW_HOME/bin:$PATH

WORKDIR $AIRFLOW_HOME

# System dependencies
USER root

RUN apt-get update && \
    apt-get install -y \
        build-essential \
        curl \
        git \
        postgresql-client \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/

# Create Airflow directories
RUN mkdir -p \
    $AIRFLOW_HOME/dags \
    $AIRFLOW_HOME/plugins \
    $AIRFLOW_HOME/logs

# Install Python dependencies (Airflow base image already includes Airflow)
# Use Airflow constraints for compatibility
ARG AIRFLOW_VERSION=2.7.3
ARG PYTHON_VERSION=3.11
ARG AIRFLOW_CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

COPY requirements/runtime.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --constraint "${AIRFLOW_CONSTRAINT_URL}" -r /tmp/requirements.txt \
    apache-airflow-providers-amazon \
    apache-airflow-providers-postgres \
    apache-airflow-providers-celery

# Airflow entrypoint
COPY docker/airflow/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set permissions
RUN chown -R airflow:airflow $AIRFLOW_HOME

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

USER airflow

ENTRYPOINT ["/entrypoint.sh"]
CMD ["webserver"]
