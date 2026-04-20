#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Structured Logging Module
Provides JSON-formatted logging for ELK/CloudWatch ingestion
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
import os

from pythonjsonlogger import jsonlogger


class StructuredLogger:
    """Structured logger with JSON output and contextual metadata"""

    def __init__(self, name: str, log_format: str = "json"):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            log_format: json or text
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Clear existing handlers
        self.logger.handlers = []

        # Console handler
        console_handler = logging.StreamHandler()

        if log_format == "json":
            formatter = jsonlogger.JsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s %(extra)s")
        else:
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Context for structured logging
        self.context: Dict[str, Any] = {
            "app_env": os.getenv("APP_ENV", "dev"),
        }

    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add context to log entry"""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            **self.context,
        }
        if extra:
            context.update(extra)
        return context

    def info(self, message: str, **extra):
        """Log info with structured context"""
        self.logger.info(message, extra={"extra": json.dumps(extra)} if extra else {})

    def error(self, message: str, exc_info: bool = False, **extra):
        """Log error with structured context"""
        self.logger.error(
            message,
            exc_info=exc_info,
            extra={"extra": json.dumps(extra)} if extra else {},
        )

    def warning(self, message: str, **extra):
        """Log warning with structured context"""
        self.logger.warning(message, extra={"extra": json.dumps(extra)} if extra else {})

    def debug(self, message: str, **extra):
        """Log debug with structured context"""
        self.logger.debug(message, extra={"extra": json.dumps(extra)} if extra else {})

    def set_context(self, **kwargs):
        """Set logger context (execution_id, user, etc.)"""
        self.context.update(kwargs)


# Global logger instance
_log_format = os.getenv("LOG_FORMAT", "json")
logger = StructuredLogger("lakehouse", log_format=_log_format)


# Convenience wrappers for structured logging
def log_job_start(job_name: str, execution_id: str, execution_date: str):
    """Log job start with metadata"""
    logger.info(
        f"Job started: {job_name}",
        job_name=job_name,
        execution_id=execution_id,
        execution_date=execution_date,
        event="job_start",
    )


def log_job_end(job_name: str, execution_id: str, duration_seconds: float, status: str):
    """Log job completion with metrics"""
    logger.info(
        f"Job completed: {job_name}",
        job_name=job_name,
        execution_id=execution_id,
        duration_seconds=duration_seconds,
        status=status,
        event="job_end",
    )


def log_data_quality(
    dataset_name: str,
    total_rows: int,
    failed_checks: int,
    check_results: Dict[str, Any],
):
    """Log data quality check results"""
    status = "PASS" if failed_checks == 0 else "FAIL"
    logger.info(
        f"Data Quality Check: {dataset_name}",
        dataset_name=dataset_name,
        total_rows=total_rows,
        failed_checks=failed_checks,
        status=status,
        details=check_results,
        event="dq_check",
    )


def log_partition_processed(dataset_name: str, partition_date: str, row_count: int, size_bytes: int):
    """Log partition processing"""
    logger.info(
        f"Partition processed: {dataset_name}/{partition_date}",
        dataset_name=dataset_name,
        partition_date=partition_date,
        row_count=row_count,
        size_mb=round(size_bytes / (1024 * 1024), 2),
        event="partition_processed",
    )


# ---------------------------------------------------------------------------
# DAG-level helpers (used by ETL_lakehouse.py)
# ---------------------------------------------------------------------------

def log_dag_event(dag_id: str, event: str, **extra):
    """Log a DAG-level lifecycle event (start / end / failure)."""
    logger.info(
        f"DAG {dag_id}: {event}",
        dag_id=dag_id,
        event=event,
        **extra,
    )


def log_quality_gate(dataset: str, layer: str, checks_passed: int, checks_failed: int, **extra):
    """Log a data-quality gate result."""
    status = "PASS" if checks_failed == 0 else "FAIL"
    logger.info(
        f"DQ gate {status}: {layer}/{dataset}  passed={checks_passed} failed={checks_failed}",
        dataset=dataset,
        layer=layer,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        status=status,
        event="dq_gate",
        **extra,
    )
