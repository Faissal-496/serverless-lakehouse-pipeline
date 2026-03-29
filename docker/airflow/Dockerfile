# Apache Airflow 2.7.3 Runtime Image  
# Optimized for Spark ETL via spark-submit (not direct PySpark execution)
# Executes Spark jobs via BashOperator + spark-submit to Spark master

FROM apache/airflow:2.7.3

# Set environment
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags
ENV AIRFLOW__CORE__PLUGINS_FOLDER=$AIRFLOW_HOME/plugins
ENV PYTHONPATH=/opt/lakehouse/src:$PYTHONPATH
ENV SPARK_HOME=/opt/spark-3.5.0-bin-hadoop3
ENV PATH=$SPARK_HOME/bin:$PATH

# Use Airflow's official method for adding Python packages  
# Include minimal runtime dependencies
ENV _PIP_ADDITIONAL_REQUIREMENTS="apache-airflow-providers-amazon apache-airflow-providers-postgres apache-airflow-providers-celery pyspark==3.5.0 pandas==2.1.4 pyarrow==14.0.1 boto3==1.28.85 s3fs==2023.12.1 python-dotenv==1.0.0 requests pyyaml python-json-logger==2.0.7"

# Switch to root for system packages
USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        postgresql-client \
        wget \
        openjdk-11-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Spark binaries for spark-submit command
RUN cd /opt && \
    wget -q https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz && \
    tar xzf spark-3.5.0-bin-hadoop3.tgz && \
    rm spark-3.5.0-bin-hadoop3.tgz && \
    chmod -R 755 /opt/spark-3.5.0-bin-hadoop3 && \
    \
    # Download S3A JARs for Hadoop S3 support
    mkdir -p /opt/spark-3.5.0-bin-hadoop3/jars && \
    cd /opt/spark-3.5.0-bin-hadoop3/jars && \
    wget -q https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    wget -q https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    chmod 644 *.jar

# Copy entrypoint script
COPY docker/airflow/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create necessary directories as root
RUN mkdir -p $AIRFLOW_HOME/dags $AIRFLOW_HOME/plugins $AIRFLOW_HOME/logs

# Return to airflow user (will have proper permissions from base image)
USER airflow

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["webserver"]
