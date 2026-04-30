"""
DAG: dag_glue_crawl_and_catalog
================================
Triggers all 3 Glue Crawlers (bronze, silver, gold) after ETL completes,
waits for their completion, then verifies that the expected tables exist
in the Glue Catalog.

Schedule: Triggered by the lakehouse_etl_complete DAG (or daily at 04:00 UTC,
          i.e. ~1h after ETL starts at 02:00 and crawlers run at 03:30).

Dependencies: boto3 must be installed in the Airflow environment.
"""

import os
import time
import logging
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

# CONFIGURATION

REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
S3_BUCKET = os.getenv("S3_BUCKET", "lakehouse-assurance-migration-data-736047917658")

BRONZE_DB = "lakehouse_bronze"
SILVER_DB = "lakehouse_silver"
GOLD_DB = "lakehouse_gold"

BRONZE_CRAWLER = "lakehouse-bronze-crawler"
SILVER_CRAWLER = "lakehouse-silver-crawler"
GOLD_CRAWLER = "lakehouse-gold-crawler"

ALL_CRAWLERS = [BRONZE_CRAWLER, SILVER_CRAWLER, GOLD_CRAWLER]

# Expected tables after crawling (table names as Glue infers them from S3 folders)
EXPECTED_TABLES = {
    BRONZE_DB: ["client", "contrat1", "contrat2"],
    SILVER_DB: ["client_contrat_silver"],
    GOLD_DB: ["client_profile_analysis", "contract_analysis"],
}

# TASK FUNCTIONS

def start_crawlers(**context) -> None:
    """Start all 3 Glue Crawlers. Skip already-running ones."""
    glue = boto3.client("glue", region_name=REGION)
    started = []
    skipped = []

    for crawler_name in ALL_CRAWLERS:
        try:
            glue.start_crawler(Name=crawler_name)
            started.append(crawler_name)
            logging.info(f"Started crawler: {crawler_name}")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "CrawlerRunningException":
                skipped.append(crawler_name)
                logging.info(f"Crawler already running, skipping: {crawler_name}")
            elif code == "EntityNotFoundException":
                raise RuntimeError(
                    f"Crawler '{crawler_name}' not found. "
                    "Run scripts/glue/bootstrap_glue_catalog.py first."
                ) from e
            else:
                raise

    context["task_instance"].xcom_push(key="started_crawlers", value=started)
    context["task_instance"].xcom_push(key="skipped_crawlers", value=skipped)
    logging.info(f"Started: {started}, Already running: {skipped}")


def wait_for_crawlers(**context) -> None:
    """Poll all crawlers every 30s until all are in READY or STOPPING state."""
    glue = boto3.client("glue", region_name=REGION)

    max_wait_seconds = 1200  # 20 minutes
    poll_interval = 30
    elapsed = 0

    while elapsed < max_wait_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval

        states = {}
        for crawler_name in ALL_CRAWLERS:
            resp = glue.get_crawler(Name=crawler_name)
            states[crawler_name] = resp["Crawler"]["State"]

        logging.info(f"Crawler states at {elapsed}s: {states}")

        still_running = [n for n, s in states.items() if s in ("RUNNING", "STOPPING")]
        if not still_running:
            logging.info("All crawlers finished.")
            context["task_instance"].xcom_push(key="final_states", value=states)
            return

    raise TimeoutError(
        f"Crawlers did not finish within {max_wait_seconds}s. "
        "Check AWS Console > Glue > Crawlers for details."
    )


def verify_catalog_tables(**context) -> None:
    """Check that expected tables exist in each Glue database."""
    glue = boto3.client("glue", region_name=REGION)
    issues = []

    for db_name, expected in EXPECTED_TABLES.items():
        try:
            resp = glue.get_tables(DatabaseName=db_name)
            existing = {t["Name"].lower() for t in resp.get("TableList", [])}
            logging.info(f"Database '{db_name}': found tables {existing}")

            for table in expected:
                if table.lower() not in existing:
                    issues.append(f"Missing table '{table}' in database '{db_name}'")
                    logging.warning(f"  MISSING: {db_name}.{table}")
                else:
                    logging.info(f"  OK: {db_name}.{table}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityNotFoundException":
                issues.append(f"Database '{db_name}' does not exist")
            else:
                raise

    if issues:
        raise ValueError(
            "Glue Catalog verification failed:\n" + "\n".join(f"  - {i}" for i in issues)
        )

    logging.info("Glue Catalog verification passed — all expected tables are present.")


def log_catalog_summary(**context) -> None:
    """Log a summary of all Glue Catalog tables and column counts."""
    glue = boto3.client("glue", region_name=REGION)

    for db_name in [BRONZE_DB, SILVER_DB, GOLD_DB]:
        try:
            resp = glue.get_tables(DatabaseName=db_name)
            tables = resp.get("TableList", [])
            logging.info(f"\n  [{db_name}] — {len(tables)} table(s):")
            for t in tables:
                cols = t.get("StorageDescriptor", {}).get("Columns", [])
                location = t.get("StorageDescriptor", {}).get("Location", "N/A")
                logging.info(f"    - {t['Name']:40s} {len(cols):3d} cols  {location}")
        except ClientError as e:
            logging.warning(f"Could not list tables for {db_name}: {e}")


# DAG DEFINITION

default_args = {
    "owner": "lakehouse",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="dag_glue_crawl_and_catalog",
    description="Trigger Glue Crawlers after ETL, wait for completion, verify Catalog tables",
    default_args=default_args,
    schedule_interval="0 4 * * *",   # 04:00 UTC — after ETL (02:00) and scheduled crawl (03:30)
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "glue", "catalog"],
) as dag:

    start = EmptyOperator(task_id="start")

    t_start_crawlers = PythonOperator(
        task_id="start_glue_crawlers",
        python_callable=start_crawlers,
    )

    t_wait = PythonOperator(
        task_id="wait_for_crawlers",
        python_callable=wait_for_crawlers,
        execution_timeout=timedelta(minutes=25),
    )

    t_verify = PythonOperator(
        task_id="verify_catalog_tables",
        python_callable=verify_catalog_tables,
    )

    t_summary = PythonOperator(
        task_id="log_catalog_summary",
        python_callable=log_catalog_summary,
    )

    end = EmptyOperator(task_id="end")

    start >> t_start_crawlers >> t_wait >> t_verify >> t_summary >> end
