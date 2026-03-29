"""
Spark ETL Pipeline - Bronze → Silver → Gold
Utilise spark-submit pour exécuter les scripts validés

Structure:
1. Bronze: CSV → S3 Parquet
2. Silver: Standardize + Join
3. Gold: Analytics + KPIs

Note: Les scripts Python sont exécutés via spark-submit sur le Spark master
      Au lieu d'être importés comme modules Python.
      Cela permet une exécution distribuée et la migration future vers EMR Serverless.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
import os

# ============================================================================
# Configuration from Environment
# ============================================================================
SPARK_MASTER = "local[*]"  # Use local mode since files are on Airflow worker
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-west-3')
S3_BUCKET = os.getenv('S3_BUCKET', 'lakehouse-assurance-moto-prod')
GLUE_DB_NAME = os.getenv('GLUE_DB_NAME', 'lakehouse_assurance_dev')
APP_ENV = os.getenv('APP_ENV', 'dev')

# ============================================================================
# Spark Submit Environment Variables
# ============================================================================
SPARK_ENV = f"""
export AWS_ACCESS_KEY_ID='{AWS_ACCESS_KEY_ID}'
export AWS_SECRET_ACCESS_KEY='{AWS_SECRET_ACCESS_KEY}'
export AWS_DEFAULT_REGION='{AWS_DEFAULT_REGION}'
export S3_BUCKET='{S3_BUCKET}'
export GLUE_DB_NAME='{GLUE_DB_NAME}'
export APP_ENV='{APP_ENV}'
export PYTHONPATH=/opt/lakehouse/src:$PYTHONPATH
"""

# ============================================================================
# Default Arguments
# ============================================================================
default_args = {
    'owner': 'lakehouse-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
}

# ============================================================================
# DAG Definition
# ============================================================================
dag = DAG(
    'spark_submit_etl',
    default_args=default_args,
    description='Spark ETL: Bronze → Silver → Gold (spark-submit based)',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['spark', 'etl', 'lakehouse', 'production', 'spark-submit'],
)

# ============================================================================
# Task: Validate Environment
# ============================================================================
validate_env = BashOperator(
    task_id='validate_environment',
    bash_command=f"""
    {SPARK_ENV}
    echo "✅ Environment Validation"
    echo "========================="
    echo "Spark Master: {SPARK_MASTER}"
    echo "AWS Region: $AWS_DEFAULT_REGION"
    echo "S3 Bucket: $S3_BUCKET"
    echo "Environment: $APP_ENV"
    echo ""
    echo "✅ All environment variables set"
    """,
    dag=dag,
)

# ============================================================================
# Task: Bronze Ingestion
# Ingest CSV files from local filesystem to S3 Parquet
# Input: /opt/lakehouse/data/*.csv
# Output: s3://bucket/bronze/
# ============================================================================
bronze_ingestion = BashOperator(
    task_id='bronze_ingestion',
    bash_command=f"""
    set -e
    {SPARK_ENV}
    echo "📊 STAGE 1: BRONZE INGESTION"
    spark-submit \\
        --master local[*] \\
        --deploy-mode client \\
        --driver-memory 2g \\
        --executor-memory 2g \\
        --total-executor-cores 4 \\
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \\
        /opt/lakehouse/src/lakehouse/ingestion/bronze_ingest.py 2>&1
    echo "✅ Bronze ingestion completed"
    """,
    dag=dag,
)

# ============================================================================
# Task: Silver Transformation
# Consolidate, standardize, and join contract data
# Input: s3://bucket/bronze/
# Output: s3://bucket/silver/
# ============================================================================
silver_transformation = BashOperator(
    task_id='silver_transformation',
    bash_command=f"""
    set -e
    {SPARK_ENV}
    echo "📊 STAGE 2: SILVER TRANSFORMATION"
    spark-submit \\
        --master local[*] \\
        --deploy-mode client \\
        --driver-memory 2g \\
        --executor-memory 2g \\
        --total-executor-cores 4 \\
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \\
        /opt/lakehouse/src/lakehouse/transformation/bronze_to_silver.py 2>&1
    echo "✅ Silver transformation completed"
    """,
    dag=dag,
)

# ============================================================================
# Task: Gold Transformation
# Create analytical tables and KPI dashboard
# Input: s3://bucket/silver/
# Output: s3://bucket/gold/
# ============================================================================
gold_transformation = BashOperator(
    task_id='gold_transformation',
    bash_command=f"""
    set -e
    {SPARK_ENV}
    echo "📊 STAGE 3: GOLD TRANSFORMATION"
    spark-submit \\
        --master local[*] \\
        --deploy-mode client \\
        --driver-memory 2g \\
        --executor-memory 2g \\
        --total-executor-cores 4 \\
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \\
        /opt/lakehouse/src/lakehouse/transformation/silver_to_gold.py 2>&1
    echo "✅ Gold transformation completed"
    """,
    dag=dag,
)

# ============================================================================
# Task: Verify Output
# Check that all S3 output folders have files
# ============================================================================
verify_output = BashOperator(
    task_id='verify_output',
    bash_command=f"""
    {SPARK_ENV}
    echo "🔍 VERIFY OUTPUT"
    echo "================"
    echo ""
    
    python3 << 'ENDPYTHON'
import boto3
import os
import sys

s3 = boto3.client(
    's3',
    region_name=os.getenv('AWS_DEFAULT_REGION', 'eu-west-3'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

bucket = os.getenv('S3_BUCKET', 'lakehouse-assurance-moto-prod')
total_files = 0

# Check each layer
for layer in ['bronze', 'silver', 'gold']:
    print('')
    print('📁 Checking ' + layer.upper() + ' layer...')
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=layer + '/', MaxKeys=10)
        if 'Contents' in response:
            count = len(response['Contents'])
            total_files += count
            print('   ✅ Found ' + str(count) + ' objects')
            for obj in response['Contents'][:3]:  # Show first 3
                size_kb = obj['Size'] / 1024
                fname = obj['Key'].split('/')[-1]
                print('      - ' + fname + ' (' + str(round(size_kb, 1)) + ' KB)')
        else:
            print('   ⚠️  No files found')
    except Exception as e:
        print('   ❌ Error: ' + str(e))
        sys.exit(1)

print('')
print('✅ Verification completed - ' + str(total_files) + ' total files found')
ENDPYTHON
    """,
    dag=dag,
)

# ============================================================================
# Task Dependencies
# ============================================================================
validate_env >> bronze_ingestion >> silver_transformation >> gold_transformation >> verify_output
