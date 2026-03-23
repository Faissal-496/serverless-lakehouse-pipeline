#!/bin/bash
set -e

AIRFLOW_HOME=${AIRFLOW_HOME:-/opt/airflow}
AIRFLOW_INIT=${AIRFLOW_INIT:-false}
AIRFLOW_CMD=${1:-}

# Initialize Airflow database on first run
if [[ "$AIRFLOW_INIT" == "true" && "$AIRFLOW_CMD" == "webserver" && ! -f "$AIRFLOW_HOME/.airflow_initialized" ]]; then
    echo "Initializing Airflow database..."
    airflow db migrate
    
    if [[ -z "$AIRFLOW__CORE__LOAD_EXAMPLES" ]] || [[ "$AIRFLOW__CORE__LOAD_EXAMPLES" == "False" ]]; then
        # Create default admin user if needed
        if ! airflow users list | grep -q admin; then
            airflow users create \
                --username admin \
                --firstname Admin \
                --lastname User \
                --role Admin \
                --email admin@example.com \
                --password admin || true
        fi
    fi
    
    touch "$AIRFLOW_HOME/.airflow_initialized"
    echo "Airflow initialization complete"
fi

echo "Starting Airflow $1..."
exec airflow "$@"
