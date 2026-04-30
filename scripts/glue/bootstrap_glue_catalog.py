#!/usr/bin/env python3
"""
Bootstrap Glue Catalog for the RUNNING Lakehouse environment.

What this script does:
  1. Creates IAM policy for Athena+Glue and attaches it to the EC2 role
  2. Creates Glue databases (bronze, silver, gold)
  3. Creates Glue Crawler IAM role
  4. Creates Glue Crawlers for each layer
  5. Starts all 3 crawlers and waits for completion
  6. Lists the tables discovered in each database
  7. Creates the Athena 'lakehouse' workgroup with S3 results path

Pre-requisites:
  - AWS credentials configured (aws configure or IAM role)
  - boto3 installed (pip install boto3)
  - The S3 bucket must contain Parquet files in bronze/, silver/, gold/

Usage:
  python3 scripts/glue/bootstrap_glue_catalog.py [--dry-run]

  --dry-run   Print what would be done without actually doing it.
"""

import argparse
import json
import sys
import time
import logging

import boto3
from botocore.exceptions import ClientError

# CONFIGURATION — matches the REAL running environment

REGION = "eu-west-3"
ACCOUNT_ID = "736047917658"

S3_BUCKET = "lakehouse-assurance-migration-data-736047917658"
S3_URI = f"s3://{S3_BUCKET}"

# IAM role used by EC2/Airflow (the instance profile role)
EC2_ROLE_NAME = "lakehouse-ec2-role"

# Glue names
DB_PREFIX = "lakehouse"
BRONZE_DB = f"{DB_PREFIX}_bronze"
SILVER_DB = f"{DB_PREFIX}_silver"
GOLD_DB = f"{DB_PREFIX}_gold"

CRAWLER_ROLE_NAME = "lakehouse-glue-crawler-role"
BRONZE_CRAWLER = "lakehouse-bronze-crawler"
SILVER_CRAWLER = "lakehouse-silver-crawler"
GOLD_CRAWLER = "lakehouse-gold-crawler"

# Athena
ATHENA_WORKGROUP = "lakehouse"
ATHENA_RESULTS_PATH = f"{S3_URI}/athena/results/"

# IAM policy name for Athena+Glue (attached to EC2 role)
ATHENA_GLUE_POLICY_NAME = "lakehouse-athena-glue-access-policy"

TAGS = [
    {"Key": "Project", "Value": "lakehouse-assurance"},
    {"Key": "Environment", "Value": "migration"},
    {"Key": "ManagedBy", "Value": "bootstrap-script"},
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def section(title: str) -> None:
    log.info("=" * 60)
    log.info(f"  {title}")
    log.info("=" * 60)


# STEP 1 — IAM: Athena+Glue policy on EC2 role

def ensure_athena_glue_policy(iam, dry_run: bool) -> str:
    section("IAM: Athena + Glue policy for EC2 role")

    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AthenaQueryExecution",
                "Effect": "Allow",
                "Action": [
                    "athena:StartQueryExecution",
                    "athena:StopQueryExecution",
                    "athena:GetQueryExecution",
                    "athena:GetQueryResults",
                    "athena:GetQueryResultsStream",
                    "athena:GetWorkGroup",
                    "athena:ListQueryExecutions",
                    "athena:BatchGetQueryExecution",
                    "athena:GetNamedQuery",
                    "athena:ListNamedQueries",
                    "athena:CreateNamedQuery",
                    "athena:ListWorkGroups",
                    "athena:GetDataCatalog",
                    "athena:ListDataCatalogs",
                ],
                "Resource": [
                    f"arn:aws:athena:{REGION}:{ACCOUNT_ID}:workgroup/{ATHENA_WORKGROUP}",
                    f"arn:aws:athena:{REGION}:{ACCOUNT_ID}:workgroup/primary",
                    f"arn:aws:athena:{REGION}:{ACCOUNT_ID}:datacatalog/AwsDataCatalog",
                ],
            },
            {
                "Sid": "GlueCatalogRead",
                "Effect": "Allow",
                "Action": [
                    "glue:GetDatabase",
                    "glue:GetDatabases",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartition",
                    "glue:GetPartitions",
                    "glue:BatchGetPartition",
                    "glue:GetCrawler",
                    "glue:GetCrawlers",
                    "glue:StartCrawler",
                    "glue:GetCrawlerMetrics",
                    "glue:GetCatalogImportStatus",
                ],
                "Resource": [
                    f"arn:aws:glue:{REGION}:{ACCOUNT_ID}:catalog",
                    f"arn:aws:glue:{REGION}:{ACCOUNT_ID}:database/*",
                    f"arn:aws:glue:{REGION}:{ACCOUNT_ID}:table/*/*",
                    f"arn:aws:glue:{REGION}:{ACCOUNT_ID}:crawler/*",
                ],
            },
            {
                "Sid": "S3AthenaResults",
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts",
                ],
                "Resource": [
                    f"arn:aws:s3:::{S3_BUCKET}",
                    f"arn:aws:s3:::{S3_BUCKET}/athena/*",
                ],
            },
        ],
    }

    policy_arn = f"arn:aws:iam::{ACCOUNT_ID}:policy/{ATHENA_GLUE_POLICY_NAME}"

    if dry_run:
        log.info(f"[DRY-RUN] Would create/verify policy: {policy_arn}")
        return policy_arn

    # Create or verify policy exists
    try:
        iam.get_policy(PolicyArn=policy_arn)
        log.info(f"Policy already exists: {ATHENA_GLUE_POLICY_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            resp = iam.create_policy(
                PolicyName=ATHENA_GLUE_POLICY_NAME,
                PolicyDocument=json.dumps(policy_document),
                Description="Allows EC2/Airflow to run Athena queries and read Glue Catalog",
            )
            policy_arn = resp["Policy"]["Arn"]
            log.info(f"Created policy: {policy_arn}")
        else:
            raise

    # Attach to EC2 role
    try:
        iam.attach_role_policy(RoleName=EC2_ROLE_NAME, PolicyArn=policy_arn)
        log.info(f"Attached {ATHENA_GLUE_POLICY_NAME} to role {EC2_ROLE_NAME}")
    except ClientError as e:
        if "already attached" in str(e).lower() or e.response["Error"]["Code"] == "EntityAlreadyExists":
            log.info(f"Policy already attached to {EC2_ROLE_NAME}")
        else:
            raise

    return policy_arn


