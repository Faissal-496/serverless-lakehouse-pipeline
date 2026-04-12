#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bronze Ingestion Job
Ingests raw CSV data from S3 RAW/ and writes to Bronze layer (S3 Parquet)
"""

from pyspark.sql.utils import AnalysisException
from lakehouse.jobs.base_job import SparkJob
from lakehouse.ingestion.schema_registry import CONTRAT2_SCHEMA, CLIENT_SCHEMA
from lakehouse.monitoring.logging import logger, log_partition_processed
from lakehouse.monitoring.metrics import (
    record_rows_processed,
    S3OperationMetricsContext,
)
from lakehouse.core.exceptions import DataSourceError, PersistenceError


class BronzeIngestJob(SparkJob):
    """Ingests raw CSV data to Bronze layer"""

    JOB_NAME = "bronze_ingest"

    def run(self):
        logger.info("Starting Bronze Ingestion")

        self._ingest_dataset("Contrat2", "Contrat2.csv", CONTRAT2_SCHEMA)
        self._ingest_dataset("Contrat1", "Contrat1.csv", CONTRAT2_SCHEMA)
        self._ingest_dataset("Client", "Client.csv", CLIENT_SCHEMA)

        logger.info("Bronze Ingestion completed successfully")

    def _ingest_dataset(self, dataset_name: str, filename: str, schema):
        logger.info(f"Ingesting {dataset_name}...")

        try:
            # Always read from S3 RAW/
            input_path = self.config.get_input_path(filename)
            logger.info(f"Reading from: {input_path}")

            df = (
                self.spark.read.option("header", "true")
                .option("inferSchema", "false")
                .option("nullValue", "")
                .schema(schema)
                .csv(input_path)
            )

            # Always write to S3 bronze/
            output_path = self.config.get_s3_layer_path("bronze", dataset_name)
            logger.info(f"Writing to: {output_path}")

            with S3OperationMetricsContext("write_parquet"):
                df.write.mode("overwrite").parquet(output_path)

            # Count AFTER write — reads from Parquet (faster, no double S3 scan)
            row_count = self.spark.read.parquet(output_path).count()
            logger.info(f"{dataset_name} written to: {output_path} ({row_count} rows)")

            record_rows_processed("bronze", dataset_name, row_count)
            log_partition_processed(
                dataset_name=dataset_name,
                partition_date=self.execution_date_str,
                row_count=row_count,
                size_bytes=0,
            )

        except AnalysisException as e:
            raise DataSourceError(f"Failed to read {filename}: {str(e)}")
        except Exception as e:
            raise PersistenceError(f"Failed to write {dataset_name} to S3: {str(e)}")


if __name__ == "__main__":
    import sys

    execution_date = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--execution_date" and i + 2 < len(sys.argv):
            execution_date = sys.argv[i + 2]

    job = BronzeIngestJob(execution_date=execution_date)
    success = job.execute()
    sys.exit(0 if success else 1)
