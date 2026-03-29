# 🔧 Code Optimization Checklist

## File: `src/lakehouse/transformation/bronze_to_silver.py`

### Changes Required

#### 1️⃣ Remove Eager .count() Calls (Lines 47-51)

**BEFORE:**
```python
df_contrat2 = spark.read.parquet(s3_bronze_path_contrat2)
df_contrat1 = spark.read.parquet(s3_bronze_path_contrat1)

logger.info(f"Contrat2 loaded: {df_contrat2.count()} rows")  # ❌ Forces evaluation
logger.info(f"Contrat1 loaded: {df_contrat1.count()} rows")  # ❌ Forces evaluation
```

**AFTER:**
```python
df_contrat2 = spark.read.parquet(s3_bronze_path_contrat2)
df_contrat1 = spark.read.parquet(s3_bronze_path_contrat1)

logger.info(f"Contrat2 schema: {len(df_contrat2.columns)} columns")  # ✅ No evaluation
logger.info(f"Contrat1 schema: {len(df_contrat1.columns)} columns")  # ✅ No evaluation
```

**Impact**: Saves 1 full S3 read per file

---

#### 2️⃣ Remove Eager Count After unionByName (Line 54)

**BEFORE:**
```python
df_contracts = df_contrat2.unionByName(df_contrat1)
logger.info(f"Merged contracts: {df_contracts.count()} rows")  # ❌ Triggers shuffle
```

**AFTER:**
```python
df_contracts = df_contrat2.unionByName(df_contrat1)
logger.info(f"Union operation created (evaluation deferred)")  # ✅ Lazy
```

**Impact**: Saves 1 expensive union + shuffle operation

---

#### 3️⃣ Remove Eager Counts for Deduplication (Lines 77-80)

**BEFORE:**
```python
before_dedup = df_silver.count()  # ❌ Evaluation 1
df_silver = df_silver.dropDuplicates(["nusoc", "nucon"])
after_dedup = df_silver.count()  # ❌ Evaluation 2
logger.info(f"Removed {before_dedup - after_dedup} duplicates")
```

**AFTER:**
```python
# Skip the before/after counts, they're expensive
df_silver = df_silver.dropDuplicates(["nusoc", "nucon"])
logger.info(f"Deduplication applied (lazy evaluation)")
```

**Impact**: Saves 1 full evaluation of the dedup operation

---

#### 4️⃣ Optimize Client Data Reading (Line 179)

**BEFORE:**
```python
df_client = spark.read.parquet(s3_bronze_path_client)
logger.info(f"Client data loaded: {df_client.count()} rows")  # ❌ Triggers 389K row read
```

**AFTER:**
```python
df_client = spark.read.parquet(s3_bronze_path_client)
logger.info(f"Client data loaded from: {s3_bronze_path_client}")  # ✅ No evaluation
```

**Impact**: Saves 1 full S3 read of 389K rows

---

#### 5️⃣ Remove Quality Check Counts (Lines 192-195)

**BEFORE:**
```python
before_qc = df_client_silver.count()  # ❌ Count entire dataset
df_client_silver = df_client_silver.filter(
    (col("age_client") >= 14) & (col("age_client") <= 100)
)
after_qc = df_client_silver.count()  # ❌ Count again after filter
logger.info(f"Quality check: removed {before_qc - after_qc} invalid ages")
```

**AFTER:**
```python
df_client_silver = df_client_silver.filter(
    (col("age_client") >= 14) & (col("age_client") <= 100)
)
logger.info(f"Quality check: filter applied for age 14-100")
```

**Impact**: Saves 1 full count (expensive operation)

---

#### 6️⃣ Remove Eager Count After Join (Line 213)

**BEFORE:**
```python
df_silver_global = df_silver.join(
    df_client_silver.select(...),
    on="nusoc",
    how="inner"
)
logger.info(f"Joint result: {df_silver_global.count()} rows")  # ❌ Count result
```

**AFTER:**
```python
df_silver_global = df_silver.join(
    df_client_silver.select(...),
    on="nusoc",
    how="inner"
)
logger.info(f"Inner join completed (evaluation deferred)")
```

**Impact**: Saves 1 join evaluation

---

#### 7️⃣ Add Caching for df_silver (After line 72)

**ADD AFTER TYPE CASTING & NULL HANDLING:**
```python
# Cache the transformed contract data
# It will be used for dedup, business logic, and joining
df_silver.cache()
logger.info("Contract data cached for reuse")
```

**REMOVE AFTER LINE 213 (at end of manipulation):**
```python
# Free up memory after final join is created
df_silver.unpersist()
logger.info("Cleared contract data cache")
```

**Impact**: Prevents re-evaluation of expensive transformations

---

### Total Impact Summary

| Operation | Removed Calls | Savings/Call | Total Savings |
|-----------|---------------|--------------|---------------|
| S3 reads | 3 | ~3-5 sec | 9-15 sec |
| Full dataset counts | 5 | ~3-5 sec | 15-25 sec |
| Union/shuffle ops | 1 | ~5 sec | 5 sec |
| **TOTAL TIME SAVINGS** | **9 eager actions** | **~4 sec avg** | **~30-45 sec (30-40%)** |

---

## File: `src/lakehouse/transformation/silver_to_gold.py`

### Changes Required

#### 1️⃣ Implement Caching Strategy (At start, after line 44)