# STEP 2 — GLUE DATABASES

def ensure_glue_databases(glue, dry_run: bool) -> None:
    section("Glue Catalog: Creating databases")

    databases = [
        (BRONZE_DB, "Lakehouse Bronze — raw ingested Parquet data (Client, Contrat1, Contrat2)", f"{S3_URI}/bronze/"),
        (SILVER_DB, "Lakehouse Silver — consolidated, joined, business-decoded data", f"{S3_URI}/silver/"),
        (GOLD_DB, "Lakehouse Gold — analytics-ready aggregated tables (KPIs, profiles)", f"{S3_URI}/gold/"),
    ]

    for db_name, description, location in databases:
        if dry_run:
            log.info(f"[DRY-RUN] Would create database: {db_name}")
            continue
        try:
            glue.get_database(Name=db_name)
            log.info(f"Database already exists: {db_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityNotFoundException":
                glue.create_database(
                    DatabaseInput={
                        "Name": db_name,
                        "Description": description,
                        "LocationUri": location,
                    }
                )
                log.info(f"Created database: {db_name}")
            else:
                raise


# STEP 3 — GLUE CRAWLER ROLE

def ensure_crawler_role(iam, dry_run: bool) -> str:
    section("IAM: Glue Crawler role")

    role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{CRAWLER_ROLE_NAME}"

    if dry_run:
        log.info(f"[DRY-RUN] Would create/verify crawler role: {CRAWLER_ROLE_NAME}")
        return role_arn

    assume_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "glue.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    })

    try:
        resp = iam.get_role(RoleName=CRAWLER_ROLE_NAME)
        role_arn = resp["Role"]["Arn"]
        log.info(f"Crawler role already exists: {role_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            resp = iam.create_role(
                RoleName=CRAWLER_ROLE_NAME,
                AssumeRolePolicyDocument=assume_policy,
                Description="Role for Glue Crawlers to read S3 and update Glue Catalog",
                Tags=[{"Key": t["Key"], "Value": t["Value"]} for t in TAGS],
            )
            role_arn = resp["Role"]["Arn"]
            log.info(f"Created crawler role: {role_arn}")
        else:
            raise

    # Attach AWS managed Glue service policy
    glue_service_policy = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
    try:
        iam.attach_role_policy(RoleName=CRAWLER_ROLE_NAME, PolicyArn=glue_service_policy)
        log.info("Attached AWSGlueServiceRole managed policy")
    except ClientError:
        log.info("AWSGlueServiceRole already attached")

    # Custom S3 read policy for crawler
    crawler_s3_policy_name = "lakehouse-glue-crawler-s3-policy"
    crawler_s3_policy_arn = f"arn:aws:iam::{ACCOUNT_ID}:policy/{crawler_s3_policy_name}"
    s3_policy_document = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "S3CrawlerRead",
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
            "Resource": [f"arn:aws:s3:::{S3_BUCKET}", f"arn:aws:s3:::{S3_BUCKET}/*"],
        }],
    })

    try:
        iam.get_policy(PolicyArn=crawler_s3_policy_arn)
        log.info(f"Crawler S3 policy already exists: {crawler_s3_policy_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            resp = iam.create_policy(
                PolicyName=crawler_s3_policy_name,
                PolicyDocument=s3_policy_document,
                Description="Allows Glue Crawlers to read the Lakehouse S3 bucket",
            )
            crawler_s3_policy_arn = resp["Policy"]["Arn"]
            log.info(f"Created crawler S3 policy: {crawler_s3_policy_arn}")
        else:
            raise

    try:
        iam.attach_role_policy(RoleName=CRAWLER_ROLE_NAME, PolicyArn=crawler_s3_policy_arn)
        log.info("Attached crawler S3 policy")
    except ClientError:
        log.info("Crawler S3 policy already attached")

    # Brief pause to allow IAM propagation
    log.info("Waiting 10s for IAM propagation...")
    time.sleep(10)

    return role_arn


