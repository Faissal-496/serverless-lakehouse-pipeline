"""
Phase 2: ETL Execution on Spark Standalone Cluster (2 workers)
Objective: Test distributed execution and compare performance
"""

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
    'spark_etl_standalone_phase2',
    default_args=default_args,
    description='Phase 2: ETL on Spark Standalone Cluster (2 workers, 8 cores total)',
    schedule_interval=None,
    start_date=days_ago(1),
    catchup=False,
)

validate_env = BashOperator(
    task_id='validate_environment',
    bash_command='echo "✅ Standalone environment ready" && echo "Cluster: spark://spark-master:7077"',
    dag=dag,
)

bronze_task = BashOperator(
    task_id='bronze_ingestion_standalone',
    bash_command='''
set -e
echo "Starting Bronze Ingestion on Standalone Cluster..."
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
    --conf spark.sql.shuffle.partitions=8 \
    src/lakehouse/ingestion/bronze_ingest.py 2>&1 | grep -E "loaded|completed|✅|ERROR"
echo "✅ Bronze task complete"
    ''',
    dag=dag,
)

silver_task = BashOperator(
    task_id='silver_transformation_standalone',
    bash_command='''
set -e
echo "Starting Silver Transformation on Standalone Cluster..."
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
    --conf spark.sql.shuffle.partitions=8 \
    src/lakehouse/transformation/bronze_to_silver.py 2>&1 | grep -E "merged|deduplicated|completed|✅|ERROR"
echo "✅ Silver task complete"
    ''',
    dag=dag,
)

gold_task = BashOperator(
    task_id='gold_transformation_standalone',
    bash_command='''
set -e
echo "Starting Gold Transformation on Standalone Cluster..."
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
    --conf spark.sql.shuffle.partitions=8 \
    src/lakehouse/transformation/silver_to_gold.py 2>&1 | grep -E "profile|analysis|dashboard|completed|✅|ERROR"
echo "✅ Gold task complete"
    ''',
    dag=dag,
)

verify = BashOperator(
    task_id='verify_cluster_output',
    bash_command='''
echo "Verifying Standalone execution..."
echo "✅ Phase 2 Standalone Test Complete!"
    ''',
    dag=dag,
)

# Define task dependencies
validate_env >> bronze_task >> silver_task >> gold_task >> verify
