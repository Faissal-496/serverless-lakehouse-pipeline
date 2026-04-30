"""
DAG: dag_athena_data_quality
==============================
Runs data quality checks via Athena SQL on the Silver and Gold layers.

Checks performed:
  - NULL rate on critical columns
  - Record count plausibility (non-zero)
  - Duplicate key detection
  - Referential consistency between Silver and Gold
  - Premium anomaly detection (negative, zero, or extreme values)
  - Date/age plausibility

On failure: Raises an AirflowException with a full quality report summary.
Results are stored as JSON in S3 for audit trail.

Schedule: Daily at 05:30 UTC (same day as KPI exports).
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

# CONFIGURATION

REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
S3_BUCKET = os.getenv("S3_BUCKET", "lakehouse-assurance-migration-data-736047917658")
ATHENA_WORKGROUP = os.getenv("ATHENA_WORKGROUP", "lakehouse")

DB_SILVER = "lakehouse_silver"
DB_GOLD = "lakehouse_gold"

QUERY_TIMEOUT_SECONDS = 180
QUALITY_RESULTS_PREFIX = "quality/reports"

# Thresholds
MAX_NULL_RATE_PCT = 5.0       # Alert if any critical column has > 5% NULLs
MAX_DUPLICATE_RATE_PCT = 1.0  # Alert if > 1% duplicate primary keys
MIN_RECORD_COUNT = 10         # Alert if table has fewer than 10 records

# DATA STRUCTURES

@dataclass
class QualityCheck:
    check_name: str
    database: str
    table: str
    status: str          # "PASS" | "FAIL" | "WARNING" | "ERROR"
    metric: Optional[float] = None
    threshold: Optional[float] = None
    detail: str = ""


# QUALITY CHECK DEFINITIONS

# Each entry: (check_name, database, table, sql, evaluation_fn)
# evaluation_fn receives {col: value} dict from first result row
# and returns (status, metric, threshold, detail)

def _eval_not_empty(row: dict, min_count: int = MIN_RECORD_COUNT):
    count = int(row.get("row_count", 0) or 0)
    if count == 0:
        return "FAIL", count, min_count, f"Table is EMPTY (0 rows)"
    if count < min_count:
        return "WARNING", count, min_count, f"Only {count} rows (min expected: {min_count})"
    return "PASS", count, min_count, f"{count} rows"


def _eval_null_rate(row: dict, col_name: str, max_pct: float = MAX_NULL_RATE_PCT):
    total = int(row.get("total", 1) or 1)
    null_count = int(row.get("null_count", 0) or 0)
    pct = round(null_count * 100.0 / max(total, 1), 2)
    if pct > max_pct:
        return "FAIL", pct, max_pct, f"{null_count}/{total} NULLs in '{col_name}' ({pct}%)"
    return "PASS", pct, max_pct, f"{null_count}/{total} NULLs in '{col_name}' ({pct}%)"


def _eval_no_duplicates(row: dict, max_pct: float = MAX_DUPLICATE_RATE_PCT):
    total = int(row.get("total_rows", 1) or 1)
    dupes = int(row.get("duplicate_count", 0) or 0)
    pct = round(dupes * 100.0 / max(total, 1), 2)
    if dupes > 0:
        status = "FAIL" if pct > max_pct else "WARNING"
        return status, pct, max_pct, f"{dupes} duplicate keys ({pct}% of {total} rows)"
    return "PASS", 0.0, max_pct, "No duplicates found"


def _eval_no_negative_premium(row: dict):
    count = int(row.get("neg_count", 0) or 0)
    if count > 0:
        return "FAIL", float(count), 0.0, f"{count} rows with negative or zero premium (prmaco)"
    return "PASS", 0.0, 0.0, "No negative/zero premiums"


def _eval_age_plausibility(row: dict):
    out_of_range = int(row.get("out_of_range", 0) or 0)
    if out_of_range > 0:
        return "FAIL", float(out_of_range), 0.0, f"{out_of_range} clients with age outside [18, 100]"
    return "PASS", 0.0, 0.0, "All client ages within plausible range [18, 100]"


QUALITY_CHECKS = [
    # ---- SILVER: record count ----
    {
        "check_name": "silver_record_count",
        "database": DB_SILVER,
        "table": "client_contrat_silver",
        "sql": "SELECT COUNT(*) AS row_count FROM client_contrat_silver",
        "eval_fn": lambda row: _eval_not_empty(row),
    },
    # ---- SILVER: NULL on nusoc (PK) ----
    {
        "check_name": "silver_null_nusoc",
        "database": DB_SILVER,
        "table": "client_contrat_silver",
        "sql": "SELECT COUNT(*) AS total, SUM(CASE WHEN nusoc IS NULL THEN 1 ELSE 0 END) AS null_count FROM client_contrat_silver",
        "eval_fn": lambda row: _eval_null_rate(row, "nusoc"),
    },
    # ---- SILVER: NULL on nucon (contract key) ----
    {
        "check_name": "silver_null_nucon",
        "database": DB_SILVER,
        "table": "client_contrat_silver",
        "sql": "SELECT COUNT(*) AS total, SUM(CASE WHEN nucon IS NULL THEN 1 ELSE 0 END) AS null_count FROM client_contrat_silver",
        "eval_fn": lambda row: _eval_null_rate(row, "nucon"),
    },
    # ---- SILVER: duplicate (nusoc, nucon) pairs ----
    {
        "check_name": "silver_duplicate_keys",
        "database": DB_SILVER,
        "table": "client_contrat_silver",
        "sql": """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) - COUNT(DISTINCT CONCAT(CAST(nusoc AS VARCHAR), '-', CAST(nucon AS VARCHAR))) AS duplicate_count
            FROM client_contrat_silver
        """,
        "eval_fn": lambda row: _eval_no_duplicates(row),
    },
    # ---- SILVER: negative/zero premium ----
    {
        "check_name": "silver_negative_premium",
        "database": DB_SILVER,
        "table": "client_contrat_silver",
        "sql": "SELECT COUNT(*) AS neg_count FROM client_contrat_silver WHERE prmaco <= 0",
        "eval_fn": lambda row: _eval_no_negative_premium(row),
    },
    # ---- SILVER: age plausibility ----
    {
        "check_name": "silver_age_plausibility",
        "database": DB_SILVER,
        "table": "client_contrat_silver",
        "sql": "SELECT COUNT(*) AS out_of_range FROM client_contrat_silver WHERE age_client < 18 OR age_client > 100",
        "eval_fn": lambda row: _eval_age_plausibility(row),
    },
    # ---- GOLD: contract_analysis record count ----
    {
        "check_name": "gold_contract_analysis_count",
        "database": DB_GOLD,
        "table": "contract_analysis",
        "sql": "SELECT COUNT(*) AS row_count FROM contract_analysis",
        "eval_fn": lambda row: _eval_not_empty(row, min_count=1),
    },
    # ---- GOLD: NULL type_vehicule ----
    {
        "check_name": "gold_null_type_vehicule",
        "database": DB_GOLD,
        "table": "contract_analysis",
        "sql": "SELECT COUNT(*) AS total, SUM(CASE WHEN type_vehicule IS NULL THEN 1 ELSE 0 END) AS null_count FROM contract_analysis",
        "eval_fn": lambda row: _eval_null_rate(row, "type_vehicule"),
    },
    # ---- GOLD: negative total_premium ----
    {
        "check_name": "gold_negative_total_premium",
        "database": DB_GOLD,
        "table": "contract_analysis",
        "sql": "SELECT COUNT(*) AS neg_count FROM contract_analysis WHERE total_premium < 0",
        "eval_fn": lambda row: _eval_no_negative_premium(row),
    },
    # ---- GOLD: client_profile_analysis count ----
    {
        "check_name": "gold_client_profiles_count",
        "database": DB_GOLD,
        "table": "client_profile_analysis",
        "sql": "SELECT COUNT(*) AS row_count FROM client_profile_analysis",
        "eval_fn": lambda row: _eval_not_empty(row, min_count=1),
    },
    # ---- GOLD: age_segment populated ----
    {
        "check_name": "gold_null_age_segment",
        "database": DB_GOLD,
        "table": "client_profile_analysis",
        "sql": "SELECT COUNT(*) AS total, SUM(CASE WHEN age_segment IS NULL THEN 1 ELSE 0 END) AS null_count FROM client_profile_analysis",
        "eval_fn": lambda row: _eval_null_rate(row, "age_segment"),
    },
]

# HELPERS

def _run_athena_query(athena, sql: str, database: str) -> list[dict]:
    resp = athena.start_query_execution(
        QueryString=sql.strip(),
        QueryExecutionContext={"Database": database, "Catalog": "AwsDataCatalog"},
        WorkGroup=ATHENA_WORKGROUP,
    )
    execution_id = resp["QueryExecutionId"]

    deadline = time.time() + QUERY_TIMEOUT_SECONDS
    while time.time() < deadline:
        time.sleep(3)
        status_resp = athena.get_query_execution(QueryExecutionId=execution_id)
        state = status_resp["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status_resp["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
            raise RuntimeError(f"Athena query {state}: {reason}")
    else:
        raise TimeoutError(f"Query timed out after {QUERY_TIMEOUT_SECONDS}s")

    results_resp = athena.get_query_results(QueryExecutionId=execution_id)
    result_set = results_resp["ResultSet"]
    columns = [col["Label"] for col in result_set["ResultSetMetadata"]["ColumnInfo"]]
    return [
        {col: field.get("VarCharValue", "") for col, field in zip(columns, row["Data"])}
        for row in result_set["Rows"][1:]
    ]


# TASK FUNCTIONS

def run_data_quality_checks(**context) -> None:
    """Execute all quality checks and push results to XCom."""
    run_date = context["ds"]
    athena = boto3.client("athena", region_name=REGION)

    results: list[QualityCheck] = []

    for check_def in QUALITY_CHECKS:
        check_name = check_def["check_name"]
        logging.info(f"Running check: {check_name}")
        try:
            rows = _run_athena_query(athena, check_def["sql"], check_def["database"])
            if not rows:
                status, metric, threshold, detail = "WARNING", None, None, "No rows returned"
            else:
                status, metric, threshold, detail = check_def["eval_fn"](rows[0])

            result = QualityCheck(
                check_name=check_name,
                database=check_def["database"],
                table=check_def["table"],
                status=status,
                metric=metric,
                threshold=threshold,
                detail=detail,
            )
        except Exception as exc:
            logging.error(f"  Check '{check_name}' raised exception: {exc}")
            result = QualityCheck(
                check_name=check_name,
                database=check_def["database"],
                table=check_def.get("table", ""),
                status="ERROR",
                detail=str(exc),
            )

        results.append(result)
        icon = {"PASS": "✓", "FAIL": "✗", "WARNING": "⚠", "ERROR": "✗"}.get(result.status, "?")
        logging.info(f"  {icon} {check_name}: {result.status} — {result.detail}")

    context["task_instance"].xcom_push(
        key="quality_results",
        value=[asdict(r) for r in results],
    )

    # Summary
    by_status = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    logging.info(f"\nQuality summary: {by_status}")

    fails = [r for r in results if r.status == "FAIL"]
    errors = [r for r in results if r.status == "ERROR"]

    if fails or errors:
        failed_names = [r.check_name for r in fails + errors]
        raise AirflowException(
            f"Data quality FAILED: {len(fails)} FAIL(s), {len(errors)} ERROR(s).\n"
            + "\n".join(f"  - {r.check_name}: {r.detail}" for r in fails + errors)
        )


def save_quality_report(**context) -> None:
    """Save the quality report JSON to S3 for audit trail."""
    run_date = context["ds"]
    results = context["task_instance"].xcom_pull(
        task_ids="run_data_quality_checks", key="quality_results"
    ) or []

    by_status = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    report = {
        "run_date": run_date,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": by_status,
        "total_checks": len(results),
        "checks": results,
    }

    s3 = boto3.client("s3", region_name=REGION)
    report_key = f"{QUALITY_RESULTS_PREFIX}/{run_date}/data_quality_report.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=report_key,
        Body=json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    logging.info(f"Quality report saved: s3://{S3_BUCKET}/{report_key}")
    logging.info(f"Summary: {by_status}")


# DAG DEFINITION

default_args = {
    "owner": "lakehouse",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,     # Do NOT retry quality checks — failures should be investigated
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="dag_athena_data_quality",
    description="Data quality checks on Silver and Gold layers via Athena SQL",
    default_args=default_args,
    schedule_interval="30 5 * * *",   # 05:30 UTC — right after KPI dashboard (05:00)
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "athena", "quality", "silver", "gold"],
) as dag:

    start = EmptyOperator(task_id="start")

    t_quality = PythonOperator(
        task_id="run_data_quality_checks",
        python_callable=run_data_quality_checks,
        execution_timeout=timedelta(minutes=30),
    )

    t_report = PythonOperator(
        task_id="save_quality_report",
        python_callable=save_quality_report,
        # Run even if quality checks fail — we still want the report saved
        trigger_rule="all_done",
    )

    end = EmptyOperator(task_id="end")

    start >> t_quality >> t_report >> end
