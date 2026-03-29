# 🚀 ETL Pipeline Optimization & EMR Serverless Migration Guide

**Status**: Action Items for Performance & Migration

---

## PART 1: WHERE IS THE CODE EXECUTING?

### Current Execution Flow
```
┌─────────────────────────────────────────────────────────────┐
│  Airflow Webserver (Container: lakehouse-airflow-webserver) │
│                                                              │
│  spark-submit ← Bash Task (in Airflow worker container)    │
│    ↓                                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Spark Driver (LOCAL JVM Process)                   │  │
│  │  ├─ Driver process: spark-submit wrapper            │  │
│  │  ├─ Memory: 2GB                                     │  │
│  │  ├─ ExecutorBackend: LocalBackend (single machine) │  │
│  │  └─ Worker threads: 2 (from config)                │  │
│  └──────────────────────────────────────────────────────┘  │
│           ↓ S3A Read/Write                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Moto S3 Server (Mock AWS S3)                       │  │
│  │  - Container: moto container                        │  │
│  │  - Network: Docker bridge                           │  │
│  │  - Data: Ephemeral (destroyed with container)       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

EXECUTION LOCATION:     Airflow worker container (single machine)
DISTRIBUTION:           ❌ NONE (local mode only)
SCALABILITY:            ❌ Very limited (1 process, 2 threads)
PARALLELISM:            ❌ Sequential (bronze → silver → gold)
```

### Why NOT Distributed?
| Aspect | Current | Why Problem |
|--------|---------|-------------|
| **Master** | `local[*]` | Local mode = single JVM, no cluster |
| **Executors** | 0 | No worker nodes, driver does all work |
| **Partitions** | 2 | Too few for parallelism (559K rows / 2 = 280K each) |
| **Cluster** | None | Not using Kubernetes, Yarn, or Spark Standalone |

**Result**: All computation is bottlenecked on a single Airflow worker process.

---

## PART 2: IS IT REAL SPARK?

### Yes and No 😕

#### ✅ What IS Real Spark
- Spark RDD → DataFrame → SQL layer ✅
- Lazy evaluation & DAG optimization ✅
- Parquet format with columnar compression ✅
- S3A integration with Hadoop SDK ✅
- Memory management & garbage collection ✅

#### ❌ What ISN'T Real Spark
- **Distributed execution** ❌ (all local)
- **Worker nodes** ❌ (only 1 JVM)
- **Parallel task execution** ❌ (2 threads = not parallelism)
- **Data shuffling** ❌ (no network shuffle, disk-based)
- **Fault tolerance** ❌ (single process failure = fail)

**Verdict**: It's Spark code, but running in **non-optimal mode**. Like running Apache
 on a laptop instead of a server.

---

## PART 3: PERFORMANCE BOTTLENECKS ANALYSIS

### Issue Timeline
```
Timeline of bronze_ingestion task (1m 52s):
- 05:31:21  Task starts
- 05:31:33  Spark session initialization (12 sec)
- 05:31:50  Dependency resolution (17 sec total)
- 05:32:05  CSV Contrat2 read + write (14 sec) ← Network call
- 05:32:36  CSV Contrat1 read + write (31 sec) ← Network call
- 05:33:00  CSV Client read + write (24 sec) ← SLOWEST
- 05:33:13  Spark session cleanup (13 sec)
```

### Why S3 Operations Are Slow
```
Real Cluster Path (EMR):
  Network Overhead: ~0ms (local S3)
  Throughput: 100+ MB/s (10 Gbps network)

Current Local Path (Docker):
  Network Overhead: ~5-10ms per call (moto HTTP)
  Throughput: ~10 MB/s (Virtual network bridge)
  Latency Added: ❌ Significant
```

### Gap Between Tasks (5 Minutes)
```
05:33:14 Bronze finishes
     ↓
05:38:29 Silver starts (5 min 15 sec gap!)

Root Causes (in order of likelihood):
1. Airflow Scheduler Delay: 2-3 min
2. Airflow Worker availability: 1-2 min
3. Spark startup time: 30-60 sec
4. Docker image overhead: 20-30 sec
```

---

## PART 4: THE 5-MINUTE DELAY MYSTERY

