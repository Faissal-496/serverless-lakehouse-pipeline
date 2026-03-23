#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bronze Ingestion Layer
Ingests raw data from local CSV files and writes to S3 in Parquet format
"""

import sys
import traceback
from pyspark.sql import SparkSession
from pyspark.sql.utils import AnalysisException

from lakehouse.paths import PathResolver
from lakehouse.ingestion.schema_registry import CONTRAT1_SCHEMA, CONTRAT2_SCHEMA, CLIENT_SCHEMA
from lakehouse.monitoring.logging import logger
from lakehouse.utils.spark_session import get_spark_session


def read_csv(spark: SparkSession, path: str, schema=None):
    """
    Safely read CSV file with logging and error handling.
    
    Args:
        spark: SparkSession instance
        path: Path to CSV file
        schema: PySpark StructType schema (optional)
    
    Returns:
        DataFrame with CSV data
    """
    try:
        logger.info(f"Reading CSV file: {path}")
        df = spark.read \
            .option("header", "true") \
            .option("inferSchema", schema is None) \
            .option("nullValue", "") \
            .schema(schema) \
            .csv(path)
        
        row_count = df.count()
        logger.info(f"CSV loaded successfully: {row_count} rows")
        logger.info(f"Columns: {len(df.columns)}")
        
        return df
        
    except AnalysisException as ae:
        logger.error(f"File not found or schema error: {ae}")
        raise
    except Exception as e:
        logger.error(f"Error reading CSV: {str(e)}", exc_info=True)
        raise


def write_parquet(df, output_path: str):
    """
    Safely write DataFrame to Parquet on S3.
    
    Args:
        df: PySpark DataFrame
        output_path: S3 path for output
    """
    try:
        logger.info(f"Writing parquet to: {output_path}")
        df.write.mode("overwrite").parquet(output_path)
        logger.info(f"Parquet written successfully")
        
    except Exception as e:
        logger.error(f"Error writing parquet: {str(e)}", exc_info=True)
        raise


def run(spark: SparkSession, resolver: PathResolver) -> None:
    """
    Execute bronze layer ingestion.
    
    Args:
        spark: SparkSession instance
        resolver: PathResolver instance for S3 paths
    """
    try:
        logger.info("-" * 80)
        logger.info("BRONZE INGESTION STARTED")
        logger.info("-" * 80)
        
        # =========================
        # INGEST CONTRAT2
        # =========================
        logger.info("[1/3] Ingesting Contrat2...")
        input_contrat2 = resolver.local_input("Contrat2.csv")
        output_contrat2 = resolver.s3_layer_path("bronze", "Contrat2")
        
        df_contrat2 = read_csv(spark, input_contrat2, schema=CONTRAT2_SCHEMA)
        write_parquet(df_contrat2, output_contrat2)
        logger.info(f"Contrat2 ingestion completed: {output_contrat2}")
        
        # =========================
        # INGEST CONTRAT1
        # =========================
        logger.info("[2/3] Ingesting Contrat1...")
        input_contrat1 = resolver.local_input("contrat1.csv")
        output_contrat1 = resolver.s3_layer_path("bronze", "contrat1")
        
        df_contrat1 = read_csv(spark, input_contrat1, schema=CONTRAT1_SCHEMA)
        write_parquet(df_contrat1, output_contrat1)
        logger.info(f"Contrat1 ingestion completed: {output_contrat1}")
        
        # =========================
        # INGEST CLIENT
        # =========================
        logger.info("[3/3] Ingesting Client...")
        input_client = resolver.local_input("client.csv")
        output_client = resolver.s3_layer_path("bronze", "Client")
        
        df_client = read_csv(spark, input_client, schema=CLIENT_SCHEMA)
        write_parquet(df_client, output_client)
        logger.info(f"Client ingestion completed: {output_client}")
        
        # =========================
        # SUMMARY
        # =========================
        logger.info("-" * 80)
        logger.info("BRONZE INGESTION COMPLETED SUCCESSFULLY")
        logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"Bronze ingestion failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    """
    Standalone execution (for testing).
    Set environment variables: APP_ENV, S3_BUCKET, DATA_BASE_PATH
    """
    spark = get_spark_session("BronzeIngestion")
    resolver = PathResolver()
    
    try:
        run(spark, resolver)
    finally:
        spark.stop()
        logger.info("Spark session stopped")


