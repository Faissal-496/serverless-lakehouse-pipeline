#!/bin/bash
set -e

if [ -z "$SPARK_HOME" ]; then
  SPARK_HOME=$(find /opt -maxdepth 2 -name "spark-class" -type f 2>/dev/null | head -1 | xargs dirname | xargs dirname)
fi

 
echo "Starting Spark Worker"
echo "SPARK_HOME: $SPARK_HOME"
 

if [ ! -f "$SPARK_HOME/bin/spark-class" ]; then
  echo "ERROR: spark-class not found at $SPARK_HOME/bin/spark-class"
  exit 1
fi

chmod +x "$SPARK_HOME/bin/spark-class"

MASTER_HOST=${SPARK_MASTER_HOST:-spark-master}
MASTER_PORT=${SPARK_MASTER_PORT:-7077}
MASTER_URL="spark://${MASTER_HOST}:${MASTER_PORT}"

WORKER_PORT=${SPARK_WORKER_PORT:-7078}
WORKER_WEBUI_PORT=${SPARK_WORKER_WEBUI_PORT:-8081}
WORKER_CORES=${SPARK_WORKER_CORES:-2}
WORKER_MEMORY=${SPARK_WORKER_MEMORY:-2g}
# Use explicit hostname so the driver can route back to this worker
WORKER_HOST=${SPARK_LOCAL_IP:-$(hostname)}

echo "Worker Configuration:"
echo "  Host:      $WORKER_HOST"
echo "  RPC Port:  $WORKER_PORT"
echo "  WebUI:     $WORKER_WEBUI_PORT"
echo "  Cores:     $WORKER_CORES"
echo "  Memory:    $WORKER_MEMORY"
echo "  Master:    $MASTER_URL"
echo ""

exec "$SPARK_HOME/bin/spark-class" org.apache.spark.deploy.worker.Worker \
  --host "$WORKER_HOST" \
  --port "$WORKER_PORT" \
  --webui-port "$WORKER_WEBUI_PORT" \
  --cores "$WORKER_CORES" \
  --memory "$WORKER_MEMORY" \
  "$MASTER_URL"
