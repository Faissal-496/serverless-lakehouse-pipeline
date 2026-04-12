#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Quality Checks Module
Validates data quality at each transformation layer
"""

from pyspark.sql import DataFrame
from pyspark.sql.functions import isnull

from lakehouse.monitoring.logging import logger


def check_null_columns(df: DataFrame, critical_cols: list) -> int:
    """
    Check for null values in critical columns.

    Args:
        df: PySpark DataFrame
        critical_cols: List of column names to check

    Returns:
        Count of rows with nulls in critical columns
    """
    null_condition = isnull(critical_cols[0])
    for col_name in critical_cols[1:]:
        null_condition = null_condition | isnull(col_name)

    null_count = df.filter(null_condition).count()

    if null_count > 0:
        logger.warning(f"Found {null_count} rows with null values in critical columns")

    return null_count


def check_duplicates(df: DataFrame, key_cols: list) -> int:
    """
    Check for duplicate records based on key columns.

    Args:
        df: PySpark DataFrame
        key_cols: List of column names forming the unique key

    Returns:
        Count of duplicate rows
    """
    duplicate_count = df.count() - df.dropDuplicates(key_cols).count()

    if duplicate_count > 0:
        logger.warning(f"Found {duplicate_count} duplicate records")

    return duplicate_count


def check_data_types(df: DataFrame, expected_types: dict) -> bool:
    """
    Validate column data types.

    Args:
        df: PySpark DataFrame
        expected_types: Dict of {column_name: expected_type}

    Returns:
        True if all types match, False otherwise
    """
    schema_dict = {field.name: field.dataType.typeName() for field in df.schema.fields}

    all_match = True
    for col_name, expected_type in expected_types.items():
        actual_type = schema_dict.get(col_name)
        if actual_type != expected_type:
            logger.error(f"Column '{col_name}': expected {expected_type}, got {actual_type}")
            all_match = False

    return all_match


def generate_data_quality_report(df: DataFrame, table_name: str) -> dict:
    """
    Generate comprehensive data quality report.

    Args:
        df: PySpark DataFrame
        table_name: Name of the table

    Returns:
        Dictionary with quality metrics
    """
    total_rows = df.count()

    report = {
        "table_name": table_name,
        "total_rows": total_rows,
        "columns": len(df.columns),
        "column_names": df.columns,
        "null_summary": {},
    }

    # Check nulls per column
    for col_name in df.columns:
        null_count = df.filter(isnull(col_name)).count()
        null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
        report["null_summary"][col_name] = {
            "null_count": null_count,
            "null_percentage": round(null_pct, 2),
        }

    logger.info(f"Quality Report for {table_name}:")
    logger.info(f"   Total Rows: {total_rows}")
    logger.info(f"   Columns: {len(df.columns)}")

    return report
