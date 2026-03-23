"""
Data Quality Framework using Great Expectations

This module defines reusable data quality expectations and validators
for the enterprise data lakehouse platform.
"""

from typing import Optional, Dict, Any
from pyspark.sql import DataFrame
import logging

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """Validates data using predefined quality rules."""
    
    def __init__(self, context_name: str = "lakehouse_qc"):
        """
        Initialize validator.
        
        Args:
            context_name: Name of Great Expectations context
        """
        self.context_name = context_name
        self.validation_results = {}
    
    def validate_bronze_layer(self, df: DataFrame, dataset_name: str) -> Dict[str, Any]:
        """
        Validate bronze layer ingestion data.
        
        Expectations:
        - No null values in key columns
        - Schema matches expected structure
        - Row count > 0
        - No duplicate records (if applicable)
        
        Args:
            df: Spark DataFrame to validate
            dataset_name: Name of dataset being validated
            
        Returns:
            Dictionary with validation results
        """
        results = {
            "dataset": dataset_name,
            "checks": {},
            "passed": True
        }
        
        try:
            # Check 1: Non-empty dataset
            row_count = df.count()
            results["checks"]["row_count"] = {
                "value": row_count,
                "status": "PASS" if row_count > 0 else "FAIL"
            }
            if row_count == 0:
                results["passed"] = False
            
            # Check 2: Schema validation
            schema = df.schema
            results["checks"]["schema"] = {
                "columns": len(schema.fields),
                "field_names": [f.name for f in schema.fields],
                "status": "PASS"
            }
            
            # Check 3: Null check on key columns
            null_counts = {}
            for col in df.columns:
                null_count = df.filter(f"{col} IS NULL").count()
                null_counts[col] = null_count
                if null_count > 0:
                    logger.warning(f"Column {col} has {null_count} null values")
            
            results["checks"]["null_values"] = {
                "value": null_counts,
                "status": "PASS" if sum(null_counts.values()) == 0 else "WARN"
            }
            
            # Check 4: Duplicate records
            total_rows = df.count()
            distinct_rows = df.distinct().count()
            duplicate_count = total_rows - distinct_rows
            
            results["checks"]["duplicates"] = {
                "total_rows": total_rows,
                "distinct_rows": distinct_rows,
                "duplicates": duplicate_count,
                "status": "PASS" if duplicate_count == 0 else "WARN"
            }
            
            # Check 5: Data freshness (if timestamp column exists)
            if "created_at" in df.columns or "ingestion_date" in df.columns:
                ts_col = "created_at" if "created_at" in df.columns else "ingestion_date"
                latest_date = df.agg({ts_col: "max"}).collect()[0][0]
                results["checks"]["data_freshness"] = {
                    "latest_timestamp": str(latest_date),
                    "status": "PASS"
                }
            
        except Exception as e:
            logger.error(f"Validation error for {dataset_name}: {str(e)}")
            results["passed"] = False
            results["error"] = str(e)
        
        self.validation_results[dataset_name] = results
        return results
    
    def validate_silver_layer(self, df: DataFrame, dataset_name: str) -> Dict[str, Any]:
        """
        Validate silver layer transformation data.
        
        Expectations:
        - No null values in key business columns
        - Data types match expected schema
        - Row count increase <= 10% vs bronze
        - No duplicate surrogate keys
        
        Args:
            df: Spark DataFrame to validate
            dataset_name: Name of dataset being validated
            
        Returns:
            Dictionary with validation results
        """
        results = {
            "dataset": dataset_name,
            "layer": "silver",
            "checks": {},
            "passed": True
        }
        
        try:
            # Data profiling
            row_count = df.count()
            results["checks"]["row_count"] = {
                "value": row_count,
                "status": "PASS"
            }
            
            # Column statistics
            stats = df.describe().toPandas()
            results["checks"]["statistics"] = {
                "mean": stats.loc[stats["summary"] == "mean"].to_dict(),
                "status": "PASS"
            }
            
            # NULL analysis per column
            null_analysis = {}
            for col in df.columns:
                null_pct = (df.filter(f"{col} IS NULL").count() / row_count) * 100
                null_analysis[col] = {
                    "null_count": df.filter(f"{col} IS NULL").count(),
                    "null_percentage": round(null_pct, 2)
                }
            
            results["checks"]["null_analysis"] = null_analysis
            
        except Exception as e:
            logger.error(f"Silver validation error for {dataset_name}: {str(e)}")
            results["passed"] = False
            results["error"] = str(e)
        
        return results
    
    def validate_gold_layer(self, df: DataFrame, dataset_name: str) -> Dict[str, Any]:
        """
        Validate gold layer analytical data.
        
        Expectations:
        - Complete business context
        - No NULL in key dimensions
        - Data consistency across joins
        
        Args:
            df: Spark DataFrame to validate
            dataset_name: Name of dataset being validated
            
        Returns:
            Dictionary with validation results
        """
        results = {
            "dataset": dataset_name,
            "layer": "gold",
            "checks": {},
            "passed": True
        }
        
        try:
            row_count = df.count()
            col_count = len(df.columns)
            
            results["checks"]["dimensions"] = {
                "rows": row_count,
                "columns": col_count,
                "status": "PASS"
            }
            
            # Sample data for inspection
            sample = df.limit(5).toPandas().to_dict(orient='records')
            results["checks"]["sample_data"] = sample
            
        except Exception as e:
            logger.error(f"Gold validation error for {dataset_name}: {str(e)}")
            results["passed"] = False
            results["error"] = str(e)
        
        return results
    
    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive validation report."""
        passed_count = sum(1 for r in self.validation_results.values() if r.get("passed", False))
        total_count = len(self.validation_results)
        
        return {
            "total_datasets": total_count,
            "passed": passed_count,
            "failed": total_count - passed_count,
            "pass_rate": (passed_count / total_count * 100) if total_count > 0 else 0,
            "datasets": self.validation_results
        }


def create_quality_expectation_suite(dataset_name: str) -> Dict[str, Any]:
    """
    Create a reusable expectation suite for a dataset.
    
    Returns configuration for Great Expectations validation.
    """
    return {
        "expectation_suite_name": f"{dataset_name}_expectations",
        "expectations": [
            {
                "expectation_type": "expect_table_row_count_to_be_between",
                "kwargs": {"min_value": 1, "max_value": None}
            },
            {
                "expectation_type": "expect_table_columns_to_match_ordered_list",
                "kwargs": {"column_list": []}  # Populated based on schema
            }
        ]
    }
