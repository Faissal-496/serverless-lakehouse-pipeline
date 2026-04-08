#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Metrics Module
Prometheus metrics with graceful fallback when prometheus_client is not installed.
"""

from pyspark.sql import DataFrame
from lakehouse.utils.helpers import safe_divide

import time

# ============================================================================
# BUSINESS METRICS
# ============================================================================


def retention_rate(df: DataFrame, active_col: str = "contrat_actif") -> float:
    total = df.count()
    active = df.filter(f"{active_col} = 1").count()
    return safe_divide(active, total) * 100


def market_share(df: DataFrame, active_col: str = "contrat_actif") -> float:
    total = df.count()
    active = df.filter(f"{active_col} = 1").count()
    return safe_divide(active, total) * 100


# ============================================================================
# PROMETHEUS METRICS — conditional import with no-op fallback
# ============================================================================

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

    class _NoOp:
        """No-op metric stub."""

        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def inc(self, amount=1):
            pass

        def set(self, value):
            pass

        def observe(self, value):
            pass

    Counter = _NoOp  # type: ignore[misc]
    Gauge = _NoOp  # type: ignore[misc]
    Histogram = _NoOp  # type: ignore[misc]

    def generate_latest() -> bytes:
        return b""


# Job Metrics
job_runs_total = Counter(
    "lakehouse_job_runs_total",
    "Total number of job runs",
    ["job_name", "status"],
)

job_duration_seconds = Histogram(
    "lakehouse_job_duration_seconds",
    "Job execution duration",
    ["job_name"],
    buckets=(30, 60, 120, 300, 600, 1800, 3600),
)

job_failures_total = Counter(
    "lakehouse_job_failures_total",
    "Total number of job failures",
    ["job_name", "error_type"],
)

# Data Metrics
rows_processed_total = Counter(
    "lakehouse_rows_processed_total",
    "Total rows processed",
    ["layer", "dataset"],
)

data_quality_checks = Counter(
    "lakehouse_dq_checks_total",
    "Data quality checks executed",
    ["dataset", "check_type", "result"],
)

data_quality_failures = Counter(
    "lakehouse_dq_failures_total",
    "Data quality check failures",
    ["dataset", "check_type", "severity"],
)

data_volume_bytes = Gauge(
    "lakehouse_data_volume_bytes",
    "Current data volume in storage",
    ["layer", "dataset"],
)

# S3 Metrics
s3_operations_total = Counter(
    "lakehouse_s3_operations_total",
    "Total S3 operations",
    ["operation", "status"],
)

s3_operation_duration_seconds = Histogram(
    "lakehouse_s3_operation_duration_seconds",
    "S3 operation duration",
    ["operation"],
    buckets=(1, 5, 10, 30, 60, 300),
)

# Spark Metrics
spark_tasks_succeeded = Counter(
    "lakehouse_spark_tasks_succeeded_total",
    "Spark tasks succeeded",
    ["job_name"],
)

spark_tasks_failed = Counter(
    "lakehouse_spark_tasks_failed_total",
    "Spark tasks failed",
    ["job_name"],
)


# ============================================================================
# CONTEXT MANAGERS
# ============================================================================


class JobMetricsContext:
    def __init__(self, job_name: str):
        self.job_name = job_name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if exc_type is not None:
            job_failures_total.labels(job_name=self.job_name, error_type=exc_type.__name__).inc()
            status = "FAILURE"
        else:
            status = "SUCCESS"

        job_runs_total.labels(job_name=self.job_name, status=status).inc()
        job_duration_seconds.labels(job_name=self.job_name).observe(duration)
        return False


class S3OperationMetricsContext:
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        status = "SUCCESS" if exc_type is None else "FAILURE"
        s3_operations_total.labels(operation=self.operation, status=status).inc()
        s3_operation_duration_seconds.labels(operation=self.operation).observe(duration)
        return False


# ============================================================================
# HELPERS
# ============================================================================


def record_rows_processed(layer: str, dataset: str, count: int):
    rows_processed_total.labels(layer=layer, dataset=dataset).inc(count)


def record_data_volume(layer: str, dataset: str, size_bytes: int):
    data_volume_bytes.labels(layer=layer, dataset=dataset).set(size_bytes)


def export_metrics() -> bytes:
    return generate_latest()
