# 🔍 AUDIT D'ARCHITECTURE - AIRFLOW + SPARK

**Date**: 2026-03-31  
**Status**: DIAGNOSTIC + CORRECTION

---

## 1️⃣ PROBLÈMES IDENTIFIÉS

### ❌ ANTI-PATTERN #1: Spark sur Airflow Workers
**Symptôme**: `docker-compose-local-ha.yml` utilise une image `airflow-runtime:local` qui contient Spark  
**Impact**: 
- Les workers Airflow ne devraient **JAMAIS** exécuter Spark lui-même
- Cela double les dépendances + overhead mémoire
- Pas de vrai distributed computing

### ❌ ANTI-PATTERN #2: Configuration Spark Master incohérente
**Symptôme**: 
- `spark-master` utilise image `spark-runtime:local`
- Workers lancés avec `apache/spark:3.5.0` (erreur: spark-class absent)
- Pas de configuration clair pour RPC + Web UI

**Evidence**:
```
docker logs spark-worker-1
> /opt/entrypoint.sh: line 128: /opt/spark-3.5.0-bin-hadoop3/bin/spark-class: No such file
```

### ❌ ANTI-PATTERN #3: DAGs utilisent `--master local[*]`
**Symptôme**: 
```python
SPARK_MASTER = "local[*]"  # spark_submit_etl.py
```
**Impact**: 
- Aucune exécution distribuée
- Tout tourne sur un seul worker Airflow
- Pas de scalabilité

---

## 2️⃣ ARCHITECTURE CORRECTE À PRODUIRE

### 🎯 Séparation clair des responsabilités

```
┌─────────────────────────────────────┐
│  ORCHESTRATION (Airflow)            │
│  ├─ Scheduler                       │
│  ├─ Webserver                       │
│  ├─ Workers Celery (x2)             │  ← NE CONTIENT PAS SPARK
│  ├─ Redis + PostgreSQL              │
└─────────────────────────────────────┘
           ↓ SparkSubmitOperator
┌─────────────────────────────────────┐
│  COMPUTE (Spark Standalone)         │
│  ├─ Master (port 7077)              │
│  ├─ Workers (x2)                    │  ← CONTIENT Spark + S3A
│  └─ S3A jars inclus                 │
└─────────────────────────────────────┘
           ↓ S3A
┌─────────────────────────────────────┐
│  STORAGE (S3)                       │
└─────────────────────────────────────┘
```

---

## 3️⃣ CONFIGURATION REQUISE

### Airflow Workers (SANS Spark)
```yaml
airflow-worker:
  image: apache/airflow:2.9.0  # Image AIRFLOW SEULE
  command: celery worker
  env:
    SPARK_MASTER: spark://spark-master:7077  # Référence seulement
```

### Spark Standalone
```yaml
spark-master:
  image: apache/spark:3.5.0

spark-worker:
  image: apache/spark:3.5.0
  env:
    SPARK_WORKER_CORES: 4
    SPARK_WORKER_MEMORY: 2G
```

---

**À suivre**: Implémentation et test
