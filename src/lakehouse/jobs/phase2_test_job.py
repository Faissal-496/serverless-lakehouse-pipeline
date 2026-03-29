#!/usr/bin/env python
"""
Phase 2 Test Job - Bronze Ingestion without S3 (local output)
Tests Spark Standalone distributed execution on 2 workers
"""

from pyspark.sql import SparkSession
import os
import sys
from datetime import datetime
import logging

# Add src path
sys.path.insert(0, '/opt/lakehouse/src')

from lakehouse.config_loader import load_yaml
from lakehouse.paths import PathResolver

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_spark_session():
    """Create Spark session for distributed execution"""
    spark = SparkSession.builder \
        .appName("lakehouse-bronze-phase2") \
        .getOrCreate()

    # Configure for standalone cluster
    spark.conf.set("spark.sql.shuffle.partitions", "8")

    return spark


def ingest_bronze(spark, data_path, output_path):
    """
    Ingest CSV files to Parquet (local filesystem for Phase 2 test)
    
    Args:
        spark: SparkSession
        data_path: Path to CSV files
        output_path: Path to write Parquet output
    """
    
    files = {
        "Contrat2": f"{data_path}/Contrat2.csv",
        "Client": f"{data_path}/Client.csv",
    }
    
    results = {}
    
    for name, file_path in files.items():
        try:
            logger.info(f"[PHASE2] Reading {name} from {file_path}...")
            
            # Read CSV with lenient parsing
            df = spark.read \
                .option("header", "true") \
                .option("inferSchema", "true") \
                .option("mode", "PERMISSIVE") \
                .option("charset", "UTF-8") \
                .csv(file_path)
            
            row_count = df.count()
            
            logger.info(f"[PHASE2] {name}: {row_count} rows read, {len(df.columns)} columns")
            
            # Repartition for distributed processing
            df_partitioned = df.repartition(4)  # Spread across 2 workers × 2 partitions
            
            # Write to local parquet
            output = f"{output_path}/{name}"
            logger.info(f"[PHASE2] Writing {name} to {output}...")
            
            df_partitioned.write.mode("overwrite").parquet(output)
            
            logger.info(f"[PHASE2] ✅ {name} ingestion completed")
            results[name] = row_count
            
        except Exception as e:
            logger.error(f"[PHASE2] ❌ Error processing {name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    return results


def main():
    """Main execution"""
    
    logger.info("="*80)
    logger.info("PHASE 2: SPARK STANDALONE BRONZE INGESTION TEST")
    logger.info("="*80)
    
    spark = create_spark_session()
    
    logger.info(f"Spark Master: {spark.sparkContext.master}")
    logger.info(f"App Name: lakehouse-bronze-phase2")
    logger.info(f"Cores Available: {spark.sparkContext.defaultParallelism}")
    
    # Paths
    data_path = "/opt/lakehouse/data"
    output_path = "/tmp/lakehouse-phase2-bronze"  # Local temp directory
    
    os.makedirs(output_path, exist_ok=True)
    
    try:
        start_time = datetime.now()
        logger.info(f"Start Time: {start_time}")
        
        # Run ingestion
        results = ingest_bronze(spark, data_path, output_path)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Summary
        logger.info("="*80)
        logger.info("PHASE 2 TEST RESULTS")
        logger.info("="*80)
        
        total_rows = sum(results.values())
        for name, count in results.items():
            logger.info(f"  {name:15} -> {count:10,} rows")
        
        logger.info(f"{'TOTAL':15} -> {total_rows:10,} rows")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Throughput: {total_rows/duration:,.0f} rows/sec")
        logger.info("="*80)
        logger.info("✅ PHASE 2 TEST PASSED")
        
    except Exception as e:
        logger.error(f"❌ PHASE 2 TEST FAILED: {str(e)}", exc_info=True)
        spark.stop()
        sys.exit(1)
    
    finally:
        spark.stop()
        logger.info("Spark session stopped")


if __name__ == "__main__":
    main()
