#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom Exceptions for Lakehouse Platform
Hierarchical exception structure for proper error handling
"""


class LakehouseException(Exception):
    """Base exception for all Lakehouse platform errors"""
    pass


class ConfigurationError(LakehouseException):
    """Configuration-related errors (missing vars, invalid YAML, etc.)"""
    pass


class DataSourceError(LakehouseException):
    """Data source connectivity or accessibility errors"""
    pass


class ValidationError(LakehouseException):
    """Data validation and quality errors"""
    pass


class SchemaError(ValidationError):
    """Schema mismatch or validation errors"""
    pass


class DataQualityError(ValidationError):
    """Data quality check failures"""
    pass


class TransformationError(LakehouseException):
    """Spark transformation errors"""
    pass


class PersistenceError(LakehouseException):
    """S3 write or storage errors"""
    pass


class BackfillError(LakehouseException):
    """Backfill-specific errors"""
    pass


class IdempotencyError(LakehouseException):
    """Idempotency constraint violations"""
    pass