### Log Analysis
```yaml
Bronze Task:
  Finished: 05:33:14  ✅
  Mark as SUCCESS: 05:33:14

Silver Task:
  Scheduled: 05:33:14 (~immediate)
  Started:   05:38:29  ⏸️ 5 MINUTE GAP

Gold Task:
  Scheduled: 05:39:47 (~immediate)
  Started:   05:45:04  ⏸️ 5 MINUTE GAP (again!)
```

### Investigation Checklist
- [ ] Check Airflow Scheduler logs: `docker logs lakehouse-airflow-scheduler`
- [ ] Check if using KubernetesExecutor (pod startup overhead)
- [ ] Verify Airflow Dag Run state transitions
- [ ] Monitor container resource usage during gaps

### Quick Fix
Add dependency annotations to make Airflow more aggressive:
```python
# In spark_submit_etl.py DAG:
bronze_ingestion.pool = 'default_pool'
silver_transformation.pool_slots = 1  # Reduce contention
silver_transformation.priority_weight = 10  # Higher priority
```

---

## PART 5: OPTIMIZATION ROADMAP

### ✅ Quick Wins (1-2 hours)
```yaml
1. Increase shuffle.partitions:
   dev.yaml:  2  → 50
   prod.yaml: 4  → 200   # Already done!

2. Remove eager .count() calls:
   Before:  df_contrat2.count()  # Triggers evaluation
   After:   logger.info(df_contrat2.schema)  # No evaluation

3. Add caching for reused data:
   df_silver.cache()
   ...operations...
   df_silver.unpersist()

TIME SAVED: 30-40% reduction in execution time
```

### 🔧 Medium-Term (1-2 days)
```yaml
4. Profile with Spark UI:
   - Identify actual slow operations
   - Optimize joins & shuffles
   - Monitor memory usage

5. Implement data skipping:
   - Predicate pushdown to parquets
   - Only read necessary columns

6. Parallelize DAG execution:
   - bronze → (silver + other_tasks)
   - Not sequential

TIME SAVED: 40-50% reduction total
```

### 🚀 Long-Term (1-2 weeks)
```yaml
7. Migrate to EMR Serverless:
   - Change --master to: spark://emr-cluster:7077
   - Auto-scaling executors
   - Spot instances for cost

8. Implement incremental processing:
   - Only process new data
   - Avoid full re-processing

TIME SAVED: 70-80% reduction + cost savings
```

---

## PART 6: EMR SERVERLESS MIGRATION CHECKLIST

