"""
Complete Lakehouse ETL Pipeline DAG
=====================================

Pipeline: Bronze → Silver → Gold
Execution: Full daily ETL with data quality checks

Environment-agnostic: switch between local Docker Spark cluster and AWS EMR
by changing two environment variables only — no code change required.

  Local Docker:  SPARK_MASTER=spark://spark-master:7077  SPARK_DEPLOY_MODE=client
  AWS EMR:       SPARK_MASTER=yarn                       SPARK_DEPLOY_MODE=cluster

DAG Structure:
├── etl_start                      (Dummy start gate)
├── bronze_ingest                  (Read CSV → Parquet in S3)
│   └── silver_transform           (Consolidate & clean)
│       └── gold_transform         (Aggregate & analytics)
│           └── etl_end            (Dummy end gate)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
import os
import sys

# Make the lakehouse package importable at DAG-parse time so the builder can
# be imported.  The /app/src bind-mount is present in all Airflow containers.
if "/app/src" not in sys.path:
    sys.path.insert(0, "/app/src")

from lakehouse.core.spark_submit_builder import build_spark_submit_command

# ==============================================================================
# Configuration
# ==============================================================================

SPARK_APP_BASE = "/app/src/lakehouse/jobs"
AIRFLOW_PYTHON  = "/home/airflow/.local/bin/python3"

# Task env: process-level variables for the spark-submit subprocess.
# SPARK_MASTER and SPARK_DEPLOY_MODE are read from the container env so the
# builder picks them up at DAG-parse time (and at task execution time).
TASK_ENV = {
    "PYTHONPATH":            "/app/src",
    "PYSPARK_PYTHON":        AIRFLOW_PYTHON,
    "PYSPARK_DRIVER_PYTHON": AIRFLOW_PYTHON,
    "APP_ENV":               os.getenv("APP_ENV", "prod"),
    "CONFIG_DIR":            os.getenv("CONFIG_DIR", "/app/config"),
    "DATA_BASE_PATH":        "/data",
    "SPARK_MASTER":          os.getenv("SPARK_MASTER", "spark://spark-master:7077"),
    "SPARK_DEPLOY_MODE":     os.getenv("SPARK_DEPLOY_MODE", "client"),
    "AWS_ACCESS_KEY_ID":     os.getenv("AWS_ACCESS_KEY_ID", ""),
    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
    "AWS_DEFAULT_REGION":    os.getenv("AWS_DEFAULT_REGION", "eu-west-3"),
}


def _task_command(script_name: str) -> str:
    """Build the bash_command for a BashOperator ETL task."""
    label = script_name.replace("_job.py", "").upper()
    spark_cmd = build_spark_submit_command(
        app_file=f"{SPARK_APP_BASE}/{script_name}",
        extra_args='--execution_date "$EXECUTION_DATE"',
    )
    return f"""
        set -e
        EXECUTION_DATE='{{{{ ds }}}}'

        echo "=========================================="
        echo "[{label}] Started  (date: $EXECUTION_DATE)"
        echo "=========================================="

        {spark_cmd}

        echo "=========================================="
        echo "[{label}] Completed"
        echo "=========================================="
    """


# ==============================================================================
# DAG Definition
# ==============================================================================

dag = DAG(
    "lakehouse_etl_complete",
    description="Complete Lakehouse ETL Pipeline: Bronze → Silver → Gold",
    schedule_interval="0 2 * * *",   # Daily at 2 AM
    start_date=datetime(2026, 1, 1),
    end_date=None,
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

start_task = DummyOperator(task_id="etl_start",  dag=dag)
end_task   = DummyOperator(task_id="etl_end",    dag=dag)

bronze_ingest = BashOperator(
    task_id="bronze_ingest",
    bash_command=_task_command("bronze_ingest_job.py"),
    dag=dag,
    append_env=True,
    env=TASK_ENV,
)

silver_transform = BashOperator(
    task_id="silver_transform",
    bash_command=_task_command("silver_transform_job.py"),
    dag=dag,
    append_env=True,
    env=TASK_ENV,
)

gold_transform = BashOperator(
    task_id="gold_transform",
    bash_command=_task_command("gold_transform_job.py"),
    dag=dag,
    append_env=True,
    env=TASK_ENV,
)

# ==============================================================================
# Task Dependencies
# ==============================================================================

start_task >> bronze_ingest >> silver_transform >> gold_transform >> end_task

if __name__ == "__main__":
    dag.cli()
