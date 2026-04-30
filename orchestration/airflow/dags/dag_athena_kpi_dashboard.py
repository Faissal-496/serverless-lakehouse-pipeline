"""
DAG: dag_athena_kpi_dashboard
==============================
Runs pre-defined SQL KPI queries on the Gold layer via Athena,
then saves the results as CSV files to S3 for downstream consumption
(dashboards, reports, exports).

Schedule: Daily at 05:00 UTC (after ETL at 02:00 and Crawler at 03:30).

Output S3 path: s3://{S3_BUCKET}/exports/kpi_dashboard/{date}/
"""

import csv
import io
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
ATHENA_WORKGROUP = os.getenv("ATHENA_WORKGROUP", "lakehouse")

DB_GOLD = "lakehouse_gold"
DB_SILVER = "lakehouse_silver"

QUERY_TIMEOUT_SECONDS = 300   # 5 minutes per query
EXPORT_PREFIX = "exports/kpi_dashboard"

# KPI QUERIES

KPI_QUERIES = [
    {
        "name": "kpi_contract_analysis_by_vehicle",
        "database": DB_GOLD,
        "description": "Nombre de contrats, primes et séniorité moyenne par type de véhicule",
        "sql": """
            SELECT
                type_vehicule,
                total_contracts,
                unique_clients,
                ROUND(avg_premium, 2)        AS avg_premium_eur,
                ROUND(total_premium, 2)      AS total_premium_eur,
                ROUND(avg_seniority, 1)      AS avg_seniority_years,
                ROUND(avg_guarantees, 1)     AS avg_guarantees_count
            FROM contract_analysis
            ORDER BY total_contracts DESC
        """,
    },
    {
        "name": "kpi_client_age_segments",
        "database": DB_GOLD,
        "description": "Distribution des clients par segment d'âge",
        "sql": """
            SELECT
                age_segment,
                COUNT(*)                     AS profile_count,
                ROUND(AVG(CAST(age_client AS double)), 1) AS avg_age
            FROM client_profile_analysis
            GROUP BY age_segment
            ORDER BY profile_count DESC
        """,
    },
    {
        "name": "kpi_client_gender_distribution",
        "database": DB_GOLD,
        "description": "Répartition des clients par sexe",
        "sql": """
            SELECT
                sexsoc,
                COUNT(*) AS count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
            FROM client_profile_analysis
            GROUP BY sexsoc
            ORDER BY count DESC
        """,
    },
    {
        "name": "kpi_young_client_ratio",
        "database": DB_GOLD,
        "description": "Ratio de clients jeunes (< 25 ans)",
        "sql": """
            SELECT
                SUM(client_jeune)                               AS young_clients,
                COUNT(*)                                        AS total_clients,
                ROUND(SUM(client_jeune) * 100.0 / COUNT(*), 2) AS pct_young
            FROM client_profile_analysis
        """,
    },
    {
        "name": "kpi_marital_status_by_age_segment",
        "database": DB_GOLD,
        "description": "Situation matrimoniale croisée avec segment d'âge",
        "sql": """
            SELECT
                age_segment,
                sitmat,
                COUNT(*) AS count
            FROM client_profile_analysis
            GROUP BY age_segment, sitmat
            ORDER BY age_segment, count DESC
        """,
    },
    {
        "name": "kpi_active_vs_inactive_contracts",
        "database": DB_SILVER,
        "description": "Contrats actifs vs inactifs avec prime moyenne",
        "sql": """
            SELECT
                contrat_actif,
                etat_contrat_libelle,
                COUNT(*)                    AS nb_contracts,
                ROUND(AVG(prmaco), 2)       AS avg_premium,
                ROUND(SUM(prmaco), 2)       AS total_premium
            FROM silver
            GROUP BY contrat_actif, etat_contrat_libelle
            ORDER BY nb_contracts DESC
        """,
    },
    {
        "name": "kpi_top10_premium_segments",
        "database": DB_SILVER,
        "description": "Top 10 segments (type véhicule + CSP) par prime moyenne",
        "sql": """
            SELECT
                type_vehicule,
                cspsoc,
                COUNT(*)                AS nb_contracts,
                ROUND(AVG(prmaco), 2)   AS avg_premium
            FROM silver
            WHERE contrat_actif = 1
            GROUP BY type_vehicule, cspsoc
            ORDER BY avg_premium DESC
            LIMIT 10
        """,
    },
]

# HELPERS

