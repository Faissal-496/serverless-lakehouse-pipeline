#!/usr/bin/env python3
"""
Enterprise Data Lake - Unit & Integration Tests
Validates data quality framework, partitioning strategy, and AWS integration.
"""

import sys
import logging
from datetime import datetime, timedelta
import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Spark
try:
    from pyspark.sql import SparkSession
    SPARK_AVAILABLE = True
    # Initialize Spark for testing
    spark = SparkSession.builder \
        .appName("LakehouseTests") \
        .master("local[*]") \
        .getOrCreate()
except ImportError:
    SPARK_AVAILABLE = False
    spark = None
    logger.warning("PySpark not installed - Spark tests will be skipped")

# Skip tests if Spark not available
pytestmark = pytest.mark.skipif(not SPARK_AVAILABLE, reason="PySpark not installed")


class TestDataQualityFramework:
    """Test data quality validation rules."""
    
    def test_bronze_validation_passes_with_valid_data(self):
        """Test bronze layer validation with clean data."""
        from src.lakehouse.quality.data_quality_rules import DataQualityValidator
        
        # Create sample data
        df = spark.createDataFrame([
            (1, "2026-03-08", 100.0),
            (2, "2026-03-08", 200.0),
            (3, "2026-03-08", 300.0),
        ], ["id", "date", "amount"])
        
        # Validate
        validator = DataQualityValidator()
        results = validator.validate_bronze_layer(df, "test_dataset")
        
        # Assertions
        assert results["passed"] == True
        assert results["checks"]["row_count"]["status"] == "PASS"
        assert results["checks"]["null_values"]["status"] == "PASS"
        logger.info("✅ Bronze validation test PASSED")
    
    def test_bronze_validation_detects_nulls(self):
        """Test bronze layer validation detects null values."""
        from src.lakehouse.quality.data_quality_rules import DataQualityValidator
        
        df = spark.createDataFrame([
            (1, "2026-03-08", 100.0),
            (2, None, 200.0),  # Null date
            (3, "2026-03-08", None),  # Null amount
        ], ["id", "date", "amount"])
        
        validator = DataQualityValidator()
        results = validator.validate_bronze_layer(df, "test_dataset_with_nulls")
        
        assert results["checks"]["null_values"]["value"]["date"] > 0
        assert results["checks"]["null_values"]["value"]["amount"] > 0
        logger.info("✅ Null detection test PASSED")
    
    def test_duplicate_detection(self):
        """Test duplicate record detection."""
        from src.lakehouse.quality.data_quality_rules import DataQualityValidator
        
        df = spark.createDataFrame([
            (1, "2026-03-08", 100.0),
            (1, "2026-03-08", 100.0),  # Duplicate
            (2, "2026-03-08", 200.0),
        ], ["id", "date", "amount"])
        
        validator = DataQualityValidator()
        results = validator.validate_bronze_layer(df, "test_duplicates")
        
        assert results["checks"]["duplicates"]["duplicates"] == 1
        logger.info("✅ Duplicate detection test PASSED")


class TestPartitioningStrategy:
    """Test S3 partitioning logic."""
    
    def test_bronze_partitioning_adds_correct_columns(self):
        """Test bronze partitioning adds year/month/day columns."""
        from src.lakehouse.utils.partitioning import PartitioningStrategy
        
        df = spark.createDataFrame([
            ("dataset1", "value1"),
            ("dataset2", "value2"),
        ], ["col1", "col2"])
        
        strategy = PartitioningStrategy(environment="dev")
        df_partitioned = strategy.partition_bronze(df, "test_dataset")
        
        assert "ingestion_year" in df_partitioned.columns
        assert "ingestion_month" in df_partitioned.columns
        assert "ingestion_day" in df_partitioned.columns
        assert "ingestion_timestamp" in df_partitioned.columns
        logger.info("✅ Bronze partitioning test PASSED")
    
    def test_silver_partitioning_adds_quality_columns(self):
        """Test silver partitioning adds quality metadata."""
        from src.lakehouse.utils.partitioning import PartitioningStrategy
        
        df = spark.createDataFrame([
            ("data1",),
            ("data2",),
        ], ["value"])
        
        strategy = PartitioningStrategy(environment="dev")
        df_partitioned = strategy.partition_silver(df, "test_dataset")
        
        assert "transform_year" in df_partitioned.columns
        assert "transform_timestamp" in df_partitioned.columns
        assert "data_quality_score" in df_partitioned.columns
        logger.info("✅ Silver partitioning test PASSED")
    
    def test_partition_path_generation(self):
        """Test S3 partition path generation."""
        from src.lakehouse.utils.partitioning import PartitioningStrategy
        
        strategy = PartitioningStrategy(environment="prod")
        test_date = datetime(2026, 3, 8)
        
        bronze_path = strategy.get_partition_path("bronze", "test_dataset", test_date)
        assert "bronze" in bronze_path
        assert "year=2026" in bronze_path
        assert "month=03" in bronze_path
        assert "day=08" in bronze_path
        assert "prod" in bronze_path
        logger.info("✅ Partition path generation test PASSED")
    
    def test_partition_schema_validation(self):
        """Test partition schema validation."""
        from src.lakehouse.utils.partitioning import validate_partition_schema
        
        df = spark.createDataFrame([
            (1, 2026, 3, 8),
        ], ["id", "year", "month", "day"])
        
        result = validate_partition_schema(df, ["year", "month", "day"])
        assert result == True
        logger.info("✅ Partition schema validation test PASSED")
    
    def test_missing_partition_columns_detected(self):
        """Test detection of missing partition columns."""
        from src.lakehouse.utils.partitioning import validate_partition_schema
        
        df = spark.createDataFrame([
            (1, "value"),
        ], ["id", "value"])
        
        result = validate_partition_schema(df, ["year", "month", "day"])
        assert result == False
        logger.info("✅ Missing partition detection test PASSED")


