# Apache Airflow 2.7.3 Runtime Image  
# Includes AWS and database providers

FROM apache/airflow:2.7.3

# Set environment
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags
ENV AIRFLOW__CORE__PLUGINS_FOLDER=$AIRFLOW_HOME/plugins

# Use Airflow's official method for adding Python packages
ENV _PIP_ADDITIONAL_REQUIREMENTS="apache-airflow-providers-amazon apache-airflow-providers-postgres apache-airflow-providers-celery boto3 requests pyyaml"

# Switch to root for system packages
USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        postgresql-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p $AIRFLOW_HOME/dags $AIRFLOW_HOME/plugins $AIRFLOW_HOME/logs && \
    chown -R airflow:airflow $AIRFLOW_HOME

# Copy entrypoint if it exists, without failing
COPY --chown=airflow:airflow docker/airflow/entrypoint.sh /entrypoint.sh || true
RUN chmod +x /entrypoint.sh || true

# Return to airflow user
USER airflow

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["webserver"]
