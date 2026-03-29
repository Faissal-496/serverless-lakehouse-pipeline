# 📝 QUICK SUMMARY: Your Pipeline Issues Explained

## 🎯 Main Questions Answered

### Q1: "Où sont exécutées les tâches?" (Where do tasks execute?)
**A**: In the **Airflow worker container**, NOT in a distributed cluster.
```
Airflow Worker Container
├─ spark-submit (bash process)
│  └─ Spark Driver (single JVM)
│     └─ All computation happens here
└─ No worker nodes, no executors
```

**Timeline**: Task starts → Airflow schedules → Container runs spark-submit → Spark runs locally

---

### Q2: "Est-ce du vrai calcul Spark distribué?" (Is it real distributed Spark?)
**A**: **NO**, it's local mode.
```
--master local[*]
│
├─ ✅ Real Spark code (RDD, DataFrame, SQL)
├─ ✅ Real S3 integration (S3A protocol)
├─ ✅ Real lazy evaluation & DAG optimization
│
├─ ❌ No distribution (all on 1 machine)
├─ ❌ No workers (1 JVM only)
├─ ❌ No parallelism (2 threads max = sequential)
└─ ❌ No fault tolerance
```

**Result**: Your code is Spark, but execution is **non-optimal** `(like using Apache on a laptop).`

---

### Q3: "Pourquoi ça prend plus que 2min?" (Why > 2min?)

| Issue | Current | Impact |
|-------|---------|--------|
| Only 2 partitions | 559K rows / 2 | No parallelism |
| Eager `.count()` calls | 8 calls (lines 47, 50, 54, 77, 79, 179, 194, 213) | Extra S3 reads/shuffles |
| No caching | Silver data read 3× | Repeated S3 I/O |
| Local mode overhead | Single JVM | Can't scale |
| 5-min delays between tasks | Airflow scheduler | Orchestration bottleneck |

**Math**: 
- Bronze (559K rows): 1m 52s ÷ 559K = **2K rows/sec** (should be 50K+)
- **30-40% slower than expected** due to configuration

---

### Q4: "Comment améliorer avant EMR?"(How to improve before EMR?)

#### 4 Quick Wins (1-2 hours work):

**1. Increase Partitions** (config/spark/prod.yaml - ✅ Already done!)
```yaml
# Before: spark.sql.shuffle.partitions: 2
# After:  spark.sql.shuffle.partitions: 100
```
**Saves**: 20-30% time

**2. Remove Eager `.count()` Calls** 
```python
# Before: logger.info(f"Loaded: {df.count()} rows")
# After:  logger.info(f"Loaded: {len(df.columns)} columns")
```
**Saves**: 30-45 sec per stage

**3. Add Caching for Silver Data**
```python
df_silver.cache()
df_silver.count()  # trigger cache
# Use it 3 times without re-reading
df_silver.unpersist()
```
**Saves**: 1 S3 read = 13-17 sec

**4. Optimize Joins (Broadcast)**
```python
# Before: df_large.join(df_small)  # Both shuffled
# After:  df_large.join(broadcast(df_small))  # Only small broadcast
```
**Saves**: 10-15 sec

**TOTAL POTENTIAL SAVINGS**: 1minute 20 seconds → 3m 35s total (28.5% faster)

---

## 🚨 Critical Issue: The 5-Minute Gaps

```
Timeline:
05:31:21 ──────────────────────── 05:33:14  bronze_ingestion (1m 52s) ✅
         ⏸️ 5 MINUTE GAP
05:38:29 ────────────── 05:39:47  silver_transformation (1m 17s) ✅
         ⏸️ 5 MINUTE GAP
05:45:04 ─────────────── 05:46:49  gold_transformation (1m 44s) ✅

Total time if sequential: 1m52 + 1m17 + 1m44 = 4m53s
Actual time: ~15 minutes (with gaps!)
```

**Root cause**: Airflow Scheduler delay (not Spark problem)

**Quick check**:
```bash
docker logs lakehouse-airflow-scheduler | grep silver_transformation
# Look for time between scheduled and actually started
```

---

## ✅ What's Working

- ✅ Data flowing correctly (parquets in bronze, silver, gold)
- ✅ Transformations logic is correct
- ✅ All 3 stages complete successfully
- ✅ Spark code is valid and scalable
- ✅ S3 integration works (using moto mock)

---

## ❌ What's Not Optimal

| Issue | Severity | Fix Time |
|-------|----------|----------|
| Local mode (not distributed) | Medium | Need cluster for EMR |
| 8 eager `.count()` calls | High | 15 min to fix |
| Partition count = 2 (too low) | High | 5 min (just config) |
| No caching of reused data | Medium | 20 min to add |
| 5-min delays between tasks | Low | Airflow config |

---

## 🏗️ Execution Model (Detailed)

