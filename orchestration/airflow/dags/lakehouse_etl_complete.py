"""
Lakehouse ETL DAG - EMR Serverless edition.

Submits Bronze, Silver, and Gold Spark jobs to EMR Serverless via the
AWS StartJobRun API. Each task polls GetJobRun until the job completes.

Environment variables (injected by docker-compose-aws.yml):
  EMR_APPLICATION_ID      EMR Serverless application ID
  EMR_EXECUTION_ROLE_ARN  IAM role assumed by the Spark runtime
  S3_BUCKET               Data lake bucket
  LAKEHOUSE_WHL_S3        s3://bucket/path/lakehouse-latest.whl
  SPARK_CONF_S3           s3://bucket/config/spark-defaults-emr.conf
  AWS_DEFAULT_REGION      eu-west-3
"""

import os
import time
import logging
from datetime import datetime, timedelta

import boto3
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger("airflow.task")

# Read once at DAG parse time
EMR_APP_ID = os.getenv("EMR_APPLICATION_ID", "")
EXECUTION_ROLE = os.getenv("EMR_EXECUTION_ROLE_ARN", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
WHL_PATH = os.getenv("LAKEHOUSE_WHL_S3", "")
SPARK_CONF = os.getenv("SPARK_CONF_S3", "")
REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")

POLL_SECONDS = int(os.getenv("EMR_POLL_SECONDS", "30"))
MAX_WAIT_SECONDS = int(os.getenv("EMR_MAX_WAIT_SECONDS", "3600"))


def submit_emr_job(job_module: str, execution_date: str, **kwargs):
    """
    Submit a PySpark job to EMR Serverless and wait for completion.

    Args:
        job_module: fully qualified module path, e.g.
                    lakehouse.jobs.bronze_ingest_job
        execution_date: YYYY-MM-DD string passed as --execution_date
    """
    client = boto3.client("emr-serverless", region_name=REGION)

    # The entrypoint script is a thin wrapper that imports and runs the job.
    # It is embedded directly so we do not need a separate file on S3.
    entry_point = f"s3://{S3_BUCKET}/artifacts/run_job.py"

    spark_submit = {
        "entryPoint": entry_point,
        "entryPointArguments": [
            "--job-module", job_module,
            "--execution-date", execution_date,
        ],
        "sparkSubmitParameters": (
            f"--py-files {WHL_PATH}"
        ),
    }

    if SPARK_CONF:
        spark_submit["sparkSubmitParameters"] += (
            f" --properties-file {SPARK_CONF}"
        )

    logger.info(
        "Submitting EMR Serverless job: app=%s module=%s date=%s",
        EMR_APP_ID, job_module, execution_date,
    )

    response = client.start_job_run(
        applicationId=EMR_APP_ID,
        executionRoleArn=EXECUTION_ROLE,
        jobDriver={"sparkSubmit": spark_submit},
        configurationOverrides={
            "monitoringConfiguration": {
                "s3MonitoringConfiguration": {
                    "logUri": f"s3://{S3_BUCKET}/logs/emr-serverless/"
                }
            }
        },
        tags={"job_module": job_module, "execution_date": execution_date},
    )

    job_run_id = response["jobRunId"]
    logger.info("Job submitted: job_run_id=%s", job_run_id)

    # Poll until terminal state
    elapsed = 0
    while elapsed < MAX_WAIT_SECONDS:
        status = client.get_job_run(
            applicationId=EMR_APP_ID, jobRunId=job_run_id
        )
        state = status["jobRun"]["state"]
        logger.info("Job %s state: %s (elapsed %ds)", job_run_id, state, elapsed)

        if state in ("SUCCESS",):
            logger.info("Job %s completed successfully", job_run_id)
            return job_run_id
        if state in ("FAILED", "CANCELLED"):
            detail = status["jobRun"].get("stateDetails", "no details")
            raise RuntimeError(
                f"EMR job {job_run_id} ended with state {state}: {detail}"
            )

        time.sleep(POLL_SECONDS)
        elapsed += POLL_SECONDS

    raise TimeoutError(
        f"EMR job {job_run_id} did not finish within {MAX_WAIT_SECONDS}s"
    )


# DAG definition

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="lakehouse_etl_complete",
    description="Bronze - Silver - Gold ETL pipeline on EMR Serverless",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "etl", "emr-serverless"],
) as dag:

    bronze = PythonOperator(
        task_id="bronze_ingest",
        python_callable=submit_emr_job,
        op_kwargs={
            "job_module": "lakehouse.jobs.bronze_ingest_job",
            "execution_date": "{{ ds }}",
        },
    )

    silver = PythonOperator(
        task_id="silver_transform",
        python_callable=submit_emr_job,
        op_kwargs={
            "job_module": "lakehouse.jobs.silver_transform_job",
            "execution_date": "{{ ds }}",
        },
    )

    gold = PythonOperator(
        task_id="gold_transform",
        python_callable=submit_emr_job,
        op_kwargs={
            "job_module": "lakehouse.jobs.gold_transform_job",
            "execution_date": "{{ ds }}",
        },
    )

    bronze >> silver >> gold
