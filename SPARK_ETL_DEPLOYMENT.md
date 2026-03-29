# Spark ETL Deployment Guide

**Note**: AWS credentials and sensitive data removed. Use environment variables instead.

## Phase 2: Spark Standalone Cluster

- Master: spark://spark-master:7077
- Workers: 2 (4 cores, 2GB each)
- Network: serverless-lakehouse-pipeline_lakehouse-network

See PHASE2_RESULTS.md for detailed results.

## Configuration

Use `.env` file at root for AWS credentials (excluded from Git).

Key variables:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY  
- AWS_DEFAULT_REGION

## See Also

- PHASE2_RESULTS.md - Complete Phase 2 deployment results
- ARCHITECTURE_VISUALIZATION.md - System architecture diagrams
