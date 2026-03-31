# 🏗️ ARCHITECTURE LAKEHOUSE CORRIGÉE

**Date**: 2026-03-31  
**Status**: IMPLÉMENTATION FINALISÉE

---

## Table des matières
1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture correcte](#2-architecture-correcte)
3. [Composants](#3-composants)
4. [Flux de données](#4-flux-de-données)
5. [Configuration](#5-configuration)
6. [Déploiement](#6-déploiement)
7. [Tests](#7-tests)
8. [Améliorations futures](#8-améliorations-futures)

---

## 1. Vue d'ensemble

### Objectif
Construire une **data platform locale** simulant un environnement AWS EMR Serverless en utilisant:
- **Airflow HA**: orchestration (sans calcul distribué)
- **Spark Standalone**: compute distribué (2 workers)
- **S3A**: stockage (S3 simulé)
- **Docker Compose**: orchestration containers

### Principes de base
```
✅ Séparation des responsabilités
✅ Architecture scalable (local → Kubernetes → AWS)
✅ Isolation des workloads (orchestration ≠ compute)
✅ Résilience (HA sur Airflow + failover aware)
✅ Observabilité (logs centralisés + Web UIs)
```

---

## 2. Architecture correcte

### Vue logique

```
┌──────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                       │
│  (Airflow HA - pas de calcul distribué)                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │   Scheduler      │  │   Webserver      │                │
│  │  (DAG Parser)    │  │  (REST API+UI)   │                │
│  └────────┬─────────┘  └──────────────────┘                │
│           │                                                 │
│           │ (publish tasks via Redis)                      │
│           ↓                                                  │
│  ┌────────┴──────────────┬────────────────┐               │
│  │                       │                │                │
│  ▼                       ▼                ▼                 │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│ │ Celery       │  │ Celery       │  │ Celery       │      │
│ │ Worker 1     │  │ Worker 2     │  │ Monitoring   │      │
│ │(task exec)   │  │(task exec)   │  │(metrics)     │      │
│ └──────┬───────┘  └──────┬───────┘  └──────────────┘      │
│        │ (SparkSubmitOp) │                                 │
└────────┼─────────────────┼─────────────────────────────────┘
         │ spark-submit    │
         └────────┬────────┘
                  │ --master spark://spark-master:7077
                  ▼
┌──────────────────────────────────────────────────────────────┐
│                   COMPUTE LAYER (Spark)                      │
│         Standalone Cluster (Master-Worker Architecture)      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Spark Master                          │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │ Driver (PySpark Job)                         │  │   │
│  │  │ - Parse DAG                                  │  │   │
│  │  │ - Schedule tasks                             │  │   │
│  │  └────────────────────┬─────────────────────────┘  │   │
│  │                       │                            │   │
│  │     RPC 7077 + Web UI 8084                        │   │
│  └───────────────────────┼────────────────────────────┘   │
│                          │                                │
│        ┌─────────────────┼─────────────────┐             │
│        │                 │                 │             │
│        ▼                 ▼                 ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Worker 1    │  │  Worker 2    │  │ Executor     │  │
│  │ (4 cores)    │  │ (4 cores)    │  │ (Shuffle)    │  │
│  │ (2GB)        │  │ (2GB)        │  │             │  │
│  │ Executors:   │  │ Executors:   │  │             │  │
│  │ - Task proc  │  │ - Task proc  │  │             │  │
│  │ - Cache      │  │ - Cache      │  │             │  │
│  │ - Shuffle    │  │ - Shuffle    │  │             │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
                      ↓ S3A protocol
┌──────────────────────────────────────────────────────────────┐
│                   STORAGE LAYER (S3)                         │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ bronze/  │  │ silver/  │  │  gold/   │               │
│  │ Parquet  │  │ Parquet  │  │ Parquet  │               │
│  └──────────┘  └──────────┘  └──────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Flux d'exécution d'un job ETL

```
DAG: lakehouse_etl_main
│
└─ Task: bronze_ingest
   │
   ├─ Airflow Scheduler: reads DAG, schedules task
   ├─ Celery Worker 1: picks task from queue
   ├─ ExecuteSparkSubmit:
   │  └─ spark-submit \
   │     --master spark://spark-master:7077 \
   │     --deploy-mode client \
   │     --executor-cores 2 \
   │     --executor-memory 2g \
   │     /opt/lakehouse/src/lakehouse/jobs/bronze_ingest_job.py
   │
   └─ Spark Cluster:
      ├─ Master receives app
      ├─ Master: "allocate 2 executors on each worker"
      ├─ Worker 1: spawn executor 1,2
      ├─ Worker 2: spawn executor 3,4
      ├─ Executor 1,2,3,4: execute PySpark job
      │  ├─ Read CSV from local mount
      │  ├─ Transform to DataFrame
      │  ├─ Write Parquet to S3A
      │  └─ S3A Client: uses hadoop-aws jar
      └─ Master: return results to Driver
          └─ Driver: collect results + logs

Result:
- Data written to S3: s3a://lakehouse.../bronze/...
- Metrics recorded to Airflow Task Instance
```

---

## 3. Composants

### Services Docker

| Service | Image | Role | CPU | Mem | Network |
|---------|-------|------|-----|-----|---------|
| **postgres** | postgres:15-alpine | Airflow metadata | 1 | 256MB | lakehouse |
| **redis** | redis:7-alpine | Celery broker | 1 | 256MB | lakehouse |
| **git-sync** | git-sync:v4.1.0 | DAG sync | 0.5 | 128MB | lakehouse |
| **spark-master** | apache/spark:3.5.0 | Spark Master | 2 | 2GB | lakehouse |
| **spark-worker-1** | apache/spark:3.5.0 | Spark Executor | 4 | 2GB | lakehouse |
| **spark-worker-2** | apache/spark:3.5.0 | Spark Executor | 4 | 2GB | lakehouse |
| **airflow-webserver** | apache/airflow:2.9.0 | Web UI | 2 | 1GB | lakehouse |
| **airflow-scheduler** | apache/airflow:2.9.0 | DAG Scheduler | 2 | 1GB | lakehouse |
| **airflow-worker-1** | apache/airflow:2.9.0 | Task Executor | 2 | 1GB | lakehouse |
| **airflow-worker-2** | apache/airflow:2.9.0 | Task Executor | 2 | 1GB | lakehouse |

**Total Resources Required**: ~25 CPUs, 12GB RAM (adjustable down for Dev)

### Volumes

| Volume | Mount Point | Purpose |
|--------|------------|---------|
| postgres_data | /var/lib/postgresql | Airflow metadata persistence |
| redis_data | /data | Celery state |
| airflow_home | /opt/airflow | Airflow settings |
| airflow_dags | /opt/airflow/dags | DAG code (from git-sync) |
| airflow_logs | /opt/airflow/logs | Task logs |
| spark_*_logs | /opt/spark/logs | Spark job logs |

### Network

- **Type**: Docker bridge (`lakehouse-network`)
- **DNS**: Enabled (hostname resolution)
- **Services accessible as**:
  - `postgres:5432`
  - `redis:6379`
  - `spark-master:7077`
  - `spark-worker-1:7078`
  - `airflow-webserver:8080`
  - `airflow-scheduler:9100` (internal)

---

## 4. Flux de données

### Bronze Layer: CSV → Parquet
```python
# Input: local CSV files (/opt/lakehouse/data/*.csv)
# Process:
#   - Spark read CSV with schema inference
#   - Repartition to distributed partitions
#   - Write as Parquet (columnar format)
# Output: S3A parquet
#   s3a://lakehouse-assurance-moto-dev/bronze/contrat2/...
#   s3a://lakehouse-assurance-moto-dev/bronze/client/...

# Job: bronze_ingest_job.py
# Executed on: Spark workers (distributed)
# Parallelism: 4 (2 workers × 2 cores each)
```

### Silver Layer: Standardize → Parquet
```python
# Input: Bronze Parquet (S3A)
# Process:
#   - Read Parquet from S3A
#   - Data quality checks
#   - Standardize columns
#   - Join multiple sources
#   - Repartition by key
# Output: Silver Parquet (S3A)

# Job: silver_transform_job.py
# Executed on: Spark workers
```

### Gold Layer: Analytics → Parquet
```python
# Input: Silver Parquet (S3A)
# Process:
#   - Aggregations
#   - KPI calculations
#   - Business logic
# Output: Gold Parquet (S3A)
#   + analytics/reports (ready for BI tools)

# Job: gold_transform_job.py
# Executed on: Spark workers
```

---

## 5. Configuration

### docker-compose-lakehouse.yml
```yaml
services:
  # Infrastructure
  postgres, redis, git-sync
  
  # Spark Standalone
  spark-master
  spark-worker-1, spark-worker-2
  
  # Airflow HA
  airflow-webserver
  airflow-scheduler
  airflow-worker-1, airflow-worker-2

networks:
  lakehouse-network (bridge, DNS enabled)

volumes:
  (persistent storage for state, logs, code)
```

### Environment Variables (.env)
```bash
AWS_ACCESS_KEY_ID=<token>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_DEFAULT_REGION=eu-west-3
S3_BUCKET=lakehouse-assurance-moto-dev
GLUE_DB_NAME=lakehouse_assurance_dev
APP_ENV=dev
```

### Airflow Configuration (env vars in compose)
```python
AIRFLOW__CORE__EXECUTOR = CeleryExecutor
AIRFLOW__CELERY__BROKER_URL = redis://redis:6379/0
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN = postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
AIRFLOW__CORE__PARALLELISM = 4
SPARK_MASTER = spark://spark-master:7077
```

---

## 6. Déploiement

### Démarrage complet
```bash
./deploy-lakehouse.sh deploy
```

Steps:
1. Initialize .env file
2. Pull Docker images
3. Start PostgreSQL, Redis
4. Start git-sync (DAG sync)
5. Start Spark Master + Workers
6. Start Airflow Webserver, Scheduler, Workers
7. Health checks

### Services state après déploiement
```
Container Status:
  ✓ postgres (healthy)
  ✓ redis (healthy)
  ✓ git-sync (healthy)
  ✓ spark-master (running, web ui 8084)
  ✓ spark-worker-1 (registered to master)
  ✓ spark-worker-2 (registered to master)
  ✓ airflow-webserver (healthy, web ui 8080)
  ✓ airflow-scheduler (running)
  ✓ airflow-worker-1 (ready)
  ✓ airflow-worker-2 (ready)
```

### Accès
```
Airflow:      http://localhost:8080 (admin/airflow)
Spark Master: http://localhost:8084
```

---

## 7. Tests

### Connectivity Test
```bash
./deploy-lakehouse.sh test
```

Vérifie:
- Spark RPC (7077)
- Spark Web UI (8084)
- Airflow connectivity

### DAG Test
```bash
./deploy-lakehouse.sh test
```

Lance une exécution test du DAG `lakehouse_etl_main`.

### Manual Testing
```bash
# Verify Spark cluster is working
docker exec lakehouse-spark-master \
  spark-submit --master spark://spark-master:7077 \
  --class org.apache.spark.examples.SparkPi \
  /opt/spark-3.5.0-bin-hadoop3/examples/jars/spark-examples_2.12-3.5.0.jar 1

# Check Airflow DAGs available
docker exec lakehouse-airflow-webserver airflow dags list

# Trigger DAG manually
docker exec lakehouse-airflow-webserver \
  airflow dags trigger lakehouse_etl_main
```

---

## 8. Améliorations futures

### Phase 4: Production Hardening
- [ ] Add Master HA (Zookeeper)
- [ ] Add Spark shuffle service (external)
- [ ] Add S3 credentials rotation
- [ ] Add job retry logic + checkpointing
- [ ] Add data quality framework (dbt / Great Expectations)

### Phase 5: Cloud Migration
- [ ] Migrate Airflow → Airflow Managed (AWS MWAA)
- [ ] Migrate Spark → EMR Serverless
- [ ] Replace S3A local → real AWS S3
- [ ] Add Lambda for preprocessing

### Phase 6: ML/Analytics
- [ ] Add feature engineering pipeline
- [ ] Add ML model training
- [ ] Add BI tool integration (Tableau/Looker)
- [ ] Add data governance (Unity Catalog / Collibra)

---

## Fichiers clés

```
project_root/
├─ docker-compose-lakehouse.yml       (main deployment config)
├─ deploy-lakehouse.sh                (CLI tool)
├─ .env.lakehouse                     (environment vars)
├─ ARCHITECTURE_AUDIT.md              (this file)
├─ orchestration/airflow/
│  └─ dags/
│     └─ lakehouse_etl_main.py        (main ETL DAG)
└─ src/lakehouse/
   └─ jobs/
      ├─ bronze_ingest_job.py
      ├─ silver_transform_job.py
      └─ gold_transform_job.py
```

---

**Status**: ✅ Architecture propre + implémentation complète  
**Next Step**: Déployer + tester + mesurer performance
