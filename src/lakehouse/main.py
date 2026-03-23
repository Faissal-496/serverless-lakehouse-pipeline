#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lakehouse Pipeline Orchestrator
Main entry point that coordinates:
1. Bronze ingestion from local CSV files
2. Silver transformation (contract + client consolidation)
3. Gold transformation (analytics dashboards & KPIs)
"""

from lakehouse.utils.spark_session import get_spark_session
from lakehouse.paths import PathResolver
from lakehouse.monitoring.logging import logger

# Import transformation modules
from lakehouse.ingestion import bronze_ingest
from lakehouse.transformation import bronze_to_silver, silver_to_gold


def main():
    """
    Execute the complete lakehouse ETL pipeline.
    """
    spark = None
    
    try:
        # Initialize Spark
        logger.info("Starting Lakehouse Pipeline Orchestrator")
        spark = get_spark_session("LakehousePipeline")
        
        # Initialize path resolver
        resolver = PathResolver()
        logger.info(f"Environment: {resolver.app_env}")
        logger.info(f"S3 Bucket: {resolver.s3_bucket}")
        
        # =============================================
        # STEP 1: BRONZE INGESTION
        # =============================================
        logger.info("-" * 40)
        logger.info("STEP 1: BRONZE INGESTION")
        logger.info("-" * 40)
        
        try:
            bronze_ingest.run(spark, resolver)
            logger.info("Bronze ingestion succeeded")
        except Exception as e:
            logger.error(f"Bronze ingestion failed: {str(e)}")
            raise
        
        # =============================================
        # STEP 2: SILVER TRANSFORMATION
        # =============================================
        logger.info("-" * 40)
        logger.info("STEP 2: SILVER TRANSFORMATION")
        logger.info("-" * 40)
        
        try:
            bronze_to_silver.run(spark, resolver)
            logger.info("Silver transformation succeeded")
        except Exception as e:
            logger.error(f"Silver transformation failed: {str(e)}")
            raise
        
        # =============================================
        # STEP 3: GOLD TRANSFORMATION
        # =============================================
        logger.info("-" * 40)
        logger.info("STEP 3: GOLD TRANSFORMATION")
        logger.info("-" * 40)
        
        try:
            silver_to_gold.run(spark, resolver)
            logger.info("Gold transformation succeeded")
        except Exception as e:
            logger.error(f"Gold transformation failed: {str(e)}")
            raise
        
        # =============================================
        # PIPELINE COMPLETED
        # =============================================
        logger.info("-" * 80)
        logger.info("LAKEHOUSE PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("-" * 80)
        logger.info("Data Flow Summary:")
        logger.info("   CSV (Local) -> Bronze (S3/Parquet)")
        logger.info("   Bronze -> Silver (Consolidated + Business Logic)")
        logger.info("   Silver -> Gold (Analytics Dashboards)")
        logger.info("Ready for analytics queries!")
        
    except Exception as e:
        logger.error("-" * 80)
        logger.error(f"PIPELINE FAILED: {str(e)}")
        logger.error("-" * 80, exc_info=True)
        raise
        
    finally:
        if spark:
            logger.info("Stopping Spark session...")
            spark.stop()
            logger.info("Spark session stopped")


if __name__ == "__main__":
    main()

