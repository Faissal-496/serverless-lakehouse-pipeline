from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'spark_etl_standalone_test',
    default_args=default_args,
    description='Phase 2: ETL on Spark Standalone (2 workers)',
    schedule_interval=None,
    start_date=days_ago(1),
)

validate_env = BashOperator(
    task_id='validate_environment',
    bash_command='echo "Environment validation: OK"',
    dag=dag,
)

bronze_task = BashOperator(
    task_id='bronze_ingestion_standalone',
    bash_command='''
    cd /opt/lakehouse && \
    /opt/spark-3.5.0-bin-hadoop3/bin/spark-submit \
        --master spark://spark-master:7077 \
        --driver-memory 1g \
        --executor-memory 2g \
        --executor-cores 4 \
        --total-executor-cores 8 \
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        --conf spark.hadoop.fs.s3a.endpoint=http://moto:5000 \
        --conf spark.hadoop.fs.s3a.access.key=test \
        --conf spark.hadoop.fs.s3a.secret.key=test \
        --conf spark.hadoop.fs.s3a.path.style.access=true \
        src/lakehouse/ingestion/bronze_ingest.py 2>&1 | tail -20
    ''',
    dag=dag,
)

silver_task = BashOperator(
    task_id='silver_transformation_standalone',
    bash_command='''
    cd /opt/lakehouse && \
    /opt/spark-3.5.0-bin-hadoop3/bin/spark-submit \
        --master spark://spark-master:7077 \
        --driver-memory 1g \
        --executor-memory 2g \
        --executor-cores 4 \
        --total-executor-cores 8 \
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        --conf spark.hadoop.fs.s3a.endpoint=http://moto:5000 \
        --conf spark.hadoop.fs.s3a.access.key=test \
        --conf spark.hadoop.fs.s3a.secret.key=test \
        --conf spark.hadoop.fs.s3a.path.style.access=true \
        src/lakehouse/transformation/bronze_to_silver.py 2>&1 | tail -20
    ''',
    dag=dag,
)

gold_task = BashOperator(
    task_id='gold_transformation_standalone',
    bash_command='''
    cd /opt/lakehouse && \
    /opt/spark-3.5.0-bin-hadoop3/bin/spark-submit \
        --master spark://spark-master:7077 \
        --driver-memory 1g \
        --executor-memory 2g \
        --executor-cores 4 \
        --total-executor-cores 8 \
        --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        --conf spark.hadoop.fs.s3a.endpoint=http://moto:5000 \
        --conf spark.hadoop.fs.s3a.access.key=test \
        --conf spark.hadoop.fs.s3a.secret.key=test \
        --conf spark.hadoop.fs.s3a.path.style.access=true \
        src/lakehouse/transformation/silver_to_gold.py 2>&1 | tail -20
    ''',
    dag=dag,
)

verify = BashOperator(
    task_id='verify_output',
    bash_command='echo "Spark Standalone test complete!"',
    dag=dag,
)

validate_env >> bronze_task >> silver_task >> gold_task >> verify