# STEP 4 — GLUE CRAWLERS

def ensure_crawlers(glue, crawler_role_arn: str, dry_run: bool) -> None:
    section("Glue: Creating crawlers")

    crawlers = [
        (BRONZE_CRAWLER, BRONZE_DB, f"{S3_URI}/bronze/", "Bronze layer Parquet (Client, Contrat1, Contrat2)"),
        (SILVER_CRAWLER, SILVER_DB, f"{S3_URI}/silver/", "Silver layer Parquet (Client_contrat_silver)"),
        (GOLD_CRAWLER, GOLD_DB, f"{S3_URI}/gold/", "Gold layer Parquet (client_profile_analysis, contract_analysis)"),
    ]

    for name, db, s3_path, description in crawlers:
        if dry_run:
            log.info(f"[DRY-RUN] Would create crawler: {name} → {s3_path}")
            continue
        try:
            glue.get_crawler(Name=name)
            log.info(f"Crawler already exists: {name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityNotFoundException":
                glue.create_crawler(
                    Name=name,
                    Role=crawler_role_arn,
                    DatabaseName=db,
                    Description=description,
                    Targets={"S3Targets": [{"Path": s3_path}]},
                    Schedule="cron(30 3 * * ? *)",  # Daily at 03:30 UTC
                    SchemaChangePolicy={
                        "UpdateBehavior": "LOG",
                        "DeleteBehavior": "LOG",
                    },
                    RecrawlPolicy={"RecrawlBehavior": "CRAWL_NEW_FOLDERS_ONLY"},
                    Configuration=json.dumps({
                        "Version": 1.0,
                        "CrawlerOutput": {
                            "Tables": {"AddOrUpdateBehavior": "MergeNewColumns"}
                        },
                    }),
                    Tags={t["Key"]: t["Value"] for t in TAGS},
                )
                log.info(f"Created crawler: {name}")
            else:
                raise


# STEP 5 — START CRAWLERS AND WAIT

def run_crawlers(glue, dry_run: bool) -> None:
    section("Glue: Starting all crawlers")

    crawlers = [BRONZE_CRAWLER, SILVER_CRAWLER, GOLD_CRAWLER]

    if dry_run:
        for c in crawlers:
            log.info(f"[DRY-RUN] Would start crawler: {c}")
        return

    for crawler_name in crawlers:
        try:
            glue.start_crawler(Name=crawler_name)
            log.info(f"Started crawler: {crawler_name}")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "CrawlerRunningException":
                log.info(f"Crawler already running: {crawler_name}")
            else:
                log.warning(f"Could not start {crawler_name}: {e}")

    log.info("Waiting for all crawlers to complete (checking every 20s)...")
    max_wait = 600  # 10 minutes max
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(20)
        elapsed += 20

        states = {}
        for crawler_name in crawlers:
            resp = glue.get_crawler(Name=crawler_name)
            states[crawler_name] = resp["Crawler"]["State"]

        log.info(f"Crawler states ({elapsed}s elapsed): {states}")

        running = [n for n, s in states.items() if s in ("RUNNING", "STOPPING")]
        if not running:
            log.info("All crawlers finished.")
            break
    else:
        log.warning("Timeout waiting for crawlers. Check AWS Console for status.")


# STEP 6 — LIST DISCOVERED TABLES

def list_catalog_tables(glue, dry_run: bool) -> None:
    section("Glue Catalog: Tables discovered")

    if dry_run:
        log.info("[DRY-RUN] Skipping table listing")
        return

    for db_name in [BRONZE_DB, SILVER_DB, GOLD_DB]:
        try:
            resp = glue.get_tables(DatabaseName=db_name)
            tables = resp.get("TableList", [])
            log.info(f"\n  {db_name}: {len(tables)} table(s)")
            for t in tables:
                cols = t.get("StorageDescriptor", {}).get("Columns", [])
                log.info(f"    - {t['Name']} ({len(cols)} columns)")
                for c in cols[:5]:
                    log.info(f"        {c['Name']:30s} {c['Type']}")
                if len(cols) > 5:
                    log.info(f"        ... (+{len(cols)-5} more columns)")
        except ClientError as e:
            log.warning(f"Could not list tables for {db_name}: {e}")


# STEP 7 — ATHENA WORKGROUP

def ensure_athena_workgroup(athena, dry_run: bool) -> None:
    section("Athena: Creating workgroup")

    if dry_run:
        log.info(f"[DRY-RUN] Would create Athena workgroup: {ATHENA_WORKGROUP}")
        return

    try:
        athena.get_work_group(WorkGroup=ATHENA_WORKGROUP)
        log.info(f"Athena workgroup already exists: {ATHENA_WORKGROUP}")
    except ClientError as e:
        err_code = e.response["Error"]["Code"]
        err_msg = str(e)
        if err_code == "InvalidRequestException" and ("not found" in err_msg.lower() or "does not exist" in err_msg.lower()):
            athena.create_work_group(
                Name=ATHENA_WORKGROUP,
                Description="Lakehouse Analytics — SQL queries on Medallion layers via Glue Catalog",
                Configuration={
                    "ResultConfiguration": {
                        "OutputLocation": ATHENA_RESULTS_PATH,
                        "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"},
                    },
                    "EnforceWorkGroupConfiguration": True,
                    "PublishCloudWatchMetricsEnabled": True,
                    "BytesScannedCutoffPerQuery": 10 * 1024 ** 3,  # 10 GB safety limit
                    "EngineVersion": {"SelectedEngineVersion": "Athena engine version 3"},
                },
                Tags=[{"Key": t["Key"], "Value": t["Value"]} for t in TAGS],
            )
            log.info(f"Created Athena workgroup: {ATHENA_WORKGROUP}")
        else:
            raise


