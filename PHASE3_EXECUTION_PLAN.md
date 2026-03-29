# PHASE 3 EXECUTION PLAN - Full ETL Pipeline on Distributed Spark

**Status**: Ready to Execute  
**Date**: 2026-03-29  
**Prerequisite**: Phase 2 HA analysis ✅ PASSED  

---

## Quick Status Summary

```
┌──────────────────────────────────────┐
│  PHASE 2 COMPLETED ✅                │
├──────────────────────────────────────┤
│ Spark Master: ALIVE                  │
│ Workers: 2/2 REGISTERED              │
│ Airflow HA: OPERATIONAL              │
│ Network: VERIFIED                    │
│ Data Access: CONFIRMED               │
│ Ready for Phase 3: YES ✅            │
└──────────────────────────────────────┘
```

---

## Phase 3 Objective

**Execute complete ETL pipeline on Spark Standalone cluster:**

```
CSV Data (Airflow triggers)
    ↓
BRONZE INGESTION (spark-submit)
    └─→ Parse Contrat2.csv (70.6K rows)
    └─→ Parse Client.csv (100K rows)
    └─→ Output: Parquet files in Bronze layer
    ↓
SILVER TRANSFORMATION (spark-submit)
    └─→ Apply schema normalization
    └─→ Data quality checks
    └─→ Output: Optimized Parquet
    ↓
GOLD ANALYTICS (spark-submit)
    └─→ Create analytical tables
    └─→ Business logic aggregations
    └─→ Output: Final reporting datasets
    ↓
VALIDATION & METRICS (Airflow task)
    └─→ Row counts
    └─→ Execution time
    └─→ Performance comparison vs Phase 1
```

---

## Execution Checklist

### Before Start
- [ ] Verify Spark cluster status: `docker ps | grep spark`
- [ ] Check Airflow WebUI: http://localhost:8080
- [ ] Confirm data files exist: `docker exec spark-worker-1 ls /opt/lakehouse/data/`

### Phase 3 Steps

#### Step 1: Trigger ETL DAG via Airflow
```bash
# Option A: Via Airflow CLI
docker exec -u airflow lakehouse-airflow-webserver airflow dags trigger \
  spark_etl_standalone_phase2 \
  --exec-date 2026-03-29T17:00:00

# Option B: Via Airflow Web UI
# Navigate to: http://localhost:8080/home
# Find: spark_etl_standalone_phase2 DAG
# Click: Trigger DAG → Execute
```

#### Step 2: Monitor Execution
```bash
# Watch Spark Master UI (real-time tasks)
# http://localhost:8084

# Watch Airflow DAG (task status)
# http://localhost:8080/dags/spark_etl_standalone_phase2

# Tail logs
docker logs lakehouse-airflow-scheduler | grep "spark_etl" | tail -20
```

#### Step 3: Validate Output
```bash
# Check parquet files created
docker exec spark-worker-1 find /tmp/lakehouse-phase2-* -type f | head -20

# Row count validation
# (Check PHASE2_RESULTS.md for expected counts)
```

---

## Expected Performance Metrics

### Baseline (Phase 1 - Local Mode)
- **Total Time**: ~150 seconds
- **Bronze**: 70.6K + 100K rows processed
- **Silver**: Row count preserved with optimizations
- **Gold**: Final aggregations
- **Execution Method**: Single node (all cores)

### Phase 3 Target (Distributed on 2 Workers)
- **Expected Time**: 50-70 seconds (2-3× speedup)
  - Parallelization benefit: 2 workers × 4 cores = 8 total
  - Network overhead: minimal (same datacenter)
- **Bronze**: Same data volume, faster via distribution
- **Silver**: Parallel processing on both workers
- **Gold**: Aggregations on clustered data
- **Execution Method**: Spark Standalone (distributed)

### Success Criteria
- ✅ All 3 layers execute without errors
- ✅ Execution time < 100 seconds (better than Phase 1)
- ✅ Row counts match expected values
- ✅ Both workers utilized (confirmed in Spark UI)
- ✅ Data preserved through pipeline integrity

---

## Key Spark Configurations Used

```python
# spark-submit configuration
spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --driver-memory 1g \
  --executor-memory 2g \
  --executor-cores 2 \
  --total-executor-cores 4 \
  {job_file}.py

# Cluster topology
Driver: Airflow worker container
Executor 0: spark-worker-1 (2 cores, 2GB)
Executor 1: spark-worker-2 (2 cores, 2GB)
```

---

## File References

### Main DAG to Execute
[orchestration/airflow/dags/spark_etl_standalone_phase2.py](orchestration/airflow/dags/spark_etl_standalone_phase2.py)

**DAG Structure**:
- Task 1: `validate_environment` - Pre-flight checks
- Task 2: `bronze_ingestion_standalone` - spark-submit bronze_ingest.py
- Task 3: `silver_transformation_standalone` - spark-submit silver_to_gold.py
- Task 4: `gold_transformation_standalone` - spark-submit silver_to_gold.py
- Task 5: `verify_cluster_output` - Validation

