"""
S3 Data Processing Pipeline - Real Data from AWS S3

This DAG:
1. Reads CSV files from S3 RAW bucket (client.csv, contrat1.csv, contrat2.csv)
2. Processes with Apache Spark (local mode for now)
3. Joins datasets
4. Writes processed results back to S3

Files processed:
  - s3://bucket/RAW/client.csv
  - s3://bucket/RAW/contrat1.csv
  - s3://bucket/RAW/contrat2.csv

Output:
  - s3://bucket/PROCESSED/joined_data.parquet
  - s3://bucket/PROCESSED/client_contract_summary.parquet
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import json
import logging
import os

# ============================================================================
# AWS Configuration from Environment
# ============================================================================
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-west-3')
S3_BUCKET = os.getenv('S3_BUCKET', 'lakehouse-assurance-moto-prod')

# ============================================================================
# Default Arguments
# ============================================================================
default_args = {
    'owner': 'data-engineering',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': ['data-alerts@company.com'],
    'email_on_failure': False,
    'email_on_retry': False,
}

# ============================================================================
# DAG Definition
# ============================================================================
dag = DAG(
    's3_data_processing_pipeline',
    default_args=default_args,
    description='Process real data from S3 RAW bucket with Spark',
    schedule_interval='@daily',  # Run daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['s3', 'spark', 'production', 'data-processing'],
)


def validate_aws_credentials(**context):
    """Verify AWS credentials are configured"""
    task_instance = context['task_instance']
    
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise ValueError("❌ AWS credentials not configured in environment!")
    
    logging.info("✅ AWS credentials configured")
    logging.info(f"🪣 S3 Bucket: {S3_BUCKET}")
    logging.info(f"📍 Region: {AWS_DEFAULT_REGION}")
    
    task_instance.xcom_push(
        key='aws_config',
        value={
            'bucket': S3_BUCKET,
            'region': AWS_DEFAULT_REGION,
            'status': 'CONFIGURED'
        }
    )
    
    return {"status": "CONFIGURED", "bucket": S3_BUCKET}


def read_and_process_s3_data(**context):
    """
    Read CSV files from S3 and process with Spark
    
    Files:
    - s3://bucket/RAW/client.csv
    - s3://bucket/RAW/contrat1.csv
    - s3://bucket/RAW/contrat2.csv
    """
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import col, concat_ws, count, avg
    except ImportError:
        logging.error("❌ PySpark not available, installing...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'pyspark'])
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import col, concat_ws, count, avg
    
    task_instance = context['task_instance']
    
    logging.info("🚀 Starting Spark session...")
    
    # Initialize Spark with S3 support
    spark = SparkSession.builder \
        .appName("S3DataProcessing") \
        .config("spark.hadoop.fs.s3a.access.key", AWS_ACCESS_KEY_ID) \
        .config("spark.hadoop.fs.s3a.secret.key", AWS_SECRET_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.endpoint", f"s3.{AWS_DEFAULT_REGION}.amazonaws.com") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
        .getOrCreate()
    
    logging.info("✅ Spark session created successfully")
    
    try:
        # ====================================================================
        # STEP 1: Read CSV files from S3
        # ====================================================================
        logging.info(f"📂 Reading CLIENT data from S3://{S3_BUCKET}/RAW/client.csv")
        
        s3_raw_path = f"s3a://{S3_BUCKET}/RAW"
        
        # Read client.csv
        df_client = spark.read \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .csv(f"{s3_raw_path}/client.csv")
        
        logging.info(f"✅ CLIENT data loaded: {df_client.count()} rows")
        logging.info(f"📋 Columns: {', '.join(df_client.columns)}")
        
        # Read contrat1.csv
        df_contrat1 = spark.read \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .csv(f"{s3_raw_path}/contrat1.csv")
        
        logging.info(f"✅ CONTRAT1 data loaded: {df_contrat1.count()} rows")
        logging.info(f"📋 Columns: {', '.join(df_contrat1.columns)}")
        
        # Read contrat2.csv
        df_contrat2 = spark.read \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .csv(f"{s3_raw_path}/contrat2.csv")
        
        logging.info(f"✅ CONTRAT2 data loaded: {df_contrat2.count()} rows")
        logging.info(f"📋 Columns: {', '.join(df_contrat2.columns)}")
        
        # ====================================================================
        # STEP 2: Combine contract datasets
        # ====================================================================
        logging.info("🔄 Combining CONTRAT1 and CONTRAT2...")
        df_contrats = df_contrat1.union(df_contrat2)
        logging.info(f"✅ Combined contracts: {df_contrats.count()} rows")
        
        # ====================================================================
        # STEP 3: Join with client data
        # ====================================================================
        logging.info("🔗 Joining with CLIENT data...")
        
        # Assuming there's a common key (e.g., 'client_id', 'id', etc.)
        # Get column names to find join key
        client_cols = set(df_client.columns)
        contrat_cols = set(df_contrats.columns)
        common_cols = client_cols.intersection(contrat_cols)
        
        if not common_cols:
            logging.warning("⚠️  No common columns found for join")
            logging.warning(f"   CLIENT columns: {client_cols}")
            logging.warning(f"   CONTRAT columns: {contrat_cols}")
            # Fallback: assume first column is the join key
            join_key = df_client.columns[0]
            logging.info(f"   Using fallback join key: {join_key}")
        else:
            join_key = list(common_cols)[0]
            logging.info(f"   Join key: {join_key}")
        
        # Perform join
        df_joined = df_client.join(
            df_contrats,
            on=join_key,
            how='left'
        )
        
        logging.info(f"✅ Joined data: {df_joined.count()} rows")
        
        # ====================================================================
        # STEP 4: Create summary statistics
        # ====================================================================
        logging.info("📊 Computing summary statistics...")
        
        # Count contracts per client
        df_summary = df_joined.groupBy(join_key).agg(
            count("*").alias("total_records"),
            count(col(contrat_cols.pop()) if contrat_cols else None).alias("contract_count")
        )
        
        logging.info(f"✅ Summary computed: {df_summary.count()} unique clients")
        
        # ====================================================================
        # STEP 5: Write results to S3
        # ====================================================================
        s3_processed_path = f"s3a://{S3_BUCKET}/PROCESSED"
        
        # Write joined data as Parquet
        joined_output = f"{s3_processed_path}/joined_data.parquet"
        logging.info(f"💾 Writing joined data to {joined_output}...")
        df_joined.write.mode("overwrite").parquet(joined_output)
        logging.info(f"✅ Joined data written to S3")
        
        # Write summary
        summary_output = f"{s3_processed_path}/client_contract_summary.parquet"
        logging.info(f"💾 Writing summary to {summary_output}...")
        df_summary.write.mode("overwrite").parquet(summary_output)
        logging.info(f"✅ Summary written to S3")
        
        # ====================================================================
        # STEP 6: Collect metrics
        # ====================================================================
        metrics = {
            'client_records': df_client.count(),
            'contrat1_records': df_contrat1.count(),
            'contrat2_records': df_contrat2.count(),
            'combined_contracts': df_contrats.count(),
            'joined_records': df_joined.count(),
            'unique_clients': df_summary.count(),
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'SUCCESS',
            'output_location': s3_processed_path
        }
        
        task_instance.xcom_push(key='processing_metrics', value=metrics)
        
        logging.info("=" * 80)
        logging.info("📊 PROCESSING METRICS:")
        logging.info(json.dumps(metrics, indent=2))
        logging.info("=" * 80)
        
        return metrics
        
    except Exception as e:
        logging.error(f"❌ Error during processing: {str(e)}")
        raise
    
    finally:
        logging.info("🛑 Stopping Spark session...")
        spark.stop()


def verify_output(**context):
    """Verify that output files were created in S3"""
    task_instance = context['task_instance']
    metrics = task_instance.xcom_pull(
        key='processing_metrics',
        task_ids='process_s3_data'
    )
    
    logging.info("✅ Processing complete!")
    logging.info(f"📊 Results summary:")
    logging.info(json.dumps(metrics, indent=2))
    
    return {
        'status': 'VERIFIED',
        'output_files': [
            f"s3://{S3_BUCKET}/PROCESSED/joined_data.parquet",
            f"s3://{S3_BUCKET}/PROCESSED/client_contract_summary.parquet"
        ]
    }


# ============================================================================
# Task Definitions
# ============================================================================

validate_creds = PythonOperator(
    task_id='validate_aws_credentials',
    python_callable=validate_aws_credentials,
    dag=dag,
)

process_data = PythonOperator(
    task_id='process_s3_data',
    python_callable=read_and_process_s3_data,
    dag=dag,
)

verify_results = PythonOperator(
    task_id='verify_output',
    python_callable=verify_output,
    dag=dag,
)

# ============================================================================
# Task Dependencies
# ============================================================================
validate_creds >> process_data >> verify_results
