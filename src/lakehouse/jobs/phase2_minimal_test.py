#!/usr/bin/env python
"""Phase 2 MINIMAL TEST - Prove distributed execution works"""

from pyspark.sql import SparkSession
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

spark = SparkSession.builder.appName("phase2-minimal-test").getOrCreate()

logger.info("="*70)
logger.info("PHASE 2 MINIMAL TEST - Distributed Execution")
logger.info("="*70)
logger.info(f"Master: {spark.sparkContext.master}")
logger.info(f"Default Parallelism: {spark.sparkContext.defaultParallelism}")
logger.info(f"Executor Cores: {spark.conf.get('spark.executor.cores', 'default')}")

try:
    # Test 1: Read one small CSV
    logger.info("\n>>> TEST 1: Reading Contrat2.csv (70,614 rows)...")
    df = spark.read.option("header", "true").csv("/opt/lakehouse/data/Contrat2.csv")
    count = df.count()
    logger.info(f"✅ Read {count:,} rows")
    
    # Test 2: Distributed processing with repartition
    logger.info("\n>>> TEST 2: Distributed processing (repartition to 4 partitions)...")
    df_repartitioned = df.repartition(4)
    
    # Do a simple distributed operation
    row_count_per_partition = df_repartitioned.mapPartitions(
        lambda partition: [("rows_in_partition", len(list(partition)))]
    ).collect()
    
    logger.info(f"Partition distribution: {row_count_per_partition}")
    logger.info("✅ Distribution successful")
    
    logger.info("\n" + "="*70)
    logger.info("PHASE 2 TEST PASSED - Spark Standalone works!")
    logger.info("="*70)
    
except Exception as e:
    logger.error(f"❌ ERROR: {str(e)}", exc_info=True)
    sys.exit(1)
finally:
    spark.stop()
