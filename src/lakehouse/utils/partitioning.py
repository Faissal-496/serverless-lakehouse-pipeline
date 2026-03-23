"""
S3 Data Lake Partitioning Strategy

Standardized partitioning patterns for enterprise lakehouse architecture.
Enables optimal query performance and cost efficiency.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pyspark.sql import DataFrame, functions as F
import logging

logger = logging.getLogger(__name__)


class PartitioningStrategy:
    """Implements standardized S3 partitioning schemas."""
    
    # Standard partition paths for bronze/silver/gold (using s3a:// for Spark compatibility)
    BRONZE_PARTITION_TEMPLATE = "s3a://lakehouse/{environment}/{dataset}/year={year}/month={month}/day={day}/"
    SILVER_PARTITION_TEMPLATE = "s3a://lakehouse/{environment}/silver/{dataset}/year={year}/month={month}/day={day}/"
    GOLD_PARTITION_TEMPLATE = "s3a://lakehouse/{environment}/gold/{aggregation_level}/{dataset}/year={year}/month={month}/day={day}/"
    
    def __init__(self, environment: str = "dev"):
        """
        Initialize partitioning strategy.
        
        Args:
            environment: dev, staging, or prod
        """
        self.environment = environment
    
    def partition_bronze(self, 
                        df: DataFrame, 
                        dataset_name: str, 
                        date_column: Optional[str] = None) -> DataFrame:
        """
        Apply bronze layer partitioning.
        
        Standard: year/month/day based on ingestion date
        
        Args:
            df: DataFrame to partition
            dataset_name: Name of dataset
            date_column: Date column for partitioning (if None, uses current date)
            
        Returns:
            DataFrame with partition columns added
        """
        if date_column and date_column in df.columns:
            # Use existing date column
            df = df.withColumn("ingestion_year", F.year(F.col(date_column))) \
                   .withColumn("ingestion_month", F.month(F.col(date_column))) \
                   .withColumn("ingestion_day", F.dayofmonth(F.col(date_column)))
        else:
            # Use current date
            current_date = F.current_date()
            df = df.withColumn("ingestion_year", F.year(current_date)) \
                   .withColumn("ingestion_month", F.month(current_date)) \
                   .withColumn("ingestion_day", F.dayofmonth(current_date))
        
        # Add ingestion timestamp
        df = df.withColumn("ingestion_timestamp", F.current_timestamp())
        
        return df
    
    def partition_silver(self,
                        df: DataFrame,
                        dataset_name: str,
                        date_column: Optional[str] = None) -> DataFrame:
        """
        Apply silver layer partitioning with quality metrics.
        
        Structure: year/month/day by transform date
        Adds data quality metadata
        
        Args:
            df: DataFrame to partition
            dataset_name: Name of dataset
            date_column: Date column for partitioning
            
        Returns:
            Partitioned DataFrame with quality columns
        """
        # Base partitioning
        if date_column and date_column in df.columns:
            df = df.withColumn("transform_year", F.year(F.col(date_column))) \
                   .withColumn("transform_month", F.month(F.col(date_column))) \
                   .withColumn("transform_day", F.dayofmonth(F.col(date_column)))
        else:
            current_date = F.current_date()
            df = df.withColumn("transform_year", F.year(current_date)) \
                   .withColumn("transform_month", F.month(current_date)) \
                   .withColumn("transform_day", F.dayofmonth(current_date))
        
        # Quality metadata
        df = df.withColumn("transform_timestamp", F.current_timestamp()) \
               .withColumn("data_quality_score", F.lit(0.0))  # Will be updated by QC
        
        return df
    
    def partition_gold(self,
                      df: DataFrame,
                      dataset_name: str,
                      aggregation_level: str = "daily") -> DataFrame:
        """
        Apply gold layer partitioning for analytics.
        
        Structure: aggregation_level/year/month/day
        Optimized for BI tool consumption
        
        Args:
            df: DataFrame to partition
            dataset_name: Name of dataset
            aggregation_level: daily, weekly, monthly, yearly
            
        Returns:
            Gold-ready partitioned DataFrame
        """
        # Ensure date column exists
        if "date" not in df.columns and "transaction_date" in df.columns:
            df = df.withColumn("date", F.col("transaction_date"))
        elif "date" not in df.columns:
            df = df.withColumn("date", F.current_date())
        
        # Partition columns
        df = df.withColumn("year", F.year(F.col("date"))) \
               .withColumn("month", F.month(F.col("date"))) \
               .withColumn("day", F.dayofmonth(F.col("date")))
        
        # Add aggregation level marker
        df = df.withColumn("aggregation_level", F.lit(aggregation_level))
        
        return df
    
    def get_partition_path(self, 
                          layer: str, 
                          dataset_name: str, 
                          date: datetime,
                          aggregation_level: Optional[str] = None) -> str:
        """
        Generate partition path for a dataset.
        
        Args:
            layer: bronze, silver, or gold
            dataset_name: Name of dataset
            date: Date for partition
            aggregation_level: For gold layer (daily, weekly, etc.)
            
        Returns:
            S3 path string
        """
        year = date.strftime("%Y")
        month = date.strftime("%m")
        day = date.strftime("%d")
        
        if layer == "bronze":
            return self.BRONZE_PARTITION_TEMPLATE.format(
                environment=self.environment,
                dataset=dataset_name,
                year=year,
                month=month,
                day=day
            )
        elif layer == "silver":
            return self.SILVER_PARTITION_TEMPLATE.format(
                environment=self.environment,
                dataset=dataset_name,
                year=year,
                month=month,
                day=day
            )
        elif layer == "gold":
            return self.GOLD_PARTITION_TEMPLATE.format(
                environment=self.environment,
                aggregation_level=aggregation_level or "daily",
                dataset=dataset_name,
                year=year,
                month=month,
                day=day
            )
        else:
            raise ValueError(f"Unknown layer: {layer}")
    
    def write_partitioned(self,
                        df: DataFrame,
                        s3_path: str,
                        partition_cols: List[str],
                        mode: str = "overwrite") -> None:
        """
        Write DataFrame with partition columns to S3.
        
        Args:
            df: DataFrame to write
            s3_path: Base S3 path
            partition_cols: Columns to partition by
            mode: write mode (overwrite, append, ignore, error)
        """
        try:
            df.write \
               .mode(mode) \
               .partitionBy(*partition_cols) \
               .parquet(s3_path)
            logger.info(f"Successfully wrote {len(partition_cols)}-way partitioned data to {s3_path}")
        except Exception as e:
            logger.error(f"Error writing partitioned data: {str(e)}")
            raise
    
    def optimize_partitioning(self, df: DataFrame, target_file_size_mb: int = 128) -> DataFrame:
        """
        Optimize DataFrame partitioning to target file size.
        
        Prevents small file problem in data lake.
        
        Args:
            df: DataFrame to optimize
            target_file_size_mb: Target file size in MB
            
        Returns:
            Repartitioned DataFrame
        """
        # Estimate data size
        row_count = df.count()
        estimated_bytes = df.rdd.map(lambda x: len(str(x))).sum()
        estimated_mb = estimated_bytes / (1024 ** 2)
        
        # Calculate optimal partition count
        if estimated_mb > 0:
            optimal_partitions = max(1, int(estimated_mb / target_file_size_mb))
        else:
            optimal_partitions = 1
        
        logger.info(f"Optimizing to {optimal_partitions} partitions (estimated size: {estimated_mb:.1f}MB)")
        
        return df.repartition(optimal_partitions)


def validate_partition_schema(df: DataFrame, expected_partitions: List[str]) -> bool:
    """
    Validate that DataFrame has expected partition columns.
    
    Args:
        df: DataFrame to validate
        expected_partitions: List of expected partition column names
        
    Returns:
        True if all partitions present, False otherwise
    """
    actual_columns = set(df.columns)
    expected_set = set(expected_partitions)
    
    if expected_set.issubset(actual_columns):
        logger.info(f"Partition schema valid: {expected_partitions}")
        return True
    else:
        missing = expected_set - actual_columns
        logger.error(f"Missing partition columns: {missing}")
        return False
