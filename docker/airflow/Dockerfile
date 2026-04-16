# Airflow runtime image for AWS production.
# Spark is NOT installed here because all Spark jobs run on EMR Serverless.
# The lakehouse wheel is pre-installed so the DAG can import helper modules.

FROM apache/airflow:2.9.0

ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags

# Extra Python packages that Airflow needs at runtime.
# boto3 is required for the EMR Serverless operator and S3 remote logging.
ENV _PIP_ADDITIONAL_REQUIREMENTS="pyyaml==6.0.1 python-json-logger==2.0.7 tenacity==8.2.3 python-dotenv==1.0.0 boto3>=1.28 apache-airflow-providers-amazon>=8.0"

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create directory where the lakehouse wheel will be copied during CI build.
RUN mkdir -p /opt/lakehouse

USER airflow