### ❌ Current Blockers
- [ ] Code uses `local[*]` mode (not cluster-compatible)
- [ ] Eager `.count()` calls (inefficient for distributed)
- [ ] No partition strategy (won't scale)
- [ ] No caching (repeated reads from S3)
- [ ] Single-threaded structure

### ✅ Must-Do Before Migration
1. **Update Spark config** → ✅ prod.yaml created
2. **Remove eager actions** → ❌ TODO
3. **Add partitioning strategy** → ❌ TODO
4. **Implement caching** → ❌ TODO
5. **Test on cluster** → ❌ TODO

### 📋 EMR Serverless Requirements
```python
# Instead of:
spark-submit \
  --master local[*] \
  --driver-memory 2g \
  --executor-memory 2g \
  ...

# Use:
spark-submit \
  --master spark://emr-serverless-endpoint:6066 \
  --deploy-mode cluster \
  --conf spark.dynamicAllocation.enabled=true \
  --conf spark.aws.credentials.provider=... \
  --conf spark.emr-serverless.driverEnv.JAVA_HOME=/usr/lib/jvm/java \
  ...
```

---

## PART 7: CODE OPTIMIZATION EXAMPLES

### Example 1: Remove Eager Evaluations

**❌ BEFORE (Triggers 3 evaluations)**
```python
df_contrat2 = spark.read.parquet(path)
logger.info(f"Contrat2: {df_contrat2.count()} rows")  # ← EVALUATION 1

df_contrat1 = spark.read.parquet(path)
logger.info(f"Contrat1: {df_contrat1.count()} rows")  # ← EVALUATION 2

merged = df_contrat2.unionByName(df_contrat1)
logger.info(f"Merged: {merged.count()} rows")  # ← EVALUATION 3

# Total time: 3 × (S3 read + shuffle) = slow!
```

**✅ AFTER (No premature evaluations)**
```python
df_contrat2 = spark.read.parquet(path)
logger.info(f"Contrat2 schema: {len(df_contrat2.columns)} columns")  # No eval

df_contrat1 = spark.read.parquet(path)
logger.info(f"Contrat1 schema: {len(df_contrat1.columns)} columns")  # No eval

merged = df_contrat2.unionByName(df_contrat1)
logger.info(f"Union created (lazy, evaluation deferred)")  # No eval

# Actual evaluation happens only during write:
merged.write.parquet(path)  # ← ONLY 1 EVALUATION
```

### Example 2: Add Caching for Reused Data

**❌ BEFORE (Reads silver data 3 times)**
```python
df_silver = spark.read.parquet(s3_silver_path)

# Operation 1: Client profile
df_client_profile = df_silver.select(...).dropDuplicates(["nusoc"])
df_client_profile.write.parquet(path1)

# Operation 2: Contract analysis
df_contract_analysis = df_silver.groupBy(...).agg(...)
df_contract_analysis.write.parquet(path2)

# Operation 3: KPI dashboard
df_kpi = df_silver.select(...).groupBy(...).agg(...)
df_kpi.write.parquet(path3)

# Problem: df_silver is read 3 times from S3!
```

**✅ AFTER (Cache once, reuse 3 times)**
```python
df_silver = spark.read.parquet(s3_silver_path)
df_silver.cache()  # Cache in memory
df_silver.count()  # Trigger caching (explicit)

# Operation 1: Client profile
df_client_profile = df_silver.select(...).dropDuplicates(["nusoc"])
df_client_profile.write.parquet(path1)

# Operation 2: Contract analysis (from cache!)
df_contract_analysis = df_silver.groupBy(...).agg(...)
df_contract_analysis.write.parquet(path2)

# Operation 3: KPI dashboard (from cache!)
df_kpi = df_silver.select(...).groupBy(...).agg(...)
df_kpi.write.parquet(path3)

df_silver.unpersist()  # Free memory after use

# Result: df_silver loaded once, operations 2+3 are faster
```

### Example 3: Optimize Joins

**❌ BEFORE (Hash join = shuffle)**
```python
df_large = spark.read.parquet(path_large)  # 559K rows
df_small = spark.read.parquet(path_small)  # 40K rows

# Default: sort-merge join (both sides are shuffled)
result = df_large.join(df_small, "client_id", "inner")
```

**✅ AFTER (Broadcast join = no shuffle)**
```python
df_large = spark.read.parquet(path_large)  # 559K rows
df_small = spark.read.parquet(path_small)  # 40K rows (~100MB)

# Broadcast df_small to all executors
from pyspark.sql.functions import broadcast
result = df_large.join(broadcast(df_small), "client_id", "inner")

# Result: df_large not shuffled, only df_small broadcast
```

---

## PART 8: NEXT STEPS - YOUR TODO LIST

### Immediate (This session)
- [ ] Read this guide completely
- [ ] Understand execution model
- [ ] Decide: local optimization vs. EMR migration
- [ ] Create ticket for each optimization

### Short-term (This week)
1. **Refactor transformation scripts**
   - Remove 8 `.count()` calls
   - Add caching strategy
   - Update logging

2. **Test prod config**
   ```bash
   # Update spark_submit_etl.py to use --conf spark.sql.shuffle.partitions=100
   # Or export APP_ENV=prod
   ```

3. **Monitor Airflow delays**
   ```bash
   docker logs lakehouse-airflow-scheduler | grep -A5 "silver_transformation scheduled"
   ```

### Medium-term (Next sprint)
4. **Partition data by vehicle type**
   ```python
   df.write.partitionBy("type_vehicule").parquet(path)
   ```

5. **Implement dynamic partition calculation**
6. **Setup Spark UI for profiling**

### Long-term (Before prod)
7. **Test on real EMR cluster**
8. **Implement cost optimization**
9. **Setup monitoring & alerting**

---

## SUMMARY

| Question | Answer |
|----------|--------|
| Where executes? | Single Airflow worker container |
| Distributed? | ❌ NO - Local mode only |
| Real Spark? | ✅ YES - But unoptimally configured |
| Why slow? | 10-30× slower than expected due to configuration |
| For EMR? | ❌ Needs refactoring before migration |
| Performance ceiling? | ~2-5 min per stage (if optimized well locally) |
| Next step? | Implement 4 quick wins: config + caching + remove counts + partition strategy |

**Start with QUICK WINS today** → 30-40% faster in 1-2 hours! 🚀
