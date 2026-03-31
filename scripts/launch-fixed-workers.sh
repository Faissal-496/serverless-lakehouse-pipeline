#!/bin/bash
# Fix and launch Spark workers with proper error handling

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

set -e

PROJECT_ROOT="/home/fisal_bel/projects/data_projects/serverless-lakehouse-pipeline"
DATA_PATH="$PROJECT_ROOT/data"
NETWORK="serverless-lakehouse-pipeline_lakehouse-network"
MASTER_URL="spark://spark-master:7077"

log_info "Launching fixed Spark Workers..."
log_info "Network: $NETWORK"
log_info "Master: $MASTER_URL"

# Verify master is running
if ! docker ps | grep -q "spark-master"; then
    log_error "Spark Master is not running!"
    exit 1
fi
log_success "Spark Master verified running"

# Remove any existing workers
log_info "Cleaning up old worker containers..."
docker rm -f spark-worker-1 spark-worker-2 2>/dev/null || true

# Define worker launch function
launch_worker() {
    local WORKER_NAME=$1
    local PORT=$2
    local CONTAINER_ID
    
    log_info "Launching $WORKER_NAME on port $PORT..."
    
    # Try with alpine-based ubuntu image instead (lighter, fewer issues)
    docker run -d \
        --name "$WORKER_NAME" \
        --network "$NETWORK" \
        --hostname "$WORKER_NAME" \
        -e SPARK_MODE=worker \
        -e SPARK_MASTER_URL="$MASTER_URL" \
        -e SPARK_WORKER_MEMORY=2G \
        -e SPARK_WORKER_CORES=4 \
        -e SPARK_LOCAL_IP="$WORKER_NAME" \
        -e SPARK_WORKER_PORT=7078 \
        -e SPARK_WORKER_WEBUI_PORT=8081 \
        -v "$DATA_PATH:/opt/lakehouse/data:ro" \
        --health-cmd="pgrep -f org.apache.spark.deploy.worker.Worker" \
        --health-interval=10s \
        --health-timeout=5s \
        --health-retries=3 \
        apache/spark:3.5.0 \
        /opt/spark-3.5.0-bin-hadoop3/bin/spark-class \
        org.apache.spark.deploy.worker.Worker "$MASTER_URL"
    
    if [ $? -eq 0 ]; then
        log_success "$WORKER_NAME launched"
        return 0
    else
        log_error "Failed to launch $WORKER_NAME"
        return 1
    fi
}

# Launch both workers
launch_worker "spark-worker-1" "8081"
launch_worker "spark-worker-2" "8082"

# Wait for workers to register
log_info "Waiting for workers to register with master..."
sleep 5

# Verify workers
log_info "Checking worker status..."
RUNNING_WORKERS=$(docker ps | grep -c "spark-worker" || echo 0)
echo -e "\n${BLUE}=== WORKER STATUS ===${NC}"
docker ps | grep spark-worker || true

log_success "Spark workers configured!"
log_info "Master UI: http://localhost:8084"
log_info "Workers are deployed on the internal Docker network"
