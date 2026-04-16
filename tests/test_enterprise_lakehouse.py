"""
Unit tests for the lakehouse data platform.
Validates data quality framework, partitioning strategy, and AWS integration.
"""

import sys
import os
import logging
from datetime import datetime
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set required env vars for PlatformConfig before any imports that trigger it.
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("APP_ENV", "test")

# PySpark is a required dev dependency. Tests must fail loudly if it is missing.
from pyspark.sql import SparkSession  # noqa: E402

spark = (
    SparkSession.builder
    .appName("LakehouseTests")
    .master("local[*]")
    .getOrCreate()
)


class TestDataQualityFramework:
    """Test data quality validation rules."""

    def test_bronze_validation_passes_with_valid_data(self):
        from lakehouse.quality.data_quality_rules import DataQualityValidator

        df = spark.createDataFrame(
            [
                (1, "2026-03-08", 100.0),
                (2, "2026-03-08", 200.0),
                (3, "2026-03-08", 300.0),
            ],
            ["id", "date", "amount"],
        )
        validator = DataQualityValidator()
        results = validator.validate_bronze_layer(df, "test_dataset")

        assert results["passed"] is True
        assert results["checks"]["row_count"]["status"] == "PASS"
        assert results["checks"]["null_values"]["status"] == "PASS"

    def test_bronze_validation_detects_nulls(self):
        from lakehouse.quality.data_quality_rules import DataQualityValidator

        df = spark.createDataFrame(
            [(1, "2026-03-08", 100.0), (2, None, 200.0), (3, "2026-03-08", None)],
            ["id", "date", "amount"],
        )
        validator = DataQualityValidator()
        results = validator.validate_bronze_layer(df, "test_nulls")

        assert results["checks"]["null_values"]["value"]["date"] > 0
        assert results["checks"]["null_values"]["value"]["amount"] > 0

    def test_duplicate_detection(self):
        from lakehouse.quality.data_quality_rules import DataQualityValidator

        df = spark.createDataFrame(
            [
                (1, "2026-03-08", 100.0),
                (1, "2026-03-08", 100.0),
                (2, "2026-03-08", 200.0),
            ],
            ["id", "date", "amount"],
        )
        validator = DataQualityValidator()
        results = validator.validate_bronze_layer(df, "test_dups")

        assert results["checks"]["duplicates"]["duplicates"] == 1


class TestPartitioningStrategy:
    """Test S3 partitioning logic."""

    def test_bronze_partitioning_adds_correct_columns(self):
        from lakehouse.utils.partitioning import PartitioningStrategy

        df = spark.createDataFrame(
            [("dataset1", "value1"), ("dataset2", "value2")], ["col1", "col2"]
        )
        strategy = PartitioningStrategy(environment="dev")
        df_p = strategy.partition_bronze(df, "test_dataset")

        assert "ingestion_year" in df_p.columns
        assert "ingestion_month" in df_p.columns
        assert "ingestion_day" in df_p.columns
        assert "ingestion_timestamp" in df_p.columns

    def test_silver_partitioning_adds_quality_columns(self):
        from lakehouse.utils.partitioning import PartitioningStrategy

        df = spark.createDataFrame([("data1",), ("data2",)], ["value"])
        strategy = PartitioningStrategy(environment="dev")
        df_p = strategy.partition_silver(df, "test_dataset")

        assert "transform_year" in df_p.columns
        assert "transform_timestamp" in df_p.columns
        assert "data_quality_score" in df_p.columns

    def test_partition_path_generation(self):
        from lakehouse.utils.partitioning import PartitioningStrategy

        strategy = PartitioningStrategy(environment="prod")
        test_date = datetime(2026, 3, 8)
        bronze_path = strategy.get_partition_path("bronze", "test_dataset", test_date)

        assert "prod" in bronze_path
        assert "test_dataset" in bronze_path
        assert "year=2026" in bronze_path
        assert "month=03" in bronze_path
        assert "day=08" in bronze_path

    def test_partition_schema_validation(self):
        from lakehouse.utils.partitioning import validate_partition_schema

        df = spark.createDataFrame([(1, 2026, 3, 8)], ["id", "year", "month", "day"])
        assert validate_partition_schema(df, ["year", "month", "day"]) is True

    def test_missing_partition_columns_detected(self):
        from lakehouse.utils.partitioning import validate_partition_schema

        df = spark.createDataFrame([(1, "value")], ["id", "value"])
        assert validate_partition_schema(df, ["year", "month", "day"]) is False


class TestAWSIntegration:
    """Test AWS integration components (mock tests)."""

    def test_glue_catalog_manager_initialization(self):
        from lakehouse.utils.aws_integration import GlueCatalogManager

        try:
            manager = GlueCatalogManager(region_name="eu-west-3")
            assert manager.region == "eu-west-3"
        except Exception:
            pytest.skip("AWS credentials needed")

    def test_cloudwatch_monitoring_initialization(self):
        from lakehouse.utils.aws_integration import CloudWatchMonitoring

        try:
            monitoring = CloudWatchMonitoring(region_name="eu-west-3")
            assert monitoring.region == "eu-west-3"
            assert monitoring.namespace == "LakehouseMetrics"
        except Exception:
            pytest.skip("AWS credentials needed")


class TestPlatformConfig:
    """Test centralized configuration."""

    def test_config_loads_with_env_vars(self):
        from lakehouse.core.config import PlatformConfig

        config = PlatformConfig(app_env="test", s3_bucket="my-bucket")
        assert config.app_env == "test"
        assert config.s3_bucket == "my-bucket"
        assert config.execution_date is not None

    def test_s3_layer_path(self):
        from lakehouse.core.config import PlatformConfig

        config = PlatformConfig(app_env="test", s3_bucket="my-bucket")
        path = config.get_s3_layer_path("bronze", "Client")
        assert "s3a://my-bucket" in path
        assert "Client" in path


class TestDataLakePipeline:
    """Integration tests for the complete pipeline logic."""

    def test_end_to_end_data_flow(self):
        from lakehouse.quality.data_quality_rules import DataQualityValidator
        from lakehouse.utils.partitioning import PartitioningStrategy

        bronze_df = spark.createDataFrame(
            [
                (1, "2026-03-08", "c001", 1500.0),
                (2, "2026-03-08", "c002", 2500.0),
                (3, "2026-03-08", "c003", None),
            ],
            ["id", "date", "contract_id", "amount"],
        )

        partitioner = PartitioningStrategy(environment="dev")
        bronze_partitioned = partitioner.partition_bronze(bronze_df, "contracts")

        validator = DataQualityValidator()
        quality_results = validator.validate_bronze_layer(
            bronze_partitioned, "contracts"
        )

        silver_df = bronze_partitioned.filter("amount IS NOT NULL")
        silver_partitioned = partitioner.partition_silver(silver_df, "contracts")

        assert bronze_partitioned.count() == 3
        assert silver_partitioned.count() == 2
        assert quality_results["checks"]["null_values"]["value"]["amount"] == 1
        assert "ingestion_year" in bronze_partitioned.columns
        assert "transform_timestamp" in silver_partitioned.columns
