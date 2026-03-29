# 🏗️ Architecture Visualization Guide

## Your Current Setup (LOCAL MODE)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YOUR LAPTOP/SERVER                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─── DOCKER COMPOSE ───────────────────────────────────────────┐ │
│  │                                                               │ │
│  │  Container: lakehouse-airflow-worker-1                      │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  Airflow: BashOperator runs:                         │  │ │
│  │  │  $ spark-submit --master local[*] --driver-memory 2g │  │ │
│  │  │           --executor-memory 2g --total-executor-cores 2  │ │
│  │  │  /opt/lakehouse/src/lakehouse/ingestion/bronze_ingest.py│ │
│  │  │                                                       │  │ │
│  │  │  ┌──────────────────────────────────────────────────┐ │  │ │
│  │  │  │ Spark Process (Single JVM - local[*])           │ │  │ │
│  │  │  │                                                  │ │  │ │
│  │  │  │ Driver:                                         │ │  │ │
│  │  │  │ ├─ Memory: 2GB                                 │ │  │ │
│  │  │  │ ├─ Executors: 0 (uses driver itself)           │ │  │ │
│  │  │  │ ├─ Max threads: 2 (from config)               │ │  │ │
│  │  │  │ ├─ Task execution: Sequential/Local            │ │  │ │
│  │  │  │ │  ├─ Read CSV → Show Progress                │ │  │ │
│  │  │  │ │  ├─ Transform (single-threaded)            │ │  │ │
│  │  │  │ │  ├─ Write Parquet (S3A)                     │ │  │ │
│  │  │  │ │  └─ Repeat for each file                    │ │  │ │
│  │  │  │ └─ No worker nodes, no distributed compute     │ │  │ │
│  │  │  └──────────────────────────────────────────────────┘ │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                      ↓ S3A calls                           │ │
│  │  Container: moto-server (Mock AWS S3)                     │ │
│  │  ├─ Endpoint: http://moto:5000                           │ │
│  │  └─ Bucket: lakehouse-assurance-moto-prod               │ │
│  │     ├─ /bronze/Contrat1/ (parquet files)                │ │
│  │     ├─ /bronze/Contrat2/ (parquet files)                │ │
│  │     ├─ /bronze/Client/ (parquet files)                  │ │
│  │     ├─ /silver/Client_contrat_silver/ (parquet)         │ │
│  │     └─ /gold/ (3 analysis tables)                        │ │
│  │                                                           │ │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────────────┘

KEY INSIGHT:
- Everything runs INSIDE docker-compose on your machine
- No external nodes, no cluster
- All computation on single Airflow worker
- S3 is mocked (not real AWS)
```

---

## Task Execution Timeline (Local Mode)

```
Task: bronze_ingestion
Start: 05:31:21
│
├─ 05:31:22-05:31:33: Spark initialization (11 sec)
│  └─ Load Spark context, prepare JVM
│
├─ 05:31:33-05:31:50: Download packages (17 sec)
│  ├─ hadoop-aws-3.3.4.jar
│  ├─ aws-java-sdk-bundle-1.12.262.jar
│  └─ wildfly-openssl-1.0.7.Final.jar
│
├─ 05:31:50-05:32:05: Read & Write Contrat2 (15 sec)
│  ├─ Read from: /opt/lakehouse/data/Contrat2.csv (70K rows)
│  ├─ Transform (type cast, null handling) - SINGLE THREAD
│  └─ Write to S3: s3a://bucket/bronze/Contrat2/
│
├─ 05:32:05-05:32:36: Read & Write Contrat1 (31 sec)
│  ├─ Read from: /opt/lakehouse/data/Contrat1.csv (100K rows)
│  ├─ Transform - SINGLE THREAD
│  └─ Write to S3: s3a://bucket/bronze/Contrat1/
│
├─ 05:32:36-05:33:00: Read & Write Client (24 sec)
│  ├─ Read from: /opt/lakehouse/data/Client.csv (389K rows)
│  ├─ Transform - SINGLE THREAD ← Why slow?
│  ├─ CSV Header mismatch warning
│  └─ Write to S3: s3a://bucket/bronze/Client/
│
└─ 05:33:00-05:33:13: Cleanup (13 sec)
   └─ Stop Spark session

Total: 1m 52s ✅

═══════════════════════════════════════════════════════════════

Task: silver_transformation
Scheduled: 05:33:14
⏸️  WAIT: 5 MINUTES 15 SECONDS (WHY?!)
Start: 05:38:29
│
├─ 05:38:29-05:38:35: Initialization (6 sec)
├─ 05:38:35-05:39:05: Read bronze data (30 sec)
│  ├─ Read df_contrat2.count() ← EAGER EVAL #1
│  ├─ Read df_contrat1.count() ← EAGER EVAL #2
│  └─ Union & count() ← EAGER EVAL #3
│
├─ 05:39:05-05:39:20: Join with client (15 sec)
│  ├─ Read client data (389K rows)
│  ├─ df_client.count() ← EAGER EVAL #4
│  ├─ Count before dedup ← EAGER EVAL #5
│  ├─ Drop duplicates
│  ├─ Count after dedup ← EAGER EVAL #6
│  └─ Join operation
│
└─ 05:39:20-05:39:45: Write silver (25 sec)
   ├─ Write to S3
   └─ df_silver_global.count() ← EAGER EVAL #7

