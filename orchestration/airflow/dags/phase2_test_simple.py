"""
Phase 2: Simple test DAG - verify Airflow HA task execution
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'data-eng',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

dag = DAG(
    'phase2_test_simple',
    default_args=default_args,
    description='Phase 2 Test: Simple task execution',
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['phase2', 'test'],
)

task1 = BashOperator(
    task_id='task_test_1',
    bash_command='echo "✅ Task 1 executed at $(date)" && sleep 5',
    dag=dag,
)

task2 = BashOperator(
    task_id='task_test_2',
    bash_command='echo "✅ Task 2 executed at $(date)"',
    dag=dag,
)

task1 >> task2
