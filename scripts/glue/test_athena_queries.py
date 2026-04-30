#!/usr/bin/env python3
"""
Test Athena queries against the Lakehouse Glue Catalog.

Runs a set of validation SQL queries on the Bronze, Silver, and Gold layers
and prints results to stdout. Useful for smoke-testing the catalog after
running bootstrap_glue_catalog.py.

Usage:
  python3 scripts/glue/test_athena_queries.py [--layer bronze|silver|gold|all]

Requirements:
  - bootstrap_glue_catalog.py must have been run first
  - AWS credentials configured
  - boto3 installed
"""

import argparse
import sys
import time
import logging
from typing import List, Dict

import boto3
from botocore.exceptions import ClientError

# CONFIGURATION

REGION = "eu-west-3"
S3_BUCKET = "lakehouse-assurance-migration-data-736047917658"
ATHENA_WORKGROUP = "lakehouse"
ATHENA_RESULTS_PATH = f"s3://{S3_BUCKET}/athena/results/"

DB_BRONZE = "lakehouse_bronze"
DB_SILVER = "lakehouse_silver"
DB_GOLD = "lakehouse_gold"

# TEST QUERIES (each entry: name, database, sql)

BRONZE_QUERIES = [
    (
        "bronze_count_clients",
        DB_BRONZE,
        "SELECT COUNT(*) AS total_rows FROM client;",
    ),
    (
        "bronze_count_contrat1",
        DB_BRONZE,
        "SELECT COUNT(*) AS total_rows FROM contrat1;",
    ),
    (
        "bronze_count_contrat2",
        DB_BRONZE,
        "SELECT COUNT(*) AS total_rows FROM contrat2;",
    ),
    (
        "bronze_sample_client",
        DB_BRONZE,
        "SELECT * FROM client LIMIT 5;",
    ),
    (
        "bronze_null_check_client",
        DB_BRONZE,
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN nusoc IS NULL THEN 1 ELSE 0 END) AS null_nusoc,
            SUM(CASE WHEN sexsoc IS NULL THEN 1 ELSE 0 END) AS null_sexsoc
        FROM client;
        """,
    ),
]

SILVER_QUERIES = [
    (
        "silver_count_client_contrat",
        DB_SILVER,
        "SELECT COUNT(*) AS total_rows FROM silver;",
    ),
    (
        "silver_sample",
        DB_SILVER,
        "SELECT * FROM silver LIMIT 5;",
    ),
    (
        "silver_active_contracts",
        DB_SILVER,
        """
        SELECT contrat_actif, COUNT(*) AS count
        FROM silver
        GROUP BY contrat_actif
        ORDER BY contrat_actif;
        """,
    ),
    (
        "silver_vehicle_types",
        DB_SILVER,
        """
        SELECT type_vehicule, COUNT(*) AS count
        FROM silver
        GROUP BY type_vehicule
        ORDER BY count DESC
        LIMIT 10;
        """,
    ),
    (
        "silver_age_distribution",
        DB_SILVER,
        """
        SELECT
            CASE
                WHEN age_client < 25 THEN '< 25'
                WHEN age_client < 35 THEN '25-35'
                WHEN age_client < 50 THEN '35-50'
                ELSE '50+'
            END AS age_bracket,
            COUNT(*) AS count
        FROM silver
        GROUP BY 1
        ORDER BY 1;
        """,
    ),
]

GOLD_QUERIES = [
    (
        "gold_client_profiles_count",
        DB_GOLD,
        "SELECT COUNT(*) AS total_rows FROM client_profile_analysis;",
    ),
    (
        "gold_contract_analysis_count",
        DB_GOLD,
        "SELECT COUNT(*) AS total_rows FROM contract_analysis;",
    ),
    (
        "gold_contract_analysis_full",
        DB_GOLD,
        """
        SELECT
            type_vehicule,
            total_contracts,
            unique_clients,
            ROUND(avg_premium, 2)   AS avg_premium,
            ROUND(total_premium, 2) AS total_premium,
            ROUND(avg_seniority, 1) AS avg_seniority_years,
            ROUND(avg_guarantees, 1) AS avg_guarantees
        FROM contract_analysis
        ORDER BY total_contracts DESC;
        """,
    ),
    (
        "gold_client_segment_distribution",
        DB_GOLD,
        """
        SELECT age_segment, COUNT(*) AS profiles
        FROM client_profile_analysis
        GROUP BY age_segment
        ORDER BY profiles DESC;
        """,
    ),
    (
        "gold_premium_by_vehicle",
        DB_GOLD,
        """
        SELECT
            type_vehicule,
            total_contracts,
            unique_clients,
            ROUND(avg_premium, 2) AS avg_premium
        FROM contract_analysis
        ORDER BY avg_premium DESC;
        """,
    ),
]

QUERIES_BY_LAYER = {
    "bronze": BRONZE_QUERIES,
    "silver": SILVER_QUERIES,
    "gold": GOLD_QUERIES,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def run_query(athena, name: str, database: str, sql: str) -> List[Dict]:
    """Execute an Athena query and return rows as list of dicts."""
    log.info(f"Running: {name}")

    resp = athena.start_query_execution(
        QueryString=sql.strip(),
        QueryExecutionContext={"Database": database, "Catalog": "AwsDataCatalog"},
        WorkGroup=ATHENA_WORKGROUP,
    )
    execution_id = resp["QueryExecutionId"]

    # Poll until done
    for _ in range(60):
        time.sleep(3)
        status_resp = athena.get_query_execution(QueryExecutionId=execution_id)
        state = status_resp["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status_resp["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
            log.error(f"  Query {name} {state}: {reason}")
            return []
    else:
        log.error(f"  Query {name} timed out")
        return []

    # Fetch results
    results_resp = athena.get_query_results(QueryExecutionId=execution_id)
    result_set = results_resp["ResultSet"]

    columns = [col["Label"] for col in result_set["ResultSetMetadata"]["ColumnInfo"]]
    rows = []
    for row in result_set["Rows"][1:]:  # skip header row
        values = [field.get("VarCharValue", "") for field in row["Data"]]
        rows.append(dict(zip(columns, values)))

    return rows


def print_results(name: str, rows: List[Dict]) -> None:
    if not rows:
        log.info(f"  [{name}] No results returned")
        return

    columns = list(rows[0].keys())
    col_widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}

    header = "  | " + " | ".join(c.ljust(col_widths[c]) for c in columns) + " |"
    separator = "  +-" + "-+-".join("-" * col_widths[c] for c in columns) + "-+"

    print(f"\n  [{name}] — {len(rows)} row(s)")
    print(separator)
    print(header)
    print(separator)
    for row in rows:
        line = "  | " + " | ".join(str(row.get(c, "")).ljust(col_widths[c]) for c in columns) + " |"
        print(line)
    print(separator)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Athena queries on Lakehouse Glue Catalog")
    parser.add_argument(
        "--layer",
        choices=["bronze", "silver", "gold", "all"],
        default="all",
        help="Which layer to test (default: all)",
    )
    args = parser.parse_args()

    session = boto3.Session(region_name=REGION)
    athena = session.client("athena", region_name=REGION)

    layers = ["bronze", "silver", "gold"] if args.layer == "all" else [args.layer]

    passed = 0
    failed = 0

    for layer in layers:
        log.info("=" * 60)
        log.info(f"  Testing layer: {layer.upper()}")
        log.info("=" * 60)

        for name, database, sql in QUERIES_BY_LAYER[layer]:
            try:
                rows = run_query(athena, name, database, sql)
                print_results(name, rows)
                passed += 1
            except (ClientError, Exception) as exc:
                log.error(f"  Query {name} raised exception: {exc}")
                failed += 1

    log.info("=" * 60)
    log.info(f"  Results: {passed} passed / {failed} failed")
    log.info("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
