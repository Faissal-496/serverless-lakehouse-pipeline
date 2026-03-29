#!/bin/bash
# Start Spark Standalone cluster locally (simulates EMR Serverless)
# Usage: ./scripts/start_spark_standalone.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SPARK_HOME="${SPARK_HOME:-/opt/spark-3.5.0-bin-hadoop3}"

echo "=========================================="
echo "🚀 Starting Spark Standalone Cluster"
echo "=========================================="
echo ""

# Check if Spark is installed
if [ ! -d "$SPARK_HOME" ]; then
    echo "❌ Spark not found at $SPARK_HOME"
    echo "   Please set SPARK_HOME environment variable"
    exit 1
fi

# Create work directories
mkdir -p /tmp/spark-master
mkdir -p /tmp/spark-worker-1
mkdir -p /tmp/spark-worker-2
mkdir -p /tmp/spark-events
mkdir -p /tmp/spark-logs

cd "$SPARK_HOME"

# Start Master
echo "Starting Master node..."
export SPARK_NO_DAEMONIZE=1
./sbin/start-master.sh \
  --host 127.0.0.1 \
  --port 7077 \
  --webui-port 8081 &

MASTER_PID=$!
echo "✓ Master started (PID: $MASTER_PID)"
sleep 3

# Start Worker 1
echo "Starting Worker 1 (4 cores, 2GB memory)..."
./sbin/start-worker.sh \
  spark://127.0.0.1:7077 \
  --cores 4 \
  --memory 2G \
  --webui-port 8082 &

WORKER1_PID=$!
echo "✓ Worker 1 started (PID: $WORKER1_PID)"
sleep 2

# Start Worker 2
echo "Starting Worker 2 (4 cores, 2GB memory)..."
./sbin/start-worker.sh \
  spark://127.0.0.1:7077 \
  --cores 4 \
  --memory 2G \
  --webui-port 8083 &

WORKER2_PID=$!
echo "✓ Worker 2 started (PID: $WORKER2_PID)"
sleep 2

echo ""
echo "=========================================="
echo "✅ Spark Standalone Cluster Started!"
echo "=========================================="
echo ""
echo "Access the cluster at:"
echo "  Master UI:  http://127.0.0.1:8081"
echo "  Worker 1 UI: http://127.0.0.1:8082"
echo "  Worker 2 UI: http://127.0.0.1:8083"
echo ""
echo "Cluster Details:"
echo "  Master: spark://127.0.0.1:7077"
echo "  Workers: 2 nodes × 4 cores × 2GB = 8 cores, 4GB total"
echo "  Total Parallelism: 8 concurrent tasks"
echo ""
echo "To submit jobs:"
echo "  spark-submit --master spark://127.0.0.1:7077 ..."
echo ""
echo "To stop the cluster, run:"
echo "  $SPARK_HOME/sbin/stop-all.sh"
echo ""

# Save PIDs for cleanup
echo "$MASTER_PID" > /tmp/spark-master.pid
echo "$WORKER1_PID" > /tmp/spark-worker-1.pid
echo "$WORKER2_PID" > /tmp/spark-worker-2.pid

wait
