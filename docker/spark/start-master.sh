#!/bin/bash
set -e

if [ -z "$SPARK_HOME" ]; then
  SPARK_HOME=$(find /opt -maxdepth 2 -name "spark-class" -type f 2>/dev/null | head -1 | xargs dirname | xargs dirname)
fi

 
echo "Starting Spark Master"
echo "SPARK_HOME: $SPARK_HOME"
 

if [ ! -f "$SPARK_HOME/bin/spark-class" ]; then
  echo "ERROR: spark-class not found at $SPARK_HOME/bin/spark-class"
  exit 1
fi

chmod +x "$SPARK_HOME/bin/spark-class"

MASTER_HOST=${SPARK_LOCAL_IP:-spark-master}
MASTER_PORT=${SPARK_MASTER_PORT:-7077}
MASTER_WEBUI_PORT=${SPARK_MASTER_WEBUI_PORT:-8080}

echo "Master Configuration:"
echo "  Host:    $MASTER_HOST"
echo "  Port:    $MASTER_PORT"
echo "  WebUI:   $MASTER_WEBUI_PORT"
echo ""

exec "$SPARK_HOME/bin/spark-class" org.apache.spark.deploy.master.Master \
  --host "$MASTER_HOST" \
  --port "$MASTER_PORT" \
  --webui-port "$MASTER_WEBUI_PORT"