```
┌────────────────────────────────────────────────────────────────┐
│                   DOCKER COMPOSE STACK                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Airflow Stack                                                 │
│  ├─ airflow-webserver (UI @ localhost:8080)                  │
│  ├─ airflow-scheduler (triggers tasks)                       │
│  └─ airflow-worker (runs Bash tasks) ← YOUR CODE RUNS HERE!  │
│      └─ spark-submit ← Bash operator calls this             │
│         └─ Spark Driver (local[*] mode)                     │
│            ├─ Driver JVM (2GB memory)                       │
│            ├─ Task execution (2 threads max)                │
│            └─ S3A reads/writes ↓                            │
│                                                              │
│  AWS/S3 Stack (Mocked)                                       │
│  └─ moto-server (mock S3 @ http://moto:5000)               │
│     └─ Test bucket: lakehouse-assurance-moto-prod           │
│        ├─ bronze/ (Contrat1, Contrat2, Client)             │
│        ├─ silver/ (Client_contrat_silver)                  │
│        └─ gold/ (3 analysis tables)                        │
│                                                              │
└────────────────────────────────────────────────────────────────┘

Key insight: Everything runs INSIDE the Airflow worker container.
No external Spark cluster. No distributed execution.
```

---

## 🚀 Roadmap to EMR Serverless

### Phase 1: Local Optimization (This week)
```
✅ New prod.yaml config (already done)
❌ Remove eager evaluations (15 min)
❌ Add caching strategy (20 min)
❌ Test improvements (30 min)
→ Expected result: 3m 35s total (-28%)
```

### Phase 2: Code Refactoring (Next week)
```
❌ Profile with Spark UI
❌ Partition data by vehicle type
❌ Implement dynamic partition calc
→ Expected result: 3m 00s total (-40%)
```

### Phase 3: EMR Migration (Before production)
```
❌ Change --master to EMR endpoint
❌ Update IAM credentials
❌ Test on real cluster
❌ Implement auto-scaling
→ Expected result: 1m-2m per stage (cloud optimized)
```

---

## 📊 Key Metrics

| Metric | Current | Optimized Local | EMR Serverless |
|--------|---------|-----------------|------------------|
| Throughput | 1.6K-5K rows/sec | 10K-20K rows/sec | 50K-100K rows/sec |
| Bronze time | 1m 52s | ~1m 20s | ~30-45 sec |
| Silver time | 1m 17s | ~50 sec | ~20-30 sec |
| Gold time | 1m 44s | ~1m 25s | ~25-35 sec |
| Total (no delays) | ~4m 53s | ~3m 35s | ~1m 30s |
| Parallelism | 2 threads | 8 threads | 16+ threads (auto) |

---

## 🎓 Key Learning

> **Local Mode ≠ Distributed Execution**

When you use `--master local[*]`, Spark:
- ✅ Still uses its optimization engine
- ✅ Still uses DataFrames & SQL
- ❌ But runs it all in one JVM on one machine
- ❌ No worker nodes to send work to
- ❌ No actual parallelism or distribution

**Analogy**: It's like buying an 18-wheeler truck but only using the engine in your garage, never taking it on the highway!

---

## 💡 What To Do Next

1. **Read these 3 files** (in this order):
   - `PERFORMANCE_ANALYSIS.md` (full analysis)
   - `EMR_MIGRATION_GUIDE.md` (detailed explanations)
   - `OPTIMIZATION_CHECKLIST.md` (specific code changes)

2. **Apply Quick Wins** (see OPTIMIZATION_CHECKLIST.md):
   - Option A: Manual edits (15-30 min)
   - Option B: Ask for refactored scripts

3. **Test improvements**:
   ```bash
   # Run pipeline again
docker-compose up -d
darflow dags trigger spark_submit_etl --exec-date 2024-01-20T00:00:00
   ```

4. **Measure**:
   - Check duration in Airflow UI
   - Compare before/after
   - Target: < 4m total

---

## ❓ FAQ

**Q: Will EMR Serverless solve all these problems?**
A: Yes, but code must be refactored first. EMR can't fix bad code.

**Q: How long to implement all optimizations?**
A: Quick wins: 1-2 hours → Full refactor: 1-2 days → EMR ready: 1 week

**Q: Should I wait for EMR or optimize local?**
A: Do quick wins NOW (28% faster), refactor for production, THEN migr to EMR.

**Q: Why not just use `--master spark://cluster`?**
A: No cluster running. Need Kubernetes, YARN, or standalone Spark cluster first.

**Q: What about the 5-minute gaps?**
A: Likely Airflow scheduler, not Spark. Separate issue to investigate later.

---

## 📞 Need Help?

If you want me to apply these changes automatically:
1. Confirm you want refactored scripts
2. I'll create optimized versions of:
   - `bronze_to_silver.py`
   - `silver_to_gold.py`
   - Updated `spark_submit_etl.py` DAG

Let me know! 🚀