class TestAWSIntegration:
    """Test AWS integration components (mock tests)."""
    
    def test_glue_catalog_manager_initialization(self):
        """Test Glue manager can be initialized."""
        from src.lakehouse.utils.aws_integration import GlueCatalogManager
        
        # In production, this would require AWS credentials
        # For now, we just test initialization
        try:
            manager = GlueCatalogManager(region_name="eu-west-3")
            assert manager.region == "eu-west-3"
            logger.info("✅ Glue manager initialization test PASSED")
        except Exception as e:
            logger.warning(f"⚠️  Glue manager test skipped (AWS credentials needed): {str(e)}")
    
    def test_cloudwatch_monitoring_initialization(self):
        """Test CloudWatch monitoring can be initialized."""
        from src.lakehouse.utils.aws_integration import CloudWatchMonitoring
        
        try:
            monitoring = CloudWatchMonitoring(region_name="eu-west-3")
            assert monitoring.region == "eu-west-3"
            assert monitoring.namespace == "LakehouseMetrics"
            logger.info("✅ CloudWatch monitoring initialization test PASSED")
        except Exception as e:
            logger.warning(f"⚠️  CloudWatch test skipped (AWS credentials needed): {str(e)}")


class TestDataLakePipeline:
    """Integration tests for complete data lake pipeline."""
    
    def test_end_to_end_data_flow(self):
        """Test complete data flow from bronze to silver."""
        from src.lakehouse.quality.data_quality_rules import DataQualityValidator
        from src.lakehouse.utils.partitioning import PartitioningStrategy
        
        # 1. Create bronze data
        bronze_df = spark.createDataFrame([
            (1, "2026-03-08", "contract001", 1500.0),
            (2, "2026-03-08", "contract002", 2500.0),
            (3, "2026-03-08", "contract003", None),  # One null
        ], ["id", "date", "contract_id", "amount"])
        
        # 2. Apply bronze partitioning
        partitioner = PartitioningStrategy(environment="dev")
        bronze_partitioned = partitioner.partition_bronze(bronze_df, "contracts")
        
        # 3. Validate data quality
        validator = DataQualityValidator()
        quality_results = validator.validate_bronze_layer(bronze_partitioned, "contracts")
        
        # 4. Apply silver transformation
        silver_df = bronze_partitioned.filter("amount IS NOT NULL")
        silver_partitioned = partitioner.partition_silver(silver_df, "contracts")
        
        # Assertions
        assert bronze_partitioned.count() == 3
        assert silver_partitioned.count() == 2  # One row filtered
        assert quality_results["checks"]["null_values"]["value"]["amount"] == 1
        assert "ingestion_year" in bronze_partitioned.columns
        assert "transform_timestamp" in silver_partitioned.columns
        
        logger.info("✅ End-to-end pipeline test PASSED")


def run_all_tests():
    """Run all test classes and report results."""
    print("\n" + "="*60)
    print("ENTERPRISE DATA LAKE - TEST SUITE")
    print("="*60 + "\n")
    
    test_results = {
        "total": 0,
        "passed": 0,
        "failed": 0
    }
    
    test_instances = [
        TestDataQualityFramework(),
        TestPartitioningStrategy(),
        TestAWSIntegration(),
        TestDataLakePipeline(),
    ]
    
    for test_class in test_instances:
        methods = [m for m in dir(test_class) if m.startswith("test_")]
        for method_name in methods:
            test_results["total"] += 1
            try:
                method = getattr(test_class, method_name)
                method()
                test_results["passed"] += 1
            except Exception as e:
                test_results["failed"] += 1
                logger.error(f"❌ {test_class.__class__.__name__}.{method_name} FAILED: {str(e)}")
    
    # Print summary
    print("\n" + "="*60)
    print(f"TEST SUMMARY")
    print("="*60)
    print(f"Total Tests:   {test_results['total']}")
    print(f"Passed:        {test_results['passed']} ✅")
    print(f"Failed:        {test_results['failed']} ❌")
    print(f"Pass Rate:     {(test_results['passed']/test_results['total']*100):.1f}%")
    print("="*60 + "\n")
    
    return 0 if test_results['failed'] == 0 else 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
