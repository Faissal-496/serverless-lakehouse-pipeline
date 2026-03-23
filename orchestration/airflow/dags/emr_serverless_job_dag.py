"""
Example Airflow DAG to submit Spark jobs to EMR Serverless.
Requires:
  - EMR_SERVERLESS_APPLICATION_ID
  - EMR_SERVERLESS_EXECUTION_ROLE_ARN
  - EMR_SERVERLESS_S3_ENTRYPOINT
"""

from datetime import datetime
import os

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.operators.emr import EmrServerlessStartJobOperator


with DAG(
    dag_id="emr_serverless_spark_job",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["emr-serverless", "spark"],
) as dag:
    application_id = os.getenv("EMR_SERVERLESS_APPLICATION_ID")
    execution_role_arn = os.getenv("EMR_SERVERLESS_EXECUTION_ROLE_ARN")
    entry_point = os.getenv("EMR_SERVERLESS_S3_ENTRYPOINT")
    log_uri = os.getenv("EMR_SERVERLESS_LOG_URI", "")

    emr_enabled = all([application_id, execution_role_arn, entry_point])

    if emr_enabled:
        submit_job = EmrServerlessStartJobOperator(
            task_id="submit_emr_serverless_job",
            application_id=application_id,
            execution_role_arn=execution_role_arn,
            job_driver={
                "sparkSubmit": {
                    "entryPoint": entry_point,
                }
            },
            configuration_overrides={
                "monitoringConfiguration": {
                    "s3MonitoringConfiguration": {
                        "logUri": log_uri
                    }
                }
            },
            wait_for_completion=True,
            aws_conn_id="aws_default",
        )
        submit_job
    else:
        emr_disabled = EmptyOperator(task_id="emr_serverless_disabled")
        emr_disabled
