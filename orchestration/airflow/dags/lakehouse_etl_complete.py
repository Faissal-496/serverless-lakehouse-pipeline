"""
Complete Lakehouse ETL Pipeline DAG
=====================================
Pipeline: Bronze -> Silver -> Gold
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
import os

# ==============================================================================
# Configuration — single source of truth
# ==============================================================================

SPARK_MASTER = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
AIRFLOW_PYTHON = "/home/airflow/.local/bin/python3"
S3_BUCKET = os.getenv("S3_BUCKET", "lakehouse-assurance-moto-prod")
APP_ENV = os.getenv("APP_ENV", "prod")

# Select config file based on environment
SPARK_CONF_FILE = os.getenv("SPARK_PROPERTIES_FILE", "/app/config/spark/spark-defaults-local.conf")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")

# Only env vars that MUST be forwarded to driver/executor JVMs
SPARK_ENV_CONF = [
    "spark.driverEnv.PYTHONPATH=/app/src",
    f"spark.driverEnv.PYSPARK_PYTHON={AIRFLOW_PYTHON}",
    f"spark.driverEnv.PYSPARK_DRIVER_PYTHON={AIRFLOW_PYTHON}",
    f"spark.driverEnv.APP_ENV={APP_ENV}",
    "spark.driverEnv.CONFIG_DIR=/app/config",
    "spark.driverEnv.DATA_BASE_PATH=/data",
    f"spark.driverEnv.S3_BUCKET={S3_BUCKET}",
    f"spark.driverEnv.AWS_ACCESS_KEY_ID={AWS_ACCESS_KEY_ID}",
    f"spark.driverEnv.AWS_SECRET_ACCESS_KEY={AWS_SECRET_ACCESS_KEY}",
    f"spark.driverEnv.AWS_DEFAULT_REGION={AWS_DEFAULT_REGION}",
    "spark.executorEnv.PYTHONPATH=/app/src",
    "spark.executorEnv.PYSPARK_PYTHON=/usr/bin/python3",
    f"spark.executorEnv.APP_ENV={APP_ENV}",
    "spark.executorEnv.CONFIG_DIR=/app/config",
    "spark.executorEnv.DATA_BASE_PATH=/data",
    f"spark.executorEnv.S3_BUCKET={S3_BUCKET}",
    f"spark.executorEnv.AWS_ACCESS_KEY_ID={AWS_ACCESS_KEY_ID}",
    f"spark.executorEnv.AWS_SECRET_ACCESS_KEY={AWS_SECRET_ACCESS_KEY}",
    f"spark.executorEnv.AWS_DEFAULT_REGION={AWS_DEFAULT_REGION}",
]

_ENV_CONF = " ".join([f"--conf {c}" for c in SPARK_ENV_CONF])

TASK_ENV = {
    "PYTHONPATH": "/app/src",
    "PYSPARK_PYTHON": AIRFLOW_PYTHON,
    "PYSPARK_DRIVER_PYTHON": AIRFLOW_PYTHON,
    "APP_ENV": APP_ENV,
    "CONFIG_DIR": "/app/config",
    "DATA_BASE_PATH": "/data",
    "S3_BUCKET": S3_BUCKET,
    "SPARK_MASTER": SPARK_MASTER,
}


def _spark_submit_cmd(job_script: str) -> str:
    return f"""
        set -e
        EXECUTION_DATE='{{{{ ds }}}}'

        spark-submit \
            --master {SPARK_MASTER} \
            --deploy-mode client \
            --properties-file {SPARK_CONF_FILE} \
            {_ENV_CONF} \
            {job_script} \
            --execution_date "$EXECUTION_DATE"
    """


# ==============================================================================
# DAG
# ==============================================================================

dag = DAG(
    "lakehouse_etl_complete",
    description="Complete Lakehouse ETL Pipeline: Bronze -> Silver -> Gold",
    schedule_interval="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "etl", "production"],
    default_args={
        "owner": "lakehouse-team",
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
        "execution_timeout": timedelta(hours=2),
    },
)

start_task = EmptyOperator(task_id="etl_start", dag=dag)

bronze_ingest = BashOperator(
    task_id="bronze_ingest",
    bash_command=_spark_submit_cmd("/app/src/lakehouse/jobs/bronze_ingest_job.py"),
    dag=dag,
    append_env=True,
    env=TASK_ENV,
)

silver_transform = BashOperator(
    task_id="silver_transform",
    bash_command=_spark_submit_cmd("/app/src/lakehouse/jobs/silver_transform_job.py"),
    dag=dag,
    append_env=True,
    env=TASK_ENV,
)

gold_transform = BashOperator(
    task_id="gold_transform",
    bash_command=_spark_submit_cmd("/app/src/lakehouse/jobs/gold_transform_job.py"),
    dag=dag,
    append_env=True,
    env=TASK_ENV,
)

end_task = EmptyOperator(task_id="etl_end", dag=dag)

start_task >> bronze_ingest >> silver_transform >> gold_transform >> end_task

if __name__ == "__main__":
    dag.cli()
