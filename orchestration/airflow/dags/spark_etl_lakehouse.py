"""
Spark ETL Pipeline - Bronze → Silver → Gold

Real enterprise data pipeline using Apache Spark:
1. Bronze: Ingest raw CSV from local filesystem to S3
2. Silver: Transform & standardize data, join datasets
3. Gold: Create analytical tables and KPIs

Uses validated transformation scripts:
- src/lakehouse/ingestion/bronze_ingest.py
- src/lakehouse/transformation/bronze_to_silver.py
- src/lakehouse/transformation/silver_to_gold.py
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import json
import logging
import os
import sys

# Add source path to Python path
sys.path.insert(0, '/opt/airflow/dags/repo/src')

# ============================================================================
# AWS Configuration from Environment
# ============================================================================
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-west-3')
S3_BUCKET = os.getenv('S3_BUCKET', 'lakehouse-assurance-moto-prod')
APP_ENV = os.getenv('APP_ENV', 'dev')

# ============================================================================
# Default Arguments
# ============================================================================
default_args = {
    'owner': 'lakehouse-team',
    'retries':  2,
    'retry_delay': timedelta(minutes=10),
    'email_on_failure': False,
    'email_on_retry': False,
}

# ============================================================================
# DAG Definition
# ============================================================================
dag = DAG(
    'spark_etl_lakehouse',
    default_args=default_args,
    description='Spark ETL: Bronze → Silver → Gold transformation pipeline',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['spark', 'etl', 'lakehouse', 'production'],
)


def validate_environment(**context):
    """Validate AWS credentials and Spark setup"""
    logging.info("=" * 80)
    logging.info("SPARK ETL PIPELINE - ENVIRONMENT VALIDATION")
    logging.info("=" * 80)
    
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise ValueError("❌ AWS credentials not configured in environment!")
    
    logging.info(f"✅ AWS Credentials: CONFIGURED")
    logging.info(f"✅ S3 Bucket: {S3_BUCKET}")
    logging.info(f"✅ Region: {AWS_DEFAULT_REGION}")
    logging.info(f"✅ Environment: {APP_ENV}")
    
    # Set Spark environment variables
    os.environ['AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
    os.environ['AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_ACCESS_KEY
    os.environ['AWS_DEFAULT_REGION'] = AWS_DEFAULT_REGION
    os.environ['S3_BUCKET'] = S3_BUCKET
    
    context['task_instance'].xcom_push(
        key='spark_config',
        value={
            'bucket': S3_BUCKET,
            'region': AWS_DEFAULT_REGION,
            'env': APP_ENV,
            'status': 'VALIDATED'
        }
    )
    
    return {"status": "VALIDATED"}


def run_bronze_ingestion(**context):
    """
    Stage 1: Bronze Layer Ingestion
    Ingest raw CSV files from local filesystem to S3 Parquet
    
    Input: /opt/lakehouse/data/*.csv
    Output: s3://bucket/bronze/
    """
    from lakehouse.ingestion.bronze_ingest import run as run_bronze
    from lakehouse.paths import PathResolver
    from lakehouse.utils.spark_session import get_spark_session
    
    logging.info("=" * 80)
    logging.info("STAGE 1: BRONZE INGESTION - CSV → S3 Parquet")
    logging.info("=" * 80)
    
    spark = None
    try:
        # Create Spark session with S3A configuration
        spark = get_spark_session("BronzeIngestion")
        logging.info(f"✅ Spark Session created: {spark.version}")
        
        # Set AWS credentials in Spark config
        spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.access.key", AWS_ACCESS_KEY_ID)
        spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.secret.key", AWS_SECRET_ACCESS_KEY)
        
        # Initialize path resolver
        resolver = PathResolver()
        
        # Execute bronze ingestion
        run_bronze(spark, resolver)
        
        logging.info("✅ Bronze ingestion completed successfully")
        
        context['task_instance'].xcom_push(
            key='bronze_status',
            value={'stage': 'BRONZE', 'status': 'SUCCESS'}
        )
        
        return {'stage': 'BRONZE', 'status': 'SUCCESS'}
        
    except Exception as e:
        logging.error(f"❌ Bronze ingestion failed: {str(e)}", exc_info=True)
        raise
    finally:
        if spark:
            logging.info("Stopping Spark session...")
            spark.stop()


def run_silver_transformation(**context):
    """
    Stage 2: Silver Layer Transformation
    - Consolidate contract data
    - Apply type casting and null handling
    - Decode business variables
    - Join with client data
    
    Input: s3://bucket/bronze/
    Output: s3://bucket/silver/
    """
    from lakehouse.transformation.bronze_to_silver import run as run_silver
    from lakehouse.paths import PathResolver
    from lakehouse.utils.spark_session import get_spark_session
    
    logging.info("=" * 80)
    logging.info("STAGE 2: SILVER TRANSFORMATION - Data Standardization")
    logging.info("=" * 80)
    
    spark = None
    try:
        spark = get_spark_session("BronzeToSilver")
        logging.info(f"✅ Spark Session created: {spark.version}")
        
        # Set AWS credentials
        spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.access.key", AWS_ACCESS_KEY_ID)
        spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.secret.key", AWS_SECRET_ACCESS_KEY)
        
        resolver = PathResolver()
        
        # Execute silver transformation
        run_silver(spark, resolver)
        
        logging.info("✅ Silver transformation completed successfully")
        
        context['task_instance'].xcom_push(
            key='silver_status',
            value={'stage': 'SILVER', 'status': 'SUCCESS'}
        )
        
        return {'stage': 'SILVER', 'status': 'SUCCESS'}
        
    except Exception as e:
        logging.error(f"❌ Silver transformation failed: {str(e)}", exc_info=True)
        raise
    finally:
        if spark:
            logging.info("Stopping Spark session...")
            spark.stop()


def run_gold_transformation(**context):
    """
    Stage 3: Gold Layer Transformation
    - Create analytical datasets
    - Generate KPI dashboard
    - Aggregate business metrics
    
    Input: s3://bucket/silver/
    Output: s3://bucket/gold/
    """
    from lakehouse.transformation.silver_to_gold import run as run_gold
    from lakehouse.paths import PathResolver
    from lakehouse.utils.spark_session import get_spark_session
    
    logging.info("=" * 80)
    logging.info("STAGE 3: GOLD TRANSFORMATION - Analytics & KPIs")
    logging.info("=" * 80)
    
    spark = None
    try:
        spark = get_spark_session("SilverToGold")
        logging.info(f"✅ Spark Session created: {spark.version}")
        
        # Set AWS credentials
        spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.access.key", AWS_ACCESS_KEY_ID)
        spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.secret.key", AWS_SECRET_ACCESS_KEY)
        
        resolver = PathResolver()
        
        # Execute gold transformation
        run_gold(spark, resolver)
        
        logging.info("✅ Gold transformation completed successfully")
        
        context['task_instance'].xcom_push(
            key='gold_status',
            value={'stage': 'GOLD', 'status': 'SUCCESS'}
        )
        
        return {'stage': 'GOLD', 'status': 'SUCCESS'}
        
    except Exception as e:
        logging.error(f"❌ Gold transformation failed: {str(e)}", exc_info=True)
        raise
    finally:
        if spark:
            logging.info("Stopping Spark session...")
            spark.stop()


def verify_pipeline_output(**context):
    """
    Verify all pipeline outputs were created successfully
    """
    import boto3
    
    logging.info("=" * 80)
    logging.info("PIPELINE VERIFICATION")
    logging.info("=" * 80)
    
    s3_client = boto3.client(
        's3',
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    
    try:
        layers = ['bronze', 'silver', 'gold']
        results = {}
        
        for layer in layers:
            try:
                response = s3_client.list_objects_v2(
                    Bucket=S3_BUCKET,
                    Prefix=layer + '/'
                )
                
                if 'Contents' in response:
                    files = [obj['Key'] for obj in response['Contents']]
                    results[layer] = {
                        'status': 'OK',
                        'count': len(files),
                        'files': files
                    }
                    logging.info(f"✅ {layer.upper()} layer: {len(files)} files")
                else:
                    results[layer] = {'status': 'EMPTY', 'count': 0}
                    logging.warning(f"⚠️  {layer.upper()} layer: NO FILES")
            except Exception as e:
                results[layer] = {'status': 'ERROR', 'error': str(e)}
                logging.error(f"❌ {layer.upper()} layer error: {str(e)}")
        
        logging.info("=" * 80)
        logging.info("PIPELINE SUMMARY")
        logging.info("=" * 80)
        logging.info(json.dumps(results, indent=2))
        
        context['task_instance'].xcom_push(
            key='verification_results',
            value=results
        )
        
        return {'verification': 'COMPLETE', 'results': results}
        
    except Exception as e:
        logging.error(f"❌ Verification failed: {str(e)}", exc_info=True)
        raise


# ============================================================================
# Task Definitions
# ============================================================================

validate_task = PythonOperator(
    task_id='validate_environment',
    python_callable=validate_environment,
    dag=dag,
)

bronze_task = PythonOperator(
    task_id='bronze_ingestion',
    python_callable=run_bronze_ingestion,
    dag=dag,
)

silver_task = PythonOperator(
    task_id='silver_transformation',
    python_callable=run_silver_transformation,
    dag=dag,
)

gold_task = PythonOperator(
    task_id='gold_transformation',
    python_callable=run_gold_transformation,
    dag=dag,
)

verify_task = PythonOperator(
    task_id='verify_output',
    python_callable=verify_pipeline_output,
    dag=dag,
)

# ============================================================================
# Task Dependencies (Sequential Pipeline)
# ============================================================================
# Environment → Bronze → Silver → Gold → Verify
validate_task >> bronze_task >> silver_task >> gold_task >> verify_task
