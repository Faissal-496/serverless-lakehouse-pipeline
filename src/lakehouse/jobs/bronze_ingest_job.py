#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bronze Ingestion Job
Ingests raw CSV data from local/S3 source and writes to Bronze layer (S3 Parquet)

Job: bronze_ingest_job.py
Execution: spark-submit \
    --py-files /opt/lakehouse/src \
    /opt/lakehouse/src/lakehouse/jobs/bronze_ingest_job.py \
    --execution_date 2024-01-15
"""

from pyspark.sql import SparkSession
from pyspark.sql.utils import AnalysisException
from lakehouse.jobs.base_job import SparkJob
from lakehouse.ingestion.schema_registry import CONTRAT2_SCHEMA, CLIENT_SCHEMA
from lakehouse.monitoring.logging import logger, log_partition_processed
from lakehouse.monitoring.metrics import record_rows_processed, S3OperationMetricsContext
from lakehouse.core.exceptions import DataSourceError, PersistenceError


class BronzeIngestJob(SparkJob):
    """Ingests raw CSV data to Bronze layer"""
    
    JOB_NAME = "bronze_ingest"
    
    def run(self):
        """Execute bronze layer ingestion"""
        logger.info("Starting Bronze Ingestion")
        
        # Ingest Contrat2
        self._ingest_dataset("Contrat2", "Contrat2.csv", CONTRAT2_SCHEMA)
        
        # Ingest Contrat1
        self._ingest_dataset("contrat1", "contrat1.csv", CONTRAT2_SCHEMA)
        
        # Ingest Client
        self._ingest_dataset("Client", "client.csv", CLIENT_SCHEMA)
        
        logger.info("Bronze Ingestion completed successfully")
    
    def _ingest_dataset(self, dataset_name: str, filename: str, schema):
        """
        Ingest a dataset from CSV to Bronze (S3) Parquet.
        
        Args:
            dataset_name: Logical dataset name (for paths)
            filename: Source CSV filename
            schema: PySpark StructType schema
        """
        logger.info(f"Ingesting {dataset_name}...")
        
        try:
            # Read CSV from local input directory
            input_path = self.config.get_local_input_path(filename)
            logger.debug(f"Reading from: {input_path}")
            
            df = self.spark.read \
                .option("header", "true") \
                .option("inferSchema", "false") \
                .option("nullValue", "") \
                .schema(schema) \
                .csv(input_path)
            
            row_count = df.count()
            logger.info(f"{dataset_name} loaded: {row_count} rows")
            
            # Write to Bronze layer - use local path for dev, S3 for prod
            if self.config.app_env == "dev":
                output_path = self.config.get_local_output_path("bronze", dataset_name)
                logger.debug(f"Writing to local path: {output_path}")
            else:
                output_path = self.config.get_s3_layer_path("bronze", dataset_name)
                logger.debug(f"Writing to S3 path: {output_path}")
            
            with S3OperationMetricsContext("write_parquet") as s3_metrics:
                df.write.mode("overwrite").parquet(output_path)
            
            logger.info(f"{dataset_name} written to: {output_path}")
            
            # Record metrics
            record_rows_processed("bronze", dataset_name, row_count)
            
            # Log partition info
            log_partition_processed(
                dataset_name=dataset_name,
                partition_date=self.execution_date_str,
                row_count=row_count,
                size_bytes=0  # Could calculate from df
            )
        
        except AnalysisException as e:
            raise DataSourceError(
                f"Failed to read {filename}: {str(e)}"
            )
        except Exception as e:
            raise PersistenceError(
                f"Failed to write {dataset_name} to S3: {str(e)}"
            )


if __name__ == "__main__":
    import sys
    
    execution_date = None
    
    # Parse command-line arguments if provided
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--execution_date" and i + 2 < len(sys.argv):
            execution_date = sys.argv[i + 2]
    
    job = BronzeIngestJob(execution_date=execution_date)
    success = job.execute()
    sys.exit(0 if success else 1)
