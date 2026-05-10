#!/usr/bin/env python3
"""
Client Athena local — lakehouse-assurance
Usage:
    python3 scripts/athena_query.py                      # mode interactif
    python3 scripts/athena_query.py "SELECT ..."         # requête directe
    python3 scripts/athena_query.py --tables             # liste toutes les tables
"""

import sys
import time
import textwrap
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# ── Configuration ──────────────────────────────────────────────────────────────
REGION = "eu-west-3"
WORKGROUP = "lakehouse"
OUTPUT_BUCKET = "s3://lakehouse-assurance-migration-data-736047917658/athena/results/"
DEFAULT_DATABASE = "lakehouse_silver"
CATALOG = "AwsDataCatalog"
POLL_INTERVAL = 1.5  # secondes entre chaque vérification de statut
MAX_WAIT = 120       # timeout en secondes
# ──────────────────────────────────────────────────────────────────────────────

client = boto3.client("athena", region_name=REGION)


def run_query(sql: str, database: str = DEFAULT_DATABASE) -> list:
    """Exécute une requête Athena et retourne les résultats sous forme de liste."""
    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database, "Catalog": CATALOG},
        ResultConfiguration={"OutputLocation": OUTPUT_BUCKET},
        WorkGroup=WORKGROUP,
    )
    execution_id = response["QueryExecutionId"]

    # Attendre la fin de l'exécution
    elapsed = 0
    while elapsed < MAX_WAIT:
        status_resp = client.get_query_execution(QueryExecutionId=execution_id)
        state = status_resp["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status_resp["QueryExecution"]["Status"].get("StateChangeReason", "inconnu")
            raise RuntimeError(f"Requête {state}: {reason}")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    else:
        raise TimeoutError(f"Délai dépassé ({MAX_WAIT}s) pour l'exécution {execution_id}")

    # Récupérer les résultats (paginés)
    rows = []
    paginator = client.get_paginator("get_query_results")
    for page in paginator.paginate(QueryExecutionId=execution_id):
        for row in page["ResultSet"]["Rows"]:
            rows.append([col.get("VarCharValue", "") for col in row["Data"]])

    return rows


def print_table(rows: list) -> None:
    """Affiche les résultats sous forme de tableau ASCII."""
    if not rows:
        print("(aucun résultat)")
        return

    headers = rows[0]
    data = rows[1:]

    # Calculer largeurs de colonnes
    widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    fmt = "|" + "|".join(f" {{:<{w}}} " for w in widths) + "|"

    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for row in data:
        padded = (row + [""] * len(widths))[: len(widths)]
        print(fmt.format(*padded))
    print(sep)
    print(f"  {len(data)} ligne(s)")


def list_all_tables() -> None:
    """Affiche toutes les tables disponibles dans tous les databases du lakehouse."""
    databases = ["lakehouse_bronze", "lakehouse_silver", "lakehouse_gold"]
    for db in databases:
        try:
            rows = run_query(f"SHOW TABLES IN {db}", database=db)
            tables = [r[0] for r in rows[1:] if r]
            if tables:
                print(f"\n[{db}]")
                for t in tables:
                    print(f"  • {t}")
        except Exception:
            pass


def interactive_shell() -> None:
    """Mode interactif REPL — tape une requête SQL, obtiens les résultats."""
    print("=" * 60)
    print("  Athena Interactive Shell — lakehouse-assurance")
    print(f"  Region: {REGION}  |  Workgroup: {WORKGROUP}")
    print("  Commandes spéciales:")
    print("    \\tables   — lister toutes les tables")
    print("    \\db NAME  — changer de database (ex: \\db lakehouse_gold)")
    print("    \\quit     — quitter")
    print("=" * 60)

    database = DEFAULT_DATABASE
    buffer = []

    while True:
        prompt = f"athena [{database}]> " if not buffer else "           ...> "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir.")
            break

        # Commandes spéciales
        stripped = line.strip()
        if stripped == "\\quit":
            print("Au revoir.")
            break
        if stripped == "\\tables":
            list_all_tables()
            continue
        if stripped.startswith("\\db "):
            database = stripped[4:].strip()
            print(f"  → Database: {database}")
            continue

        buffer.append(line)

        # Exécuter quand la ligne se termine par ;
        if stripped.endswith(";"):
            sql = " ".join(buffer).rstrip(";").strip()
            buffer = []
            if not sql:
                continue
            print(f"  → Exécution...")
            start = time.time()
            try:
                rows = run_query(sql, database=database)
                elapsed = time.time() - start
                print_table(rows)
                print(f"  Temps: {elapsed:.2f}s")
            except Exception as e:
                print(f"  ERREUR: {e}")


def main() -> None:
    args = sys.argv[1:]

    if not args:
        interactive_shell()
        return

    if args[0] == "--tables":
        list_all_tables()
        return

    # Requête directe passée en argument
    sql = " ".join(args).rstrip(";")
    try:
        rows = run_query(sql)
        print_table(rows)
    except Exception as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
