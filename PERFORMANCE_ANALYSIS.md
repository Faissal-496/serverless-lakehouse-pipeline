# 🚨 Pipeline Performance Analysis & Issues

**Date**: 2026-03-29 | **Status**: Critical Issues Identified

---

## 1. 🔴 PRIMARY ISSUE: LOCAL MODE vs DISTRIBUTED EXECUTION

### Current Configuration
```
--master local[*]
--executor-cores 1
spark.sql.shuffle.partitions: 2
spark.default.parallelism: 2
```

### The Problem ❌
| Aspect | Current | Expected |
|--------|---------|----------|
| **Execution Mode** | `local[*]` (Single JVM) | `spark://cluster:7077` (Cluster) |
| **Parallelism** | 1-2 tasks max | 10+ concurrent tasks |
| **Distribution** | NO (all on Airflow worker) | YES (across nodes) |
| **Real Spark?** | ❌ NO - Just sequential | ✅ YES - True distributed |

**Translation**: C'est PAS du calcul Spark distribué! C'est juste un processus local qui exécute les commandes Spark sur une seule machine (le worker Airflow).

---

## 2. ⏱️ SECONDARY ISSUE: 5-MINUTE GAP BETWEEN TASKS

### Timeline
```
05:31:21 → 05:33:14  Bronze ingestion (1m 52s) ✅
          ⏸️ 5 MINUTE GAP (IDLE!)
05:38:29 → 05:39:47  Silver transformation (1m 17s) ✅
          ⏸️ ~6 MINUTE GAP
05:45:04 → 05:46:49  Gold transformation (1m 44s) ✅
```

### Root Cause
- **Airflow Scheduler delay** OR
- **Kubernetes pod startup overhead** (if using KubernetesExecutor)
- **Docker container resource constraints**

---

## 3. 📊 DATA VOLUME vs DURATION ANALYSIS

### Numbers
| Layer | Input Rows | Columns | Duration | Speed |
|-------|-----------|---------|----------|-------|
| Bronze | 70K + 100K + 389K = 559K | 43-18 | 1m 52s | 5,000 rows/sec (slow!) |
| Silver | 170K (post-union/join) | 56 | 1m 17s | 2,200 rows/sec (slower!) |
| Gold | 170K (grouped/agg) | Varies | 1m 44s | 1,600 rows/sec (slowest!) |

### Baseline Expectations
- **Spark local[*]**: ~50,000-100,000 rows/sec (even on single core)
- **Your speed**: 1,600-5,000 rows/sec = **10-30× slower than expected**

---

## 4. 🐌 CODE-LEVEL BOTTLENECKS

### Issue A: Eager Actions in Transformation Logic
```python
# ❌ BAD: Forces immediate evaluation
df_contrat2 = spark.read.parquet(path)
logger.info(f"Contrat2 loaded: {df_contrat2.count()} rows")  # COUNT = EXECUTION!

df_contrat1 = spark.read.parquet(path)
logger.info(f"Contrat1 loaded: {df_contrat1.count()} rows")  # COUNT = EXECUTION!

df_silver = df_contrat2.unionByName(df_contrat1)
logger.info(f"Merged: {df_silver.count()} rows")  # ANOTHER COUNT!
```

**Impact**: 3 separate S3 reads + 2 shuffles before actual transformations start!

### Issue B: shuffle.partitions = 2 (For 559K rows)
```yaml
spark.sql.shuffle.partitions: 2  # Only 2 partitions?!
```
- With 559K rows and only 2 partitions = 280K rows per partition
- No parallelism in JOIN/GROUP BY operations  
- For EMR Serverless: This would be terrible!

### Issue C: No Caching of Intermediate Data
```python
# The silver data is read 3 times in gold.py without caching
df_silver = spark.read.parquet(s3_silver_path)  # Read 1
...
df_silver.select(...).dropDuplicates()  # Triggers transformation
df_silver.groupBy(...).agg(...)  # Triggers re-read from S3
```

---

## 5. 🏗️ WHERE IS CODE EXECUTING? 