Total: 1m 17s ✅

═══════════════════════════════════════════════════════════════

Task: gold_transformation
Scheduled: 05:39:47
⏸️  WAIT: 5 MINUTES 17 SECONDS (AGAIN?!)
Start: 05:45:04
│
├─ 05:45:04-05:45:14: Initialization (10 sec)
├─ 05:45:14-05:45:44: Read silver data (30 sec)
│  ├─ Load silver parquet
│  └─ Multiple reads: Profile → Analysis → KPI (3× read!)
│
├─ 05:45:44-05:45:57: Client profile analysis (13 sec)
│  ├─ Select columns
│  ├─ Drop duplicates
│  └─ Write to S3
│
├─ 05:45:57-05:46:16: Contract analysis (19 sec)
│  ├─ Group by vehicle type, contract status, etc.
│  └─ Write to S3
│
├─ 05:46:16-05:46:35: KPI dashboard (19 sec)
│  ├─ Aggregations & metrics
│  └─ Write to S3
│
└─ 05:46:35-05:46:49: Total (14 sec)

Total: 1m 44s ✅

═══════════════════════════════════════════════════════════════

REAL TOTAL TIME: 15 minutes ❌
COMPUTATION TIME: 4m 53s ✅
WASTED (delays):  10m 7s ❌❌❌
```

---

## Performance Bottleneck Analysis

```
1. DATA READ EFFICIENCY
   ┌─────────────────────────────────────────┐
   │ CSV Read  (single-threaded):            │
   │ 559K rows × local processing            │
   │ Expected: 50,000 rows/sec               │
   │ Actual:   2,000 rows/sec                │
   │ Inefficiency: 25× slower!               │
   └─────────────────────────────────────────┘
   
   Why?
   - Only 1 thread (can't parallelize)
   - No partition strategy
   - Moto S3 network overhead

2. EAGER EVALUATIONS
   ┌─────────────────────────────────────────┐
   │ Problem: 8 .count() calls               │
   │                                         │
   │ .count() forces Spark to:               │
   │ ├─ Evaluate the entire DataFrame       │
   │ ├─ Scan all rows from source           │
   │ ├─ For each: trigger S3 read           │
   │ └─ Finally return the count            │
   │                                         │
   │ Worse: Done in SERIAL (1 at a time)    │
   │                                         │
   │ Cost per .count():                      │
   │ ├─ 50-70K row dataset: 3-5 sec         │
   │ ├─ 100K+ row dataset: 5-10 sec         │
   │ └─ 389K row Client: 10-15 sec          │
   │                                         │
   │ Total: 8 calls × 5 sec = 40 seconds    │
   │ If removed: save 40 seconds!            │
   └─────────────────────────────────────────┘

3. NO CACHING
   ┌─────────────────────────────────────────┐
   │ silver_to_gold.py reads df_silver 3×:   │
   │                                         │
   │ Gold1: Query df_silver → Write S3      │
   │ Gold2: Query df_silver → Write S3      │
   │ Gold3: Query df_silver → Write S3      │
   │                                         │
   │ Cost:                                   │
   │ ├─ Read 1: S3 deserialize = 13-17 sec │
   │ ├─ Read 2: S3 deserialize = 13-17 sec │
   │ └─ Read 3: S3 deserialize = 13-17 sec │
   │                                         │
   │ If cached after Read 1:                │
   │ ├─ Read 2: Memory cache = <1 sec       │
   │ └─ Read 3: Memory cache = <1 sec       │
   │                                         │
   │ Total saved: 25-30 seconds!             │
   └─────────────────────────────────────────┘

4. PARTITION STRATEGY
   ┌─────────────────────────────────────────┐
   │ Config: shuffle.partitions = 2          │
   │                                         │
   │ With 559K rows:                        │
   │ ├─ Partition 1: 280K rows              │
   │ ├─ Partition 2: 279K rows              │
   │ └─ Parallelism: Can use both           │
   │    (good!) BUT...                      │
   │                                         │
   │ Problem: Only 2 threads available      │
   │ ├─ Task 1 → Thread 1 (280K rows)      │
   │ ├─ Task 2 → Thread 2 (279K rows)      │
   │ └─ Both run sequentially w/ memory    │
   │    contention                          │
   │                                         │
   │ If 100 partitions + 8 threads:        │
   │ ├─ ~5600 rows per partition           │
   │ ├─ Can process 8 in parallel          │
   │ └─ Much better throughput              │
   │                                         │
   │ (But still local, not distributed)    │
   └─────────────────────────────────────────┘
```

---

## Side-by-Side Comparison

```
LOCAL MODE (Current)           DISTRIBUTED MODE (EMR)
─────────────────────────────────────────────────────────
Master: local[*]               Master: spark://emr:7077
Nodes: 1                       Nodes: 5-100+
JVMs: 1 (driver)               JVMs: many (1 driver + N workers)
Partitions: 2                  Partitions: 100+
Parallelism: 2 threads         Parallelism: 50+ concurrent
Task Distribution: NONE        Task Distribution: Data-local
Network: Docker virtual        Network: Real Ethernet
Throughput: 2K rows/sec        Throughput: 50K+ rows/sec
Failure: Job dies              Failure: Task retried on another node
Scaling: Fixed size            Scaling: Auto-scale executors

YOUR CURRENT SYSTEM = 1 person doing 100 tasks sequentially
DISTRIBUTED SYSTEM = 100 people doing 100 tasks in parallel
```

---

## What Happens When You Run the DAG

```
Timeline of Execution:

05:31:11 - Airflow detects manual trigger
           └─ Creates DAG run instance
           └─ Marks validate_env as ready

05:31:11 - Airflow waits for resources
           └─ Searching for available worker...
           └─ Found worker: lakehouse-airflow-worker-1

05:31:21 - Task validate_env starts
           └─ Bash: echo Spark config
           └─ Returns immediately ✅

05:31:21 - Task bronze_ingestion starts  
           ├─ Bash: spark-submit bronze_ingest.py
           ├─ ~ 1m 52s of processing ~
           └─ 05:33:14: Returns SUCCESS

05:33:14 - Airflow marks bronze complete
           └─ Dependency checking for silver...
           └─ silver is ready!

05:33:14 - Airflow schedules silver_transformation
           └─ Task created, queued in executor

⏸️  DELAY (5 minutes) - WHERE IS 05:33:14 - 05:38:29?
           ├─ Airflow scheduler checking status
           ├─ Waiting for worker availability?
           ├─ Pod/container overhead?
           └─ (Investigate this later)

05:38:29 - Task silver_transformation starts
           ├─ Bash: spark-submit bronze_to_silver.py
           ├─ ~ 1m 17s of processing ~
           └─ 05:39:47: Returns SUCCESS

⏸️  DELAY (5 minutes) - SAME PATTERN
           (same investigation points)

05:45:04 - Task gold_transformation starts
           ├─ Bash: spark-submit silver_to_gold.py
           ├─ ~ 1m 44s of processing ~
           └─ 05:46:49: Returns SUCCESS

05:46:49 - All tasks complete ✅
           └─ DAG marked as SUCCESS

```

---

## Solution Visualization

```
CURRENT STATE                  AFTER 4 QUICK WINS
(~5 minutes)                   (~3m 35s)

bronze_ing   ████████████   →  ██████████ (saves 32s)
  ⏸️ 5min gap
silver_trans ████████        →  ███████ (saves 27s)
  ⏸️ 5min gap
gold_trans   ████████████    →  ██████████ (saves 19s)

Computation: 4m 53s → 3m 35s (-28%)
Still has 5m gaps in Airflow (separate issue)


AFTER FULL REFACTOR + EMR
(~1m 30s total)

bronze_ing   ██ (10× faster, parallel execution)
silver_trans █ (auto-scaling, data-local)
gold_trans   █ (distributed shuffles)

No gaps, optimized orchestration
```

---

## Memory Usage Over Time

```
Spark Driver Memory (2GB currently):

Start:  ▁▁▁▁▁▁▁▁▁▁
        Spark init (400MB)

Reading: ██████████ (1.6GB)
        CSV → DataFrame caching

Transform: ████████████ (1.8GB)
        Multiple columns, temp vars

Write:  ██████████ (1.6GB)
        Parquet serialization

End:    ▁▁▁▁▁▁▁▁▁▁
        Cleanup

With 4GB (prod):
Much more headroom for caching
Can hold multiple DataFrames in memory
```

---

## Decision Tree

```
┌──────────────────────────────────────────────┐
│ Do I need to fix this TODAY?                 │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
       NO                    YES
        │                     │
   Use it as-is         ┌─────┴──────────┐
   Schedule around      │                │
   delays               Need quick wins  Need production
                        (1-2 hours)      ready (1-2 weeks)
                        │                │
                   Apply 4 fixes → Do full refactor
                   • Remove counts → Add monitoring
                   • Add cache → Partition strategy
                   • Config tune → Incremental proc.
                   • Test → Benchmark
                        │ → EMR migration
```

---

That's your complete architecture! Start with `QUICK_SUMMARY.md` for next steps. 🚀
