#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom Exceptions for Lakehouse Platform
Hierarchical exception structure for proper error handling
"""


class LakehouseException(Exception):
    """Base exception for all Lakehouse platform errors"""


class ConfigurationError(LakehouseException):
    """Configuration-related errors (missing vars, invalid YAML, etc.)"""


class DataSourceError(LakehouseException):
    """Data source connectivity or accessibility errors"""


class ValidationError(LakehouseException):
    """Data validation and quality errors"""


class SchemaError(ValidationError):
    """Schema mismatch or validation errors"""


class DataQualityError(ValidationError):
    """Data quality check failures"""


class TransformationError(LakehouseException):
    """Spark transformation errors"""


class PersistenceError(LakehouseException):
    """S3 write or storage errors"""


class BackfillError(LakehouseException):
    """Backfill-specific errors"""


class IdempotencyError(LakehouseException):
    """Idempotency constraint violations"""