### ETL Code
- [src/lakehouse/ingestion/bronze_ingest.py](src/lakehouse/ingestion/bronze_ingest.py) - Bronze layer
- [src/lakehouse/transformation/bronze_to_silver.py](src/lakehouse/transformation/bronze_to_silver.py) - Silver layer
- [src/lakehouse/transformation/silver_to_gold.py](src/lakehouse/transformation/silver_to_gold.py) - Gold layer

### Documentation
- [PHASE2_RESULTS.md](PHASE2_RESULTS.md) - Phase 2 deployment details
- [PHASE2_HA_DEEP_ANALYSIS.md](PHASE2_HA_DEEP_ANALYSIS.md) - System health analysis

---

## Troubleshooting Guide

### Issue: Spark Master shows 0 Executors
**Cause**: Workers not registered  
**Fix**:
```bash
docker ps | grep spark-worker  # Check if workers running
docker logs spark-master | grep "Registering worker"  # Verify registration
```

### Issue: spark-submit Connection Refused
**Cause**: Network issue or master down  
**Fix**:
```bash
docker exec lakehouse-airflow-worker-1 bash -c '</dev/tcp/spark-master/7077'
# Should succeed (connection established)
```

### Issue: "File not found" on CSV
**Cause**: Worker doesn't have data volume mounted  
**Fix**:
```bash
docker inspect spark-worker-1 | grep -A 5 Mounts
# Should show /opt/lakehouse/data mounted read-only
```

### Issue: Airflow DAG stays in "scheduled"
**Cause**: Scheduler not running  
**Fix**:
```bash
docker ps | grep airflow-scheduler  # Must show running
docker logs lakehouse-airflow-scheduler | tail -20  # Check for errors
```

---

## Post-Execution Steps

### After DAG Completes
1. **Capture baseline metrics** from logs
2. **Compare with Phase 1** baseline (150s)
3. **Document actual speedup factor**
4. **Update PHASE3_RESULTS.md** with outcomes

### If Time Exceeds Expectations
1. Check Spark Master UI for task distribution
2. Look for slow tasks in logs
3. Verify network latency between workers
4. Consider data skew (check schema)

### Iteration Improvements (Phase 4)
- Add S3 backend for remote storage
- Implement checkpointing for large datasets
- Add Spark caching at intermediate layers
- Consider AWS EMR migration

---

## Commands Ready to Copy-Paste

### Check Everything is Ready
```bash
# 1. Verify infrastructure
docker ps | grep -E "spark-|airflow-"

# 2. Check Spark cluster status
curl http://localhost:8084/api/v1/applications 2>/dev/null | head

# 3. Access Airflow
# http://localhost:8080
# Username: airflow
# Password: airflow
```

### Execute Phase 3
```bash
# Trigger DAG
docker exec -u airflow lakehouse-airflow-webserver \
  airflow dags trigger spark_etl_standalone_phase2 \
  --exec-date 2026-03-29T17:00:00

# Or use Airflow Web UI (easier)
# http://localhost:8080 → spark_etl_standalone_phase2 → Trigger DAG
```

### Monitor During Execution
```bash
# Spark Master Web UI (real-time tasks)
# http://localhost:8084

# Airflow DAG run
# http://localhost:8080/dags/spark_etl_standalone_phase2/grid

# Logs from scheduler
docker logs -f lakehouse-airflow-scheduler | grep -i "spark\|error"
```

---

## Success Indicators

When execution completes successfully, you should see:

1. **Airflow WebUI**: All DAG tasks green ✅
2. **Spark Master UI**: Job marked as FINISHED
3. **Logs**: 
   ```
   [PHASE2] ✅ Bronze ingestion completed
   [PHASE2] ✅ Silver transformation completed
   [PHASE2] ✅ Gold analytics completed
   Duration: 50-80 seconds
   ```

4. **Data Output**: Parquet files in `/tmp/lakehouse-phase2-*`

---

## Next Steps After Phase 3

### Immediate (After results captured)
- [ ] Document actual execution time
- [ ] Create PHASE3_RESULTS.md with outcomes
- [ ] Calculate speedup factor vs Phase 1

### Phase 4 (Production Preparation)  
- [ ] Add S3 integration instead of local storage
- [ ] Implement data quality checks
- [ ] Add monitoring & alerting
- [ ] Performance tuning (caching, partitioning)

### Future (Beyond Phase 4)
- [ ] Migrate to AWS EMR (auto-scaling)
- [ ] Add Hive metastore for table management
- [ ] Implement data lineage tracking
- [ ] Add cost optimization

---

## Ready to Execute?

**Status**: ✅ **YES - ALL SYSTEMS GO FOR PHASE 3**

```
Spark Cluster:     ✅ READY
Airflow HA:        ✅ READY
Data:              ✅ READY
Network:           ✅ READY
DAG:               ✅ READY
```

**Proceed with Phase 3 execution!**

---

Generated: 2026-03-29 UTC  
Next Review: After Phase 3 execution
