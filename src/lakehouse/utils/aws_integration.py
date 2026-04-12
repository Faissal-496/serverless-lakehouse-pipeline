"""
AWS Glue Integration & CloudWatch Monitoring
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import boto3

logger = logging.getLogger(__name__)


class GlueCatalogManager:
    """Manages AWS Glue Data Catalog operations."""

    def __init__(self, region_name: Optional[str] = None):
        resolved_region = region_name or os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
        self.glue_client = boto3.client("glue", region_name=resolved_region)
        self.region = resolved_region

    def create_database(self, database_name: str, description: str = "") -> bool:
        try:
            self.glue_client.create_database(
                DatabaseInput={
                    "Name": database_name,
                    "Description": description,
                    "Parameters": {
                        "classification": "parquet",
                        "compressionType": "snappy",
                    },
                }
            )
            logger.info(f"Created Glue database: {database_name}")
            return True
        except self.glue_client.exceptions.AlreadyExistsException:
            logger.info(f"Database {database_name} already exists")
            return True
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            return False

    def create_table(
        self,
        database_name: str,
        table_name: str,
        s3_location: str,
        columns: Dict[str, str],
    ) -> bool:
        try:
            column_list = [{"Name": col_name, "Type": col_type} for col_name, col_type in columns.items()]
            self.glue_client.create_table(
                DatabaseName=database_name,
                TableInput={
                    "Name": table_name,
                    "StorageDescriptor": {
                        "Columns": column_list,
                        "Location": s3_location,
                        "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                        "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                        "SerdeInfo": {
                            "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                        },
                    },
                    "PartitionKeys": [
                        {"Name": "year", "Type": "string"},
                        {"Name": "month", "Type": "string"},
                        {"Name": "day", "Type": "string"},
                    ],
                },
            )
            logger.info(f"Created Glue table: {database_name}.{table_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            return False

    def update_table_partition(
        self,
        database_name: str,
        table_name: str,
        s3_bucket: str,
        partition_values: List[str],
    ) -> bool:
        """Update table partition with configurable bucket."""
        try:
            partition_path = "/".join(partition_values)
            self.glue_client.batch_create_partition(
                DatabaseName=database_name,
                TableName=table_name,
                PartitionInputList=[
                    {
                        "Values": partition_values,
                        "StorageDescriptor": {
                            "Location": f"s3://{s3_bucket}/{partition_path}/",
                        },
                    }
                ],
            )
            logger.info(f"Updated partition for {table_name}: {partition_values}")
            return True
        except Exception as e:
            logger.error(f"Error updating partition: {e}")
            return False


class CloudWatchMonitoring:
    """CloudWatch metrics and logging integration."""

    def __init__(self, region_name: Optional[str] = None):
        resolved_region = region_name or os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
        self.cw_client = boto3.client("cloudwatch", region_name=resolved_region)
        self.logs_client = boto3.client("logs", region_name=resolved_region)
        self.region = resolved_region
        self.namespace = "LakehouseMetrics"

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
    ) -> bool:
        try:
            metric_data: Dict[str, Any] = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.utcnow(),
            }
            if dimensions:
                metric_data["Dimensions"] = [{"Name": k, "Value": v} for k, v in dimensions.items()]

            self.cw_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data],
            )
            logger.info(f"Published metric: {metric_name}={value} {unit}")
            return True
        except Exception as e:
            logger.error(f"Error publishing metric: {e}")
            return False

    def put_job_metrics(
        self,
        job_name: str,
        duration_seconds: float,
        records_processed: int,
        status: str,
    ) -> bool:
        dims = {"JobName": job_name}
        for metric_name, value, unit in [
            ("JobDuration", duration_seconds, "Seconds"),
            ("RecordsProcessed", float(records_processed), "Count"),
        ]:
            self.put_metric(metric_name, value, unit, dims)

        status_value = 1.0 if status == "SUCCESS" else 0.0
        self.put_metric("JobSuccess", status_value, "None", dims)
        logger.info(f"Published metrics for job: {job_name}")
        return True

    def create_log_stream(self, log_group: str, stream_name: str) -> bool:
        try:
            self.logs_client.create_log_stream(logGroupName=log_group, logStreamName=stream_name)
            return True
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            return True
        except Exception as e:
            logger.error(f"Error creating log stream: {e}")
            return False

    def put_log_events(
        self,
        log_group: str,
        stream_name: str,
        message: str,
        log_level: str = "INFO",
    ) -> bool:
        try:
            ts = int(datetime.utcnow().timestamp() * 1000)
            log_entry = {"timestamp": ts, "level": log_level, "message": message}
            self.logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                logEvents=[{"timestamp": ts, "message": json.dumps(log_entry)}],
            )
            return True
        except Exception as e:
            logger.error(f"Error putting log events: {e}")
            return False


class DataLakeObservability:
    """High-level observability for data lake operations."""

    def __init__(self, region_name: Optional[str] = None):
        self.glue = GlueCatalogManager(region_name)
        self.cloudwatch = CloudWatchMonitoring(region_name)

    def record_ingestion_job(
        self,
        dataset_name: str,
        records_count: int,
        duration_seconds: float,
        status: str,
    ) -> None:
        self.cloudwatch.put_job_metrics(
            job_name=f"ingestion_{dataset_name}",
            duration_seconds=duration_seconds,
            records_processed=records_count,
            status=status,
        )

    def record_transformation_job(
        self,
        from_layer: str,
        to_layer: str,
        records_in: int,
        records_out: int,
        duration_seconds: float,
    ) -> None:
        job_name = f"transform_{from_layer}_to_{to_layer}"
        self.cloudwatch.put_metric("RecordsProcessed", float(records_out), "Count", {"JobName": job_name})
        self.cloudwatch.put_metric("JobDuration", duration_seconds, "Seconds", {"JobName": job_name})
        if records_in > 0:
            efficiency = (records_out / records_in) * 100
            self.cloudwatch.put_metric(
                "TransformationEfficiency",
                efficiency,
                "Percent",
                {"JobName": job_name},
            )