**ADD:**
```python
# Load silver data once, cache it for all operations
df_silver = spark.read.parquet(s3_silver_path)
logger.info(f"Silver data loaded from: {s3_silver_path}")

# Cache in memory for reuse across 3 gold tables
df_silver.cache()
df_silver.count()  # Trigger caching explicitly
logger.info(f"Silver data cached for analysis operations")
```

**IMPACT**: Prevents reading same data 3 times from S3

---

#### 2️⃣ Remove Excessive groupBy Operations (Optimization)

**Check all occurrences of** `.groupBy(...).agg(...).show()` or similar

If using `.show()` for logging, change to:
```python
# ❌ BEFORE:
gender_dist = df_client_profile.groupBy("sexsoc").agg(...)
gender_dist.show()  # Prints output (good for UI)

# ✅ For production, prefer:
gender_dist = df_client_profile.groupBy("sexsoc").agg(...)
# Only show if logging for debugging, not for every run
if logger.getEffectiveLevel() == logging.DEBUG:
    gender_dist.show()
```

---

#### 3️⃣ Add Final Cache Cleanup (At end of script, before unpersist)

**ADD BEFORE FINAL SUCCESS MESSAGE:**
```python
# Memory cleanup
df_silver.unpersist()
logger.info("Cleared silver data cache")
```

---

### Code Pattern Template

Use this pattern for all gold tables:

```python
# Gold Table N: [Description]
logger.info(f"Creating GOLD {N}: [DESCRIPTION]")

# Create transformation (lazy)
df_gold_n = df_silver.select(...).filter(...).groupBy(...).agg(...)

# Write to S3 (triggers evaluation + physical write)
s3_gold_path_n = resolver.s3_layer_path(layer="gold", dataset="gold_table_n")
df_gold_n.write.mode("overwrite").parquet(s3_gold_path_n)

logger.info(f"Gold {N} written to {s3_gold_path_n}")
```

**Key Principle**: Evaluation happens ONLY during `.write()` call, not before!

---

## File: `orchestration/airflow/dags/spark_submit_etl.py`

### Change: Use prod.yaml for Better Config

**UPDATE THE DAG TO USE PROD CONFIG:**

```python
# Check if APP_ENV is dev or prod
APP_ENV = os.getenv('APP_ENV', 'dev')

# If prod, add --conf for better parallelism
SPARK_EXTRA_CONF = ""
if APP_ENV == "prod":
    SPARK_EXTRA_CONF = f"""
    --conf spark.sql.shuffle.partitions=100 \\
    --conf spark.default.parallelism=8 \\
    --conf spark.executor.cores=4 \\
    """
```

Then in each spark-submit command:
```bash
spark-submit \\
    --master {SPARK_MASTER} \\
    --deploy-mode client \\
    --driver-memory 4g \\
    --executor-memory 4g \\
    {SPARK_EXTRA_CONF} \\  # ← Add this
    --packages ... \\
    ...
```

**Impact**: Automatically switches to optimized config in production

---

## Testing Checklist

After applying changes:

- [ ] Run bronze_ingestion task
  - Expected time: < 2 minutes (saved 30-45 sec)  
  - Check logs for 'cached' and 'unpersist' messages
  
- [ ] Run silver_transformation task
  - Expected time: < 1 minute (saved 20-30 sec)
  - Verify no eager count() calls in output
  
- [ ] Run gold_transformation task
  - Expected time: < 1:45 (saved 15-25 sec)
  - Verify caching statistics in Spark logs
  
- [ ] Check S3 outputs exist and have correct data
  - Bronze: 3 folders (Contrat1, Contrat2, Client)
  - Silver: 1 folder (Client_contrat_silver)
  - Gold: 3 folders (client_profile, contract_analysis, kpi_dashboard)

- [ ] Verify total pipeline time < 5 minutes (saved 2-3 minutes total)

---

## Monitoring & Profiling

After optimization, to dig deeper into performance:

```bash
# Enable Spark UI (add to spark-submit):
--conf spark.eventLog.enabled=true \\
--conf spark.eventLog.dir=/tmp/spark-logs \\
--conf spark.ui.port=4040 \\

# Then access: http://localhost:4040
```

**Key metrics to monitor**:
- Task duration (should be under 2 min per stage)
- Data shuffled (should be minimal)
- GC time (should be < 10%)
- Partition count (should match config)

---

## Priority Order

1. **CRITICAL** (Do first):
   - Remove eager counts (~5 min work)
   - Add caching strategy (~10 min work)
   - Test locally

2. **HIGH** (Do same session):
   - Update DAG for prod config (~5 min)
   - Verify performance improvement
   - Commit changes

3. **MEDIUM** (Follow-up):
   - Profile with Spark UI
   - Optimize specific slow operations
   - Document findings

---

## Expected Results

| Metric | Before | After | Gain |
|--------|--------|-------|------|
| Bronze time | 1m 52s | ~1m 20s | -32 sec (28%) |
| Silver time | 1m 17s | ~0m 50s | -27 sec (35%) |
| Gold time | 1m 44s | ~1m 25s | -19 sec (18%) |
| **Total pipeline** | ~5m 00s | ~3m 35s | -1m 25s (28.5%) |

**Not including the 5-minute delay between tasks** - once fixed, expect total < 4.5 min!