# MAIN

def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Glue Catalog for Lakehouse")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without doing it")
    args = parser.parse_args()

    dry_run = args.dry_run
    if dry_run:
        log.info("*** DRY-RUN MODE — no resources will be created ***")

    session = boto3.Session(region_name=REGION)
    iam = session.client("iam")
    glue = session.client("glue", region_name=REGION)
    athena = session.client("athena", region_name=REGION)

    log.info(f"Target: account={ACCOUNT_ID} region={REGION} bucket={S3_BUCKET}")

    # Step 1: IAM policy for Athena+Glue on EC2 role
    ensure_athena_glue_policy(iam, dry_run)

    # Step 2: Glue databases
    ensure_glue_databases(glue, dry_run)

    # Step 3: Crawler IAM role
    crawler_role_arn = ensure_crawler_role(iam, dry_run)

    # Step 4: Crawlers
    ensure_crawlers(glue, crawler_role_arn, dry_run)

    # Step 5: Run crawlers and wait
    run_crawlers(glue, dry_run)

    # Step 6: Show discovered tables
    list_catalog_tables(glue, dry_run)

    # Step 7: Athena workgroup
    ensure_athena_workgroup(athena, dry_run)

    section("Bootstrap complete!")
    log.info(f"Glue databases: {BRONZE_DB}, {SILVER_DB}, {GOLD_DB}")
    log.info(f"Athena workgroup: {ATHENA_WORKGROUP}")
    log.info(f"Athena results: {ATHENA_RESULTS_PATH}")
    log.info("")
    log.info("Next steps:")
    log.info("  1. Run test queries: python3 scripts/glue/test_athena_queries.py")
    log.info("  2. Trigger Airflow DAGs: dag_glue_crawl_and_catalog, dag_athena_kpi_dashboard")


if __name__ == "__main__":
    main()