### Current Setup
```
┌─────────────────────────────────────────┐
│      Airflow Scheduler/Worker           │
│  ┌────────────────────────────────────┐ │
│  │  spark-submit (Local JVM Process)  │ │  ← All computation happens here
│  │  - Driver Memory: 2GB              │ │
│  │  - Executor Memory: 2GB            │ │
│  │  - Workers: 0 (LOCAL MODE!)        │ │
│  │  - Max parallelism: 2 threads      │ │
│  └────────────────────────────────────┘ │
│           ↓ S3A (moto mock)  ↓          │
│  ┌─────────────────────────────────────┐│
│  │   Mock S3 (Moto Container)          ││
│  └─────────────────────────────────────┐│
└─────────────────────────────────────────┘
```

**Not real distributed execution!**

---

## 6. 🚀 AWS EMR SERVERLESS READINESS CHECK

| Item | Current | EMR Serverless | Gap |
|------|---------|-----------------|-----|
| Execution Mode | local[*] | ❌ Not compatible | HIGH |
| Partition Strategy | 2 partitions | Auto-scaling needed | HIGH |
| Code Structure | Eager evaluations | ❌ Inefficient | MEDIUM |
| Resource Config | Fixed (2g/2g) | ✅ Auto-scales | LOW |
| S3 Integration | moto (mock) | ✅ Real AWS SDK | LOW |

**Migration Blocker**: You MUST refactor code before EMR Serverless migration!

---

## 7. ✅ RECOMMENDATIONS (PRIORITY ORDER)

### CRITICAL (Do immediately)
1. **Increase `shuffle.partitions`** from 2 → 100+ (for larger datasets)
2. **Remove eager `.count()` calls** from logging
3. **Add caching** for data read multiple times
4. **Parallelize Airflow tasks** (bronze→silver + silver→gold independently)

### HIGH (Before production)
5. **Profile code** with Spark UI to find real bottlenecks
6. **Optimize joins** (use broadcast for small tables)
7. **Implement partitioning strategy** (by date, vehicle type, etc.)

### MEDIUM (Before EMR migration)
8. **Move to cluster mode** (Spark standalone, Kubernetes, or YARN)
9. **Implement dynamic partition calculation** in config
10. **Add metrics collection** for monitoring

### LOW (Nice to have)
11. Use Liquid/Parquet compression
12. Implement incremental processing

---

## 8. 🔧 QUICK WINS TO IMPLEMENT

### Fix 1: Production-Ready Spark Config
```yaml
# config/spark/prod.yaml
spark:
  config:
    # For datasets > 100K rows, use auto-scaling partitions
    spark.sql.shuffle.partitions: 200  # or: ceil(num_rows / 10000)
    spark.default.parallelism: 8
    spark.executor.cores: 4
    spark.driver.memory: 4g
    spark.executor.memory: 4g
```

### Fix 2: Remove Eager Actions
```python
# Instead of:
# logger.info(f"Loaded: {df.count()} rows")

# Use:
logger.info(f"Data schema: {df.schema}")  # No execution
logger.info(f"Estimated rows (no action taken)")
```

### Fix 3: Add Caching for Silver Data
```python
df_silver = spark.read.parquet(s3_silver_path)
df_silver.cache()  # Cache in memory after first read
df_silver.count()  # Trigger caching

# Now multiple operations use cached version
df_client_profile = df_silver.select(...).dropDuplicates()
df_contract_analysis = df_silver.groupBy(...).agg(...)
df_kpi = df_silver.select(...)  # All from cache!

df_silver.unpersist()  # Free memory
```

### Fix 4: Parallelize Airflow DAG Tasks
```python
# Current (Sequential): bronze → silver → gold
validate >> bronze >> silver >> gold >> verify

# Better (Parallel batches):
validate >> bronze >> (silver & gold_prep_in_parallel) >> verify
```

---

## CONCLUSION

✅ **Pipeline WORKS correctly** - Data is flowing and transforming  
❌ **Pipeline is NOT distributed** - Using local mode  
⚠️ **Pipeline is SLOW** - 10-30× slower than expected  
🔴 **EMR migration will FAIL** - Code needs refactoring first  

**Next step**: Implement the 4 quick wins above, then profile with Spark UI.
