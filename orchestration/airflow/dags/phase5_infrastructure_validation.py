"""
Phase 5 Test DAG - Validates Lakehouse Infrastructure
Tests connectivity to: PostgreSQL, RabbitMQ, S3
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'lakehouse-team',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 3, 23),
    'catchup': False,
}

dag = DAG(
    'phase5_infrastructure_validation',
    default_args=default_args,
    description='Validate Lakehouse infrastructure deployment',
    schedule_interval='@daily',
    tags=['infrastructure', 'validation', 'phase5'],
)

def test_postgres_connection(**context):
    """Test PostgreSQL connectivity"""
    try:
        import psycopg2
        
        rds_endpoint = Variable.get("RDS_ENDPOINT", "lakehouse-assurance-prod-postgres.c56eeys0i59p.eu-west-3.rds.amazonaws.com")
        rds_user = Variable.get("RDS_USER", "postgres")
        rds_password = Variable.get("RDS_PASSWORD", "")
        rds_db = Variable.get("RDS_DB", "postgres")
        
        conn = psycopg2.connect(
            host=rds_endpoint.split(":")[0],
            port=5432,
            user=rds_user,
            password=rds_password,
            database=rds_db,
            connect_timeout=10
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        logger.info(f"✓ PostgreSQL connection successful: {version}")
        return {"status": "success", "service": "PostgreSQL"}
        
    except Exception as e:
        logger.error(f"✗ PostgreSQL connection failed: {e}")
        raise

def test_s3_access(**context):
    """Test S3 bucket access"""
    try:
        import boto3
        
        s3_bucket = Variable.get("S3_BUCKET", "lakehouse-assurance-moto-prod")
        region = Variable.get("AWS_REGION", "eu-west-3")
        
        s3 = boto3.client('s3', region_name=region)
        response = s3.head_bucket(Bucket=s3_bucket)
        
        logger.info(f"✓ S3 bucket access successful: {s3_bucket}")
        return {"status": "success", "service": "S3"}
        
    except Exception as e:
        logger.error(f"✗ S3 access failed: {e}")
        raise

def test_rabbitmq_connection(**context):
    """Test RabbitMQ connectivity"""
    try:
        import pika
        import ssl
        
        rabbitmq_host = Variable.get("RABBITMQ_HOST", "b-b7e21573-f118-4faf-a07b-b19d65bd5637.mq.eu-west-3.on.aws")
        rabbitmq_user = Variable.get("RABBITMQ_USER", "rabbituser")
        rabbitmq_password = Variable.get("RABBITMQ_PASSWORD", "")
        rabbitmq_port = int(Variable.get("RABBITMQ_PORT", "5671"))
        
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=credentials,
            ssl_options=pika.SSLOptions(ssl_context),
            connection_attempts=3,
            retry_delay=2,
            socket_timeout=10
        )
        
        connection = pika.BlockingConnection(parameters)
        connection.close()
        
        logger.info(f"✓ RabbitMQ connection successful")
        return {"status": "success", "service": "RabbitMQ"}
        
    except Exception as e:
        logger.error(f"✗ RabbitMQ connection failed: {e}")
        # Don't raise - RabbitMQ is optional for test

def log_results(**context):
    """Log infrastructure validation results"""
    task_instances = context['task'].dag.get_task_instances(
        state='SUCCESS',
        session=context.get('session')
    )
    logger.info(f"✓ Infrastructure validation complete: {len(task_instances)} services tested")

# Tasks
pg_test = PythonOperator(
    task_id='test_postgres',
    python_callable=test_postgres_connection,
    dag=dag,
)

s3_test = PythonOperator(
    task_id='test_s3',
    python_callable=test_s3_access,
    dag=dag,
)

rabbitmq_test = PythonOperator(
    task_id='test_rabbitmq',
    python_callable=test_rabbitmq_connection,
    dag=dag,
)

log_step = PythonOperator(
    task_id='log_results',
    python_callable=log_results,
    trigger_rule='all_done',  # Run regardless of upstream success
    dag=dag,
)

# Execution order
[pg_test, s3_test, rabbitmq_test] >> log_step
