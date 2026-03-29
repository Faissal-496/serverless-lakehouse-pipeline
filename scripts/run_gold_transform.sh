#!/bin/bash
# Gold Transformation Wrapper 
# Installs dependencies and runs gold transformation

set -e  # Exit on error

echo "📦 Installing runtime dependencies..."
pip3 install -q pyspark==3.5.0 pandas==2.1.4 pyarrow==14.0.1 boto3==1.28.85 python-dotenv==1.0.0 2>&1 | tail -1

echo "📊 STAGE 3: GOLD TRANSFORMATION"
echo "Analytics + KPI Dashboard"
echo "========================="
echo ""

export PYTHONPATH=/opt/lakehouse/src:$PYTHONPATH
python3 /opt/lakehouse/src/lakehouse/transformation/silver_to_gold.py

echo ""
echo "✅ Gold transformation completed"
