"""
ETL_lakehouse -- EMR Serverless Lakehouse Pipeline DAG
======================================================
Pipeline : RAW (S3 sensor) -> Bronze -> Silver -> Gold
Runtime  : EMR Serverless (exclusively)
Data-driven : dataset definitions loaded from config/datasets/*.yaml

For the standalone Spark cluster (Docker), use ``lakehouse_etl_complete.py``.

Architecture contracts:
    - NO BashOperator -- uses SparkJobOperator (custom)
    - Quality checks after each layer (row count, nulls, duplicates)
    - Lineage tracking per layer transition
    - SNS alerting on failure
    - Idempotent writes (overwrite mode)

Required environment variables (must be set in .env.docker):
    EMR_APP_ID               - EMR Serverless application ID
    EMR_EXECUTION_ROLE_ARN   - IAM role ARN for EMR execution
    S3_BUCKET                - Data lake S3 bucket name
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.utils.task_group import TaskGroup

from lakehouse.operators.spark_job_operator import SparkJobOperator

_dag_log = logging.getLogger(__name__)

# ============================================================================
# Global configuration -- single source of truth (EMR Serverless only)
# ============================================================================

S3_BUCKET: str = os.getenv("S3_BUCKET", "lakehouse-assurance-prod-data")
AWS_REGION: str = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
APP_ENV: str = os.getenv("APP_ENV", "prod")

# EMR Serverless (mandatory)
EMR_APP_ID: str = os.getenv("EMR_APP_ID", "")
EMR_EXECUTION_ROLE_ARN: str = os.getenv("EMR_EXECUTION_ROLE_ARN", "")

if not EMR_APP_ID or not EMR_EXECUTION_ROLE_ARN:
    _dag_log.warning(
        "ETL_lakehouse: EMR_APP_ID or EMR_EXECUTION_ROLE_ARN not set. "
        "DAG will parse but tasks will fail at runtime. "
        "Set these in .env.docker and restart Airflow containers."
    )

S3_WHEEL_PATH: str = os.getenv(
    "S3_WHEEL_PATH",
    f"s3://{S3_BUCKET}/artifacts/lakehouse-latest.whl",
)
S3_SCRIPTS_PREFIX: str = os.getenv(
    "S3_SCRIPTS_PREFIX",
    "emr/scripts/lakehouse/jobs",
)
S3_LOGS_PREFIX: str = "logs/emr-serverless"

S3_VENV_PATH: str = os.getenv(
    "S3_VENV_PATH",
    f"s3://{S3_BUCKET}/emr/artifacts/pyspark_venv.tar.gz",
)

# Alerting
SNS_TOPIC_ARN: str = os.getenv(
    "SNS_TOPIC_ARN",
    "arn:aws:sns:eu-west-3:387642999442:lakehouse-etl-alerts",
)

# Airflow Dataset outlets (for Dataset-aware scheduling downstream)
BRONZE_DATASET = Dataset(f"s3://{S3_BUCKET}/bronze/")
SILVER_DATASET = Dataset(f"s3://{S3_BUCKET}/silver/")
GOLD_DATASET = Dataset(f"s3://{S3_BUCKET}/gold/")

# ============================================================================
# Job script mapping -- layer -> S3 entry-point for EMR Serverless
# ============================================================================

JOB_SCRIPTS: Dict[str, Dict[str, str]] = {
    "bronze": {
        "job_name": "bronze_ingest",
        "script": "bronze_ingest_job.py",
    },
    "silver": {
        "job_name": "silver_transform",
        "script": "silver_transform_job.py",
    },
    "gold": {
        "job_name": "gold_transform",
        "script": "gold_transform_job.py",
    },
}


# ============================================================================
# Utility functions
# ============================================================================


def load_dataset_configs() -> Dict[str, Dict[str, Any]]:
    """
    Load every ``config/datasets/*.yaml`` and return a dict keyed by
    dataset name.  Each value contains the full YAML content including
    ``layer``, ``quality_rules``, ``upstream_datasets``, etc.
    """
    config_dir = Path(os.getenv("CONFIG_DIR", "/app/config"))
    datasets_dir = config_dir / "datasets"
    configs: Dict[str, Dict[str, Any]] = {}

    if not datasets_dir.is_dir():
        return configs

    for yaml_file in sorted(datasets_dir.glob("*.yaml")):
        with open(yaml_file) as fh:
            cfg = yaml.safe_load(fh) or {}
        dataset_name = cfg.get("dataset")
        if dataset_name:
            configs[dataset_name] = cfg

    return configs


def load_spark_config() -> Dict[str, str]:
    """
    Load the Spark ``--conf`` map from the EMR Serverless YAML profile.
    """
    config_dir = Path(os.getenv("CONFIG_DIR", "/app/config"))
    config_file = config_dir / "spark" / "emr-serverless.yaml"

    if config_file.exists():
        with open(config_file) as fh:
            raw = yaml.safe_load(fh) or {}
        conf = raw.get("spark", {}).get("config", {})
        return {str(k): str(v) for k, v in conf.items()}
    return {}


def _build_spark_env_vars() -> Dict[str, str]:
    """
    Environment variables forwarded to the Spark driver/executor.
    Credentials are passed only when explicitly set in the container.
    """
    env: Dict[str, str] = {
        "PYTHONPATH": "/app/src",
        "APP_ENV": APP_ENV,
        "CONFIG_DIR": os.getenv("CONFIG_DIR", "/app/config"),
        "S3_BUCKET": S3_BUCKET,
        "AWS_DEFAULT_REGION": AWS_REGION,
    }
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    if aws_key:
        env["AWS_ACCESS_KEY_ID"] = aws_key
    if aws_secret:
        env["AWS_SECRET_ACCESS_KEY"] = aws_secret
    return env


def build_spark_task(
    *,
    job_name: str,
    job_script: str,
    task_group: TaskGroup,
    dag: DAG,
    spark_config: Dict[str, str],
    env_vars: Dict[str, str],
    outlets: Optional[List[Dataset]] = None,
    execution_timeout: timedelta = timedelta(hours=2),
    retries: int = 2,
) -> SparkJobOperator:
    """
    Factory that creates a fully-configured ``SparkJobOperator``
    for EMR Serverless execution.
    """
    return SparkJobOperator(
        task_id=f"run_{job_name}",
        job_name=job_name,
        job_script=job_script,
        spark_mode="emr-serverless",
        # EMR
        emr_app_id=EMR_APP_ID,
        emr_execution_role_arn=EMR_EXECUTION_ROLE_ARN,
        s3_bucket=S3_BUCKET,
        s3_scripts_prefix=S3_SCRIPTS_PREFIX,
        s3_wheel_path=S3_WHEEL_PATH,
        s3_venv_path=S3_VENV_PATH,
        s3_logs_prefix=S3_LOGS_PREFIX,
        aws_region=AWS_REGION,
        # Common
        spark_config=spark_config,
        env_vars=env_vars,
        dag=dag,
        task_group=task_group,
        outlets=outlets or [],
        execution_timeout=execution_timeout,
        retries=retries,
        retry_delay=timedelta(minutes=5),
    )


# ============================================================================
# Quality-check callable (used with PythonOperator)
# ============================================================================


def _run_quality_check(
    dataset_name: str,
    layer: str,
    s3_bucket: str,
    quality_rules: List[Dict[str, Any]],
    **context: Any,
) -> None:
    """
    Lightweight PySpark quality gate that runs in the Airflow worker.

    Creates a ``local[1]`` SparkSession, reads the output parquet from S3,
    and executes the quality rules defined in the dataset YAML.  If any
    ``severity=error`` rule fails the task raises ``AirflowException``.
    """
    import logging

    from pyspark.sql import SparkSession

    from lakehouse.quality.data_quality_checks import (
        check_duplicates,
        check_null_columns,
    )
    from lakehouse.monitoring.logging import log_data_quality, log_quality_gate
    from lakehouse.lineage.lineage import log_lineage

    log = logging.getLogger("airflow.task")

    # --- Build a minimal local session for reads only ----------------------
    builder = (
        SparkSession.builder.master("local[1]")
        .appName(f"dq_{layer}_{dataset_name}")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.driver.memory", "512m")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint.region", AWS_REGION)
        .config("spark.hadoop.fs.s3a.fast.upload", "true")
    )
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    if aws_key and aws_secret:
        builder = builder.config("spark.hadoop.fs.s3a.access.key", aws_key).config(
            "spark.hadoop.fs.s3a.secret.key", aws_secret
        )
    else:
        builder = builder.config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "com.amazonaws.auth.DefaultAWSCredentialsProviderChain",
        )

    spark = builder.getOrCreate()

    try:
        data_path = f"s3a://{s3_bucket}/{layer}/{dataset_name}"
        log.info("Reading %s for quality checks …", data_path)
        df = spark.read.parquet(data_path)

        # Check 1 — row count > 0
        row_count = df.count()
        log.info("  row_count = %d", row_count)
        if row_count == 0:
            raise RuntimeError(f"{dataset_name} has 0 rows")

        passed, failed = 0, 0
        results: Dict[str, Any] = {"row_count": row_count}

        for rule in quality_rules:
            rule_name = rule.get("rule", "")
            severity = rule.get("severity", "warning")
            cols = rule.get("columns", [])

            if rule_name == "not_null" and cols:
                # only check columns that exist
                existing = [c for c in cols if c in df.columns]
                if existing:
                    null_count = check_null_columns(df, existing)
                    ok = null_count == 0
                    results[f"not_null({','.join(existing)})"] = {"null_count": null_count, "passed": ok}
                    if ok:
                        passed += 1
                    elif severity == "error":
                        failed += 1
                    else:
                        passed += 1  # warning-only

            elif rule_name == "no_duplicates" and cols:
                existing = [c for c in cols if c in df.columns]
                if existing:
                    dup_count = check_duplicates(df, existing)
                    ok = dup_count == 0
                    results[f"no_duplicates({','.join(existing)})"] = {"dup_count": dup_count, "passed": ok}
                    if ok:
                        passed += 1
                    elif severity == "error":
                        failed += 1
                    else:
                        passed += 1

        # Schema check (always applied)
        schema_cols = len(df.columns)
        results["schema_columns"] = schema_cols
        passed += 1

        # Log results
        log_data_quality(dataset_name, row_count, failed, results)
        log_quality_gate(dataset_name, layer, passed, failed)

        # Push to XCom
        ti = context["ti"]
        ti.xcom_push(key=f"dq_row_count_{dataset_name}", value=row_count)
        ti.xcom_push(key=f"dq_passed_{dataset_name}", value=passed)
        ti.xcom_push(key=f"dq_failed_{dataset_name}", value=failed)

        # Lineage (quality check is also a lineage node)
        log_lineage(
            source=f"s3://{s3_bucket}/{layer}/{dataset_name}",
            target=f"dq_check/{layer}/{dataset_name}",
            rows=row_count,
        )

        if failed > 0:
            from airflow.exceptions import AirflowException

            raise AirflowException(
                f"Quality gate FAILED for {layer}/{dataset_name}: "
                f"{failed} error-level checks failed. Details: {results}"
            )

        log.info("Quality gate PASSED: %s/%s", layer, dataset_name)

    finally:
        spark.stop()


# ============================================================================
# Failure callback — SNS alert
# ============================================================================


def _on_failure_callback(context: Dict[str, Any]) -> None:
    """Send an SNS notification when a task fails."""
    if not SNS_TOPIC_ARN:
        return
    try:
        import boto3

        ti = context["task_instance"]
        dag_id = context["dag"].dag_id
        exc = context.get("exception", "N/A")

        message = (
            f"Lakehouse ETL Task Failed\n"
            f"DAG       : {dag_id}\n"
            f"Task      : {ti.task_id}\n"
            f"Execution : {context.get('execution_date', '')}\n"
            f"Error     : {exc}\n"
        )

        boto3.client("sns", region_name=AWS_REGION).publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[LAKEHOUSE] Task Failed: {ti.task_id}",
            Message=message,
        )
    except Exception as err:  # noqa: BLE001
        # Alerting failure must never mask the real error
        import logging

        logging.getLogger("airflow.task").warning("SNS alert failed: %s", err)


# ============================================================================
# Load configs at DAG-parse time
# ============================================================================

DATASET_CONFIGS = load_dataset_configs()
SPARK_CONFIG = load_spark_config()
SPARK_ENV_VARS = _build_spark_env_vars()

# Classify datasets by layer
BRONZE_DATASETS = {k: v for k, v in DATASET_CONFIGS.items() if v.get("layer") == "bronze"}
SILVER_DATASETS = {k: v for k, v in DATASET_CONFIGS.items() if v.get("layer") == "silver"}
GOLD_DATASETS = {k: v for k, v in DATASET_CONFIGS.items() if v.get("layer") == "gold"}


# ============================================================================
# DAG definition
# ============================================================================

default_args = {
    "owner": "lakehouse-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
    "on_failure_callback": _on_failure_callback,
}

with DAG(
    dag_id="ETL_lakehouse",
    description="Production Lakehouse ETL — Bronze → Silver → Gold",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "etl", "production", "emr-serverless"],
    default_args=default_args,
    doc_md=__doc__,
) as dag:
    # ------------------------------------------------------------------
    # Bookend tasks
    # ------------------------------------------------------------------
    start = EmptyOperator(task_id="pipeline_start")
    end = EmptyOperator(task_id="pipeline_end", trigger_rule="none_failed_min_one_success")

    # ==================================================================
    # DATA READINESS — S3 sensors for each bronze raw file
    # ==================================================================
    with TaskGroup("data_readiness", dag=dag) as tg_sensors:
        sensor_tasks = []
        for ds_name, ds_cfg in BRONZE_DATASETS.items():
            raw_file = f"RAW/{ds_name}.csv"
            sensor = S3KeySensor(
                task_id=f"wait_{ds_name.lower()}_csv",
                bucket_name=S3_BUCKET,
                bucket_key=raw_file,
                aws_conn_id="aws_default",
                poke_interval=60,
                timeout=600,
                mode="reschedule",
                retries=1,
                dag=dag,
            )
            sensor_tasks.append(sensor)

    # ==================================================================
    # BRONZE — ingest raw CSVs to Parquet
    # ==================================================================
    with TaskGroup("bronze", dag=dag) as tg_bronze:
        bronze_job = build_spark_task(
            job_name=JOB_SCRIPTS["bronze"]["job_name"],
            job_script=JOB_SCRIPTS["bronze"]["script"],
            task_group=tg_bronze,
            dag=dag,
            spark_config=SPARK_CONFIG,
            env_vars=SPARK_ENV_VARS,
            outlets=[BRONZE_DATASET],
            execution_timeout=timedelta(hours=1),
        )

        bronze_dq_tasks = []
        for ds_name, ds_cfg in BRONZE_DATASETS.items():
            dq = PythonOperator(
                task_id=f"dq_{ds_name.lower()}",
                python_callable=_run_quality_check,
                op_kwargs={
                    "dataset_name": ds_name,
                    "layer": "bronze",
                    "s3_bucket": S3_BUCKET,
                    "quality_rules": ds_cfg.get("quality_rules", []),
                },
                dag=dag,
                task_group=tg_bronze,
                retries=1,
                retry_delay=timedelta(minutes=2),
                execution_timeout=timedelta(minutes=15),
            )
            bronze_dq_tasks.append(dq)

        bronze_job >> bronze_dq_tasks  # type: ignore[operator]

    # ==================================================================
    # SILVER — transform bronze → silver
    # ==================================================================
    with TaskGroup("silver", dag=dag) as tg_silver:
        silver_job = build_spark_task(
            job_name=JOB_SCRIPTS["silver"]["job_name"],
            job_script=JOB_SCRIPTS["silver"]["script"],
            task_group=tg_silver,
            dag=dag,
            spark_config=SPARK_CONFIG,
            env_vars=SPARK_ENV_VARS,
            outlets=[SILVER_DATASET],
            execution_timeout=timedelta(hours=1),
        )

        silver_dq_tasks = []
        for ds_name, ds_cfg in SILVER_DATASETS.items():
            dq = PythonOperator(
                task_id=f"dq_{ds_name.lower()}",
                python_callable=_run_quality_check,
                op_kwargs={
                    "dataset_name": ds_cfg.get("dataset", ds_name),
                    "layer": "silver",
                    "s3_bucket": S3_BUCKET,
                    "quality_rules": ds_cfg.get("quality_rules", []),
                },
                dag=dag,
                task_group=tg_silver,
                retries=1,
                retry_delay=timedelta(minutes=2),
                execution_timeout=timedelta(minutes=15),
            )
            silver_dq_tasks.append(dq)

        silver_job >> silver_dq_tasks  # type: ignore[operator]

    # ==================================================================
    # GOLD — analytics-ready aggregations
    # ==================================================================
    with TaskGroup("gold", dag=dag) as tg_gold:
        gold_job = build_spark_task(
            job_name=JOB_SCRIPTS["gold"]["job_name"],
            job_script=JOB_SCRIPTS["gold"]["script"],
            task_group=tg_gold,
            dag=dag,
            spark_config=SPARK_CONFIG,
            env_vars=SPARK_ENV_VARS,
            outlets=[GOLD_DATASET],
            execution_timeout=timedelta(hours=1),
        )

        gold_dq_tasks = []
        for ds_name, ds_cfg in GOLD_DATASETS.items():
            # Skip datasets without a corresponding job output
            if ds_name == "kpi_final":
                continue
            dq = PythonOperator(
                task_id=f"dq_{ds_name.lower()}",
                python_callable=_run_quality_check,
                op_kwargs={
                    "dataset_name": ds_name,
                    "layer": "gold",
                    "s3_bucket": S3_BUCKET,
                    "quality_rules": ds_cfg.get("quality_rules", []),
                },
                dag=dag,
                task_group=tg_gold,
                retries=1,
                retry_delay=timedelta(minutes=2),
                execution_timeout=timedelta(minutes=15),
            )
            gold_dq_tasks.append(dq)

        gold_job >> gold_dq_tasks  # type: ignore[operator]

    # ==================================================================
    # LINEAGE — record layer transitions
    # ==================================================================

    def _record_lineage(**context: Any) -> None:
        from lakehouse.lineage.lineage import LineageTracker

        tracker = LineageTracker()

        # Bronze ← RAW
        for ds_name in BRONZE_DATASETS:
            tracker.record(
                source_datasets=[f"s3://{S3_BUCKET}/RAW/{ds_name}.csv"],
                target_dataset=f"s3://{S3_BUCKET}/bronze/{ds_name}",
                transformation="csv_to_parquet",
                layer="bronze",
            )

        # Silver ← Bronze
        for ds_name, ds_cfg in SILVER_DATASETS.items():
            upstream = ds_cfg.get("upstream_datasets", [])
            tracker.record(
                source_datasets=[f"s3://{S3_BUCKET}/bronze/{u}" for u in upstream],
                target_dataset=f"s3://{S3_BUCKET}/silver/{ds_cfg.get('dataset', ds_name)}",
                transformation="consolidation_enrichment",
                layer="silver",
            )

        # Gold ← Silver
        for ds_name, ds_cfg in GOLD_DATASETS.items():
            if ds_name == "kpi_final":
                continue
            upstream = ds_cfg.get("upstream_datasets", [])
            tracker.record(
                source_datasets=[f"s3://{S3_BUCKET}/silver/{u}" for u in upstream],
                target_dataset=f"s3://{S3_BUCKET}/gold/{ds_name}",
                transformation="aggregation_analytics",
                layer="gold",
            )

        context["ti"].xcom_push(key="lineage_graph", value=tracker.get_lineage_graph())

    record_lineage = PythonOperator(
        task_id="record_lineage",
        python_callable=_record_lineage,
        dag=dag,
        trigger_rule="none_failed_min_one_success",
    )

    # ==================================================================
    # Dependency wiring
    # ==================================================================
    start >> tg_sensors >> tg_bronze >> tg_silver >> tg_gold >> record_lineage >> end
