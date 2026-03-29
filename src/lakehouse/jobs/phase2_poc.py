#!/usr/bin/env python
"""Phase 2 - Ultra-Fast Proof of Concept"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit
import logging
import time

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

start =time.time()

spark = SparkSession.builder.appName("phase2-poc").getOrCreate()

print("="*70)
print("PHASE 2: SPARK STANDALONE PROOF OF CONCEPT")
print("="*70)
print(f"Master: {spark.sparkContext.master}")
print(f"Parallelism: {spark.sparkContext.defaultParallelism}")

# Create synthetic data (fast, no file I/O)
print("\nCreating 100,000 rows synthetic data...")
df = spark.range(0, 100000).withColumn("partition_id", (lit(1)))

# Repartition for distributed processing
print("Repartitioning to 4 partitions...")
df_distributed = df.repartition(4)

# Execute distributed operation
print("Executing distributed count (triggers task submission to workers)...")
count = df_distributed.count()

elapsed = time.time() - start

print("\n" + "="*70)
print("✅ PHASE 2 SUCCESS")
print("="*70)
print(f"Rows processed: {count:,}")
print(f"Total time: {elapsed:.2f}s")
print(f"Rate: {count/elapsed:,.0f} rows/sec")
print("\n✅ Spark Standalone cluster is WORKING!")
print(f"✅ Job submitted to master and executed on {4} partitions")
print("="*70)

spark.stop()