def _run_athena_query(athena, name: str, database: str, sql: str) -> list[dict]:
    """Run a single Athena query and return rows as list of dicts."""
    resp = athena.start_query_execution(
        QueryString=sql.strip(),
        QueryExecutionContext={"Database": database, "Catalog": "AwsDataCatalog"},
        WorkGroup=ATHENA_WORKGROUP,
    )
    execution_id = resp["QueryExecutionId"]
    logging.info(f"  Query '{name}' submitted: {execution_id}")

    deadline = time.time() + QUERY_TIMEOUT_SECONDS
    while time.time() < deadline:
        time.sleep(4)
        status_resp = athena.get_query_execution(QueryExecutionId=execution_id)
        state = status_resp["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status_resp["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
            raise RuntimeError(f"Athena query '{name}' {state}: {reason}")
    else:
        raise TimeoutError(f"Query '{name}' timed out after {QUERY_TIMEOUT_SECONDS}s")

    results_resp = athena.get_query_results(QueryExecutionId=execution_id)
    result_set = results_resp["ResultSet"]
    columns = [col["Label"] for col in result_set["ResultSetMetadata"]["ColumnInfo"]]
    rows = [
        {col: field.get("VarCharValue", "") for col, field in zip(columns, row["Data"])}
        for row in result_set["Rows"][1:]  # skip header
    ]
    logging.info(f"  Query '{name}': {len(rows)} rows returned")
    return rows


def _rows_to_csv(rows: list[dict]) -> str:
    """Serialize rows to CSV string."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# TASK FUNCTIONS

def run_kpi_queries_and_export(**context) -> None:
    """Run all KPI queries and upload CSV results to S3."""
    run_date = context["ds"]  # YYYY-MM-DD from Airflow execution date

    athena = boto3.client("athena", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)

    export_errors = []
    exported_files = []

    for query_def in KPI_QUERIES:
        name = query_def["name"]
        try:
            rows = _run_athena_query(
                athena,
                name=name,
                database=query_def["database"],
                sql=query_def["sql"],
            )

            csv_content = _rows_to_csv(rows)
            s3_key = f"{EXPORT_PREFIX}/{run_date}/{name}.csv"

            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=csv_content.encode("utf-8"),
                ContentType="text/csv",
            )
            exported_files.append(f"s3://{S3_BUCKET}/{s3_key}")
            logging.info(f"  Exported: s3://{S3_BUCKET}/{s3_key}")

        except Exception as exc:
            logging.error(f"  Query '{name}' failed: {exc}")
            export_errors.append(f"{name}: {exc}")

    context["task_instance"].xcom_push(key="exported_files", value=exported_files)

    if export_errors:
        raise RuntimeError(
            f"{len(export_errors)} KPI query/export(s) failed:\n"
            + "\n".join(f"  - {e}" for e in export_errors)
        )

    logging.info(f"KPI dashboard exported {len(exported_files)} CSV file(s) to s3://{S3_BUCKET}/{EXPORT_PREFIX}/{run_date}/")


def create_index_file(**context) -> None:
    """Write a JSON index file listing all exported CSVs for the run date."""
    run_date = context["ds"]
    exported_files = context["task_instance"].xcom_pull(
        task_ids="run_kpi_queries_and_export", key="exported_files"
    ) or []

    import json
    index = {
        "run_date": run_date,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "workgroup": ATHENA_WORKGROUP,
        "query_count": len(exported_files),
        "files": exported_files,
    }

    s3 = boto3.client("s3", region_name=REGION)
    index_key = f"{EXPORT_PREFIX}/{run_date}/index.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=index_key,
        Body=json.dumps(index, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    logging.info(f"Index written: s3://{S3_BUCKET}/{index_key}")


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
    dag_id="dag_athena_kpi_dashboard",
    description="Run KPI SQL queries on Gold/Silver via Athena and export CSV results to S3",
    default_args=default_args,
    schedule_interval="0 5 * * *",   # 05:00 UTC — after crawlers (04:00)
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "athena", "kpi", "gold"],
) as dag:

    start = EmptyOperator(task_id="start")

    t_run_queries = PythonOperator(
        task_id="run_kpi_queries_and_export",
        python_callable=run_kpi_queries_and_export,
        execution_timeout=timedelta(minutes=30),
    )

    t_index = PythonOperator(
        task_id="create_index_file",
        python_callable=create_index_file,
    )

    end = EmptyOperator(task_id="end")

    start >> t_run_queries >> t_index >> end
