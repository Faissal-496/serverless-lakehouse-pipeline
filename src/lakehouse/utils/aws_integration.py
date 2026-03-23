"""
AWS Glue Integration & CloudWatch Monitoring

Integrates AWS Glue Data Catalog for metadata management and CloudWatch for observability.
"""

import os
import boto3
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class GlueCatalogManager:
    """Manages AWS Glue Data Catalog operations."""
    
    def __init__(self, region_name: str | None = None):
        """Initialize Glue client."""
        resolved_region = region_name or os.getenv("AWS_REGION", "eu-west-3")
        self.glue_client = boto3.client("glue", region_name=resolved_region)
        self.region = resolved_region
    
    def create_database(self, database_name: str, description: str = "") -> bool:
        """Create Glue database."""
        try:
            self.glue_client.create_database(
                DatabaseInput={
                    "Name": database_name,
                    "Description": description,
                    "Parameters": {
                        "classification": "parquet",
                        "compressionType": "snappy"
                    }
                }
            )
            logger.info(f"Created Glue database: {database_name}")
            return True
        except self.glue_client.exceptions.AlreadyExistsException:
            logger.info(f"Database {database_name} already exists")
            return True
        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            return False
    
    def create_table(self, 
                    database_name: str,
                    table_name: str,
                    s3_location: str,
                    columns: Dict[str, str]) -> bool:
        """
        Create Glue table.
        
        Args:
            database_name: Target database
            table_name: Table name
            s3_location: S3 path
            columns: Dict of column_name -> data_type
        """
        try:
            column_list = [
                {"Name": col_name, "Type": col_type}
                for col_name, col_type in columns.items()
            ]
            
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
                        }
                    },
                    "PartitionKeys": [
                        {"Name": "year", "Type": "string"},
                        {"Name": "month", "Type": "string"},
                        {"Name": "day", "Type": "string"}
                    ]
                }
            )
            logger.info(f"Created Glue table: {database_name}.{table_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating table: {str(e)}")
            return False
    
    def update_table_partition(self, 
                              database_name: str,
                              table_name: str,
                              partition_values: list) -> bool:
        """Update table partition."""
        try:
            self.glue_client.batch_create_partition(
                DatabaseName=database_name,
                TableName=table_name,
                PartitionInputList=[
                    {
                        "Values": partition_values,
                        "StorageDescriptor": {
                            "Location": f"s3://lakehouse/{'/'.join(partition_values)}/"
                        }
                    }
                ]
            )
            logger.info(f"Updated partition for {table_name}: {partition_values}")
            return True
        except Exception as e:
            logger.error(f"Error updating partition: {str(e)}")
            return False


class CloudWatchMonitoring:
    """CloudWatch metrics and logging integration."""
    
    def __init__(self, region_name: str | None = None):
        """Initialize CloudWatch client."""
        resolved_region = region_name or os.getenv("AWS_REGION", "eu-west-3")
        self.cw_client = boto3.client("cloudwatch", region_name=resolved_region)
        self.logs_client = boto3.client("logs", region_name=resolved_region)
        self.region = resolved_region
        self.namespace = "LakehouseMetrics"
    
    def put_metric(self,
                  metric_name: str,
                  value: float,
                  unit: str = "None",
                  dimensions: Optional[Dict[str, str]] = None) -> bool:
        """
        Put custom metric to CloudWatch.
        
        Args:
            metric_name: Name of metric
            value: Metric value
            unit: Unit (Count, Seconds, Bytes, etc.)
            dimensions: Dict of dimension_name -> value
        """
        try:
            kwargs = {
                "Namespace": self.namespace,
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.utcnow()
            }
            
            if dimensions:
                kwargs["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in dimensions.items()
                ]
            
            self.cw_client.put_metric_data(**kwargs)
            logger.info(f"Published metric: {metric_name}={value} {unit}")
            return True
        except Exception as e:
            logger.error(f"Error publishing metric: {str(e)}")
            return False
    
    def put_job_metrics(self,
                       job_name: str,
                       duration_seconds: float,
                       records_processed: int,
                       status: str) -> bool:
        """
        Publish standard job metrics.
        
        Args:
            job_name: Name of job/task
            duration_seconds: Job duration
            records_processed: Number of records
            status: SUCCESS, FAILURE, PARTIAL
        """
        dims = {"JobName": job_name}
        
        metrics_to_publish = [
            ("JobDuration", duration_seconds, "Seconds"),
            ("RecordsProcessed", float(records_processed), "Count"),
        ]
        
        for metric_name, value, unit in metrics_to_publish:
            self.put_metric(metric_name, value, unit, dims)
        
        # Also publish status
        status_value = 1.0 if status == "SUCCESS" else 0.0
        self.put_metric("JobSuccess", status_value, "None", dims)
        
        logger.info(f"Published metrics for job: {job_name}")
        return True
    
    def create_log_stream(self, log_group: str, stream_name: str) -> bool:
        """Create CloudWatch log stream."""
        try:
            self.logs_client.create_log_stream(
                logGroupName=log_group,
                logStreamName=stream_name
            )
            logger.info(f"Created log stream: {log_group}/{stream_name}")
            return True
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            return True
        except Exception as e:
            logger.error(f"Error creating log stream: {str(e)}")
            return False
    
    def put_log_events(self,
                      log_group: str,
                      stream_name: str,
                      message: str,
                      log_level: str = "INFO") -> bool:
        """Put structured log to CloudWatch."""
        try:
            log_entry = {
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                "level": log_level,
                "message": message
            }
            
            self.logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                logEvents=[
                    {"timestamp": log_entry["timestamp"], "message": json.dumps(log_entry)}
                ]
            )
            return True
        except Exception as e:
            logger.error(f"Error putting log events: {str(e)}")
            return False


class DataLakeObservability:
    """High-level observability for data lake operations."""
    
    def __init__(self, region_name: str | None = None):
        """Initialize observability tools."""
        self.glue = GlueCatalogManager(region_name)
        self.cloudwatch = CloudWatchMonitoring(region_name)
    
    def record_ingestion_job(self,
                            dataset_name: str,
                            records_count: int,
                            duration_seconds: float,
                            status: str) -> None:
        """Record ingestion job metrics."""
        self.cloudwatch.put_job_metrics(
            job_name=f"ingestion_{dataset_name}",
            duration_seconds=duration_seconds,
            records_processed=records_count,
            status=status
        )
    
    def record_transformation_job(self,
                                 from_layer: str,
                                 to_layer: str,
                                 records_in: int,
                                 records_out: int,
                                 duration_seconds: float) -> None:
        """Record transformation job metrics."""
        job_name = f"transform_{from_layer}_to_{to_layer}"
        
        self.cloudwatch.put_metric(
            "RecordsProcessed",
            float(records_out),
            "Count",
            {"JobName": job_name}
        )
        
        self.cloudwatch.put_metric(
            "JobDuration",
            duration_seconds,
            "Seconds",
            {"JobName": job_name}
        )
        
        # Calculate efficiency
        if records_in > 0:
            efficiency = (records_out / records_in) * 100
            self.cloudwatch.put_metric(
                "TransformationEfficiency",
                efficiency,
                "Percent",
                {"JobName": job_name}
            )
