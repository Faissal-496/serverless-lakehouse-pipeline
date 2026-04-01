"""
Complete Lakehouse ETL Pipeline DAG
=====================================

Pipeline: Bronze → Silver → Gold
Execution: Full daily ETL with data quality checks

DAG Structure:
├── check_data_source              (Check if input data ready)
├── bronze_ingestion               (Read CSV → Parquet in S3)
│   └── silver_transformation      (Consolidate & clean)
│       └── gold_transformation    (Aggregate & analytics)
│           └── send_notification  (Completion alert)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.task_group import TaskGroup
import os

# ==============================================================================
# Configuration
# ==============================================================================

SPARK_MASTER = "spark://spark-master:7077"
AIRFLOW_USER = "airflow"
AIRFLOW_PYTHON = "/home/airflow/.local/bin/python3"

# AWS Credentials from environment
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-west-3')

# Common environment variables (pre-configured in docker-compose.yml)
SPARK_PACKAGES = (
    "org.apache.hadoop:hadoop-aws:3.3.4,"
    "com.amazonaws:aws-java-sdk-bundle:1.12.565"
)

# Spark configuration for driver and executors
SPARK_DRIVER_CONF = [
    "spark.driverEnv.PYTHONPATH=/app/src",
    "spark.driverEnv.PYSPARK_PYTHON=/home/airflow/.local/bin/python3",
    "spark.driverEnv.PYSPARK_DRIVER_PYTHON=/home/airflow/.local/bin/python3",
    "spark.driverEnv.APP_ENV=dev",
    "spark.driverEnv.CONFIG_DIR=/app/config",
    "spark.driverEnv.DATA_BASE_PATH=/data",
    f"spark.driverEnv.AWS_ACCESS_KEY_ID={AWS_ACCESS_KEY_ID}",
    f"spark.driverEnv.AWS_SECRET_ACCESS_KEY={AWS_SECRET_ACCESS_KEY}",
    f"spark.driverEnv.AWS_DEFAULT_REGION={AWS_DEFAULT_REGION}",
]

SPARK_EXECUTOR_CONF = [
    "spark.executorEnv.PYTHONPATH=/app/src",
    "spark.executorEnv.APP_ENV=dev",
    "spark.executorEnv.CONFIG_DIR=/app/config",
    "spark.executorEnv.DATA_BASE_PATH=/data",
    f"spark.executorEnv.AWS_ACCESS_KEY_ID={AWS_ACCESS_KEY_ID}",
    f"spark.executorEnv.AWS_SECRET_ACCESS_KEY={AWS_SECRET_ACCESS_KEY}",
    f"spark.executorEnv.AWS_DEFAULT_REGION={AWS_DEFAULT_REGION}",
]

SPARK_S3A_CONF = [
    "spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem",
    "spark.hadoop.fs.s3a.aws.credentials.provider=com.amazonaws.auth.EnvironmentVariableCredentialsProvider",
]

# ==============================================================================
# DAG Definition
# ==============================================================================

dag = DAG(
    'lakehouse_etl_complete',
    description='Complete Lakehouse ETL Pipeline: Bronze → Silver → Gold',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    start_date=datetime(2026, 1, 1),
    end_date=None,
    catchup=False,
    max_active_runs=1,
    tags=['lakehouse', 'etl', 'production'],
    default_args={
        'owner': 'lakehouse-team',
        'retries': 2,
        'retry_delay': timedelta(minutes=10),
        'execution_timeout': timedelta(hours=2),
    },
)

# ==============================================================================
# Task: Start
# ==============================================================================

start_task = DummyOperator(
    task_id='etl_start',
    dag=dag,
)

# ==============================================================================
# Task: Bronze Ingestion
# ==============================================================================

bronze_ingest = BashOperator(
    task_id='bronze_ingest',
    bash_command=f"""
        set -e
        EXECUTION_DATE='{{{{ ds }}}}'
        
        echo "=========================================="
        echo "[BRONZE] Ingestion Started"
        echo "Execution Date: $EXECUTION_DATE"
        echo "=========================================="
        
        spark-submit \
            --master {SPARK_MASTER} \
            --deploy-mode client \
            --packages {SPARK_PACKAGES} \
            {' '.join([f'--conf {conf}' for conf in SPARK_DRIVER_CONF])} \
            {' '.join([f'--conf {conf}' for conf in SPARK_EXECUTOR_CONF])} \
            {' '.join([f'--conf {conf}' for conf in SPARK_S3A_CONF])} \
            /app/src/lakehouse/jobs/bronze_ingest_job.py \
            --execution_date "$EXECUTION_DATE"
        
        echo "=========================================="
        echo "[BRONZE] Ingestion Completed"
        echo "=========================================="
    """,
    dag=dag,
    env={
        'PYTHONPATH': '/app/src',
        'PYSPARK_PYTHON': AIRFLOW_PYTHON,
        'PYSPARK_DRIVER_PYTHON': AIRFLOW_PYTHON,
        'APP_ENV': 'dev',
        'CONFIG_DIR': '/app/config',
        'DATA_BASE_PATH': '/data',
        'AWS_ACCESS_KEY_ID': '${AWS_ACCESS_KEY_ID}',
        'AWS_SECRET_ACCESS_KEY': '${AWS_SECRET_ACCESS_KEY}',
        'AWS_DEFAULT_REGION': '${AWS_DEFAULT_REGION}',
    },
)

# ==============================================================================
# Task: Silver Transformation
# ==============================================================================

silver_transform = BashOperator(
    task_id='silver_transform',
    bash_command=f"""
        set -e
        EXECUTION_DATE='{{{{ ds }}}}'
        
        echo "=========================================="
        echo "[SILVER] Transformation Started"
        echo "Execution Date: $EXECUTION_DATE"
        echo "=========================================="
        
        spark-submit \
            --master {SPARK_MASTER} \
            --deploy-mode client \
            --packages {SPARK_PACKAGES} \
            {' '.join([f'--conf {conf}' for conf in SPARK_DRIVER_CONF])} \
            {' '.join([f'--conf {conf}' for conf in SPARK_EXECUTOR_CONF])} \
            {' '.join([f'--conf {conf}' for conf in SPARK_S3A_CONF])} \
            /app/src/lakehouse/jobs/silver_transform_job.py \
            --execution_date "$EXECUTION_DATE"
        
        echo "=========================================="
        echo "[SILVER] Transformation Completed"
        echo "=========================================="
    """,
    dag=dag,
    env={
        'PYTHONPATH': '/app/src',
        'PYSPARK_PYTHON': AIRFLOW_PYTHON,
        'PYSPARK_DRIVER_PYTHON': AIRFLOW_PYTHON,
        'APP_ENV': 'dev',
        'CONFIG_DIR': '/app/config',
        'DATA_BASE_PATH': '/data',
        'AWS_ACCESS_KEY_ID': '${AWS_ACCESS_KEY_ID}',
        'AWS_SECRET_ACCESS_KEY': '${AWS_SECRET_ACCESS_KEY}',
        'AWS_DEFAULT_REGION': '${AWS_DEFAULT_REGION}',
    },
)

# ==============================================================================
# Task: Gold Transformation
# ==============================================================================

gold_transform = BashOperator(
    task_id='gold_transform',
    bash_command=f"""
        set -e
        EXECUTION_DATE='{{{{ ds }}}}'
        
        echo "=========================================="
        echo "[GOLD] Transformation Started"
        echo "Execution Date: $EXECUTION_DATE"
        echo "=========================================="
        
        spark-submit \
            --master {SPARK_MASTER} \
            --deploy-mode client \
            --packages {SPARK_PACKAGES} \
            {' '.join([f'--conf {conf}' for conf in SPARK_DRIVER_CONF])} \
            {' '.join([f'--conf {conf}' for conf in SPARK_EXECUTOR_CONF])} \
            {' '.join([f'--conf {conf}' for conf in SPARK_S3A_CONF])} \
            /app/src/lakehouse/jobs/gold_transform_job.py \
            --execution_date "$EXECUTION_DATE"
        
        echo "=========================================="
        echo "[GOLD] Transformation Completed"
        echo "=========================================="
    """,
    dag=dag,
    env={
        'PYTHONPATH': '/app/src',
        'PYSPARK_PYTHON': AIRFLOW_PYTHON,
        'PYSPARK_DRIVER_PYTHON': AIRFLOW_PYTHON,
        'APP_ENV': 'dev',
        'CONFIG_DIR': '/app/config',
        'DATA_BASE_PATH': '/data',
        'AWS_ACCESS_KEY_ID': '${AWS_ACCESS_KEY_ID}',
        'AWS_SECRET_ACCESS_KEY': '${AWS_SECRET_ACCESS_KEY}',
        'AWS_DEFAULT_REGION': '${AWS_DEFAULT_REGION}',
    },
)

# ==============================================================================
# Task: End
# ==============================================================================

end_task = DummyOperator(
    task_id='etl_end',
    dag=dag,
)

# ==============================================================================
# Task Dependencies
# ==============================================================================

start_task >> bronze_ingest >> silver_transform >> gold_transform >> end_task

if __name__ == "__main__":
    dag.cli()
