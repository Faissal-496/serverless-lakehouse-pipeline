"""
Simplified S3 Data Processing Pipeline - Pandas-based (Fast)

This DAG:
1. Reads CSV files from S3 RAW bucket using Pandas/Boto3
2. Processes with Pandas (lightweight,  fast)
3. Joins datasets
4. Writes processed results back to S3 as CSV

No Java/Spark dependencies - pure Python stack.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
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
    'email_on_failure': False,
    'email_on_retry': False,
}

# ============================================================================
# DAG Definition
# ============================================================================
dag = DAG(
    's3_data_processing_simple',
    default_args=default_args,
    description='Process real data from S3 with Pandas (no Spark)',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['s3', 'pandas', 'data-processing'],
)


def validate_aws_credentials(**context):
    """Verify AWS credentials are configured"""
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise ValueError("❌ AWS credentials not configured in environment!")
    
    logging.info("✅ AWS credentials configured")
    logging.info(f"🪣 S3 Bucket: {S3_BUCKET}")
    logging.info(f"📍 Region: {AWS_DEFAULT_REGION}")
    
    context['task_instance'].xcom_push(
        key='aws_config',
        value={'bucket': S3_BUCKET, 'region': AWS_DEFAULT_REGION, 'status': 'OK'}
    )
    return {"status": "OK"}


def process_s3_data_pandas(**context):
    """
    Read and process CSV files from S3 using Pandas
    """
    import pandas as pd
    import boto3
    
    logging.info("🚀 Starting S3 data processing with Pandas...")
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    
    try:
        logging.info("📥 Reading CSV files from S3...")
        
        # Read client.csv
        obj_client = s3_client.get_object(Bucket=S3_BUCKET, Key='RAW/client.csv')
        df_client = pd.read_csv(obj_client['Body'])
        logging.info(f"✅ Loaded client.csv: {len(df_client)} rows")
        logging.info(f"   Columns: {list(df_client.columns)}")
        
        # Read contrat1.csv
        obj_c1 = s3_client.get_object(Bucket=S3_BUCKET, Key='RAW/contrat1.csv')
        df_contrat1 = pd.read_csv(obj_c1['Body'])
        logging.info(f"✅ Loaded contrat1.csv: {len(df_contrat1)} rows")
        logging.info(f"   Columns: {list(df_contrat1.columns)}")
        
        # Read contrat2.csv
        obj_c2 = s3_client.get_object(Bucket=S3_BUCKET, Key='RAW/contrat2.csv')
        df_contrat2 = pd.read_csv(obj_c2['Body'])
        logging.info(f"✅ Loaded contrat2.csv: {len(df_contrat2)} rows")
        logging.info(f"   Columns: {list(df_contrat2.columns)}")
        
        # ================================================================
        # Data Processing
        # ================================================================
        logging.info("🔗 Processing datasets...")
        
        # Combine contracts
        df_contracts = pd.concat([df_contrat1, df_contrat2], ignore_index=True)
        logging.info(f"✅ Combined contracts: {len(df_contracts)} rows")
        
        # Find common join key
        common_cols = list(set(df_client.columns) & set(df_contracts.columns))
        
        if common_cols:
            join_key = common_cols[0]
            logging.info(f"🔑 Joining on key: '{join_key}'")
            df_joined = df_client.merge(df_contracts, on=join_key, how='inner')
            logging.info(f"✅ Joined result: {len(df_joined)} rows")
        else:
            logging.warning("⚠️ No common columns, concatenating instead")
            df_joined = pd.concat([df_client, df_contracts], axis=1)
        
        # ================================================================
        # Summary Stats
        # ================================================================
        summary = {
            'client_rows': len(df_client),
            'contrat1_rows': len(df_contrat1),
            'contrat2_rows': len(df_contrat2),
            'total_contract_rows': len(df_contracts),
            'joined_rows': len(df_joined),
            'join_key': common_cols[0] if common_cols else 'N/A',
            'timestamp': pd.Timestamp.now().isoformat(),
            'process': 'pandas-s3'
        }
        
        logging.info(f"📊 Summary: {json.dumps(summary, indent=2)}")
        
        # ================================================================
        # Write Results
        # ================================================================
        logging.info("💾 Writing results to S3...")
        
        # Write joined data
        csv_data = df_joined.to_csv(index=False)
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key='PROCESSED/joined_data.csv',
            Body=csv_data.encode('utf-8')
        )
        logging.info("✅ Uploaded joined_data.csv")
        
        # Write summary
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key='PROCESSED/summary.json',
            Body=json.dumps(summary, indent=2).encode('utf-8')
        )
        logging.info("✅ Uploaded summary.json")
        
        # Store metrics
        context['task_instance'].xcom_push(key='metrics', value=summary)
        
        return summary
        
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        raise


def verify_output(**context):
    """Verify output files were created"""
    import boto3
    
    s3_client = boto3.client(
        's3',
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    
    logging.info("✅ Data processing complete!")
    logging.info("📁 Checking output in S3...")
    
    try:
        # List processed files
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix='PROCESSED/')
        
        if 'Contents' in response:
            files = [obj['Key'] for obj in response['Contents']]
            logging.info(f"📊 Output files created:")
            for f in files:
                logging.info(f"   ✅ {f}")
        
        # Get metrics from upstream task
        metrics = context['task_instance'].xcom_pull(key='metrics', task_ids='process_data')
        logging.info(f"📈 Processing metrics: {json.dumps(metrics, indent=2)}")
        
        return {'status': 'VERIFIED', 'files': files}
        
    except Exception as e:
        logging.error(f"❌ Verification error: {str(e)}")
        raise


# ============================================================================
# Task Definitions
# ============================================================================

validate_task = PythonOperator(
    task_id='validate_credentials',
    python_callable=validate_aws_credentials,
    dag=dag,
)

process_task = PythonOperator(
    task_id='process_data',
    python_callable=process_s3_data_pandas,
    dag=dag,
)

verify_task = PythonOperator(
    task_id='verify_output',
    python_callable=verify_output,
    dag=dag,
)

# ============================================================================
# Dependencies
# ============================================================================
validate_task >> process_task >> verify_task
