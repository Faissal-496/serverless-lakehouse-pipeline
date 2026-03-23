#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spark Session Factory
Centralized Spark session creation with environment-aware configuration
"""

from pyspark.sql import SparkSession
from lakehouse.core.config import PlatformConfig
from lakehouse.monitoring.logging import logger


class SparkFactory:
    """Factory for creating configured Spark sessions"""

    @staticmethod
    def create_session(
        app_name: str,
        config: PlatformConfig,
        enable_hive: bool = True,
        enable_delta: bool = False,
    ) -> SparkSession:
        """
        Create a Spark session with platform configuration.
        
        Args:
            app_name: Application name for Spark UI
            config: PlatformConfig instance
            enable_hive: Enable HiveSQL support
            enable_delta: Enable Delta Lake support
            
        Returns:
            Configured SparkSession
        """
        logger.info(f"Creating Spark session: {app_name}")
        
        builder = (
            SparkSession.builder
            .appName(app_name)
            .master(config.spark_master)
        )
        
        # Enable Hive Metastore
        if enable_hive:
            builder = builder.enableHiveSupport()
        
        # Core Spark configuration
        builder = (
            builder
            .config("spark.driver.memory", config.spark_driver_memory)
            .config("spark.executor.memory", config.spark_executor_memory)
            .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
            .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        )
        
        # S3A Configuration (AWS credentials)
        if config.aws_access_key and config.aws_secret_key:
            builder = (
                builder
                .config("spark.hadoop.fs.s3a.access.key", config.aws_access_key)
                .config("spark.hadoop.fs.s3a.secret.key", config.aws_secret_key)
                .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
                .config("spark.hadoop.fs.s3a.path.style.access", "true")
            )
        
        # S3A tuning for performance
        builder = (
            builder
            .config("spark.hadoop.fs.s3a.block.size", "64m")
            .config("spark.hadoop.fs.s3a.multipart.size", "64m")
            .config("spark.hadoop.fs.s3a.threads.max", "20")
        )
        
        # Delta Lake (if enabled)
        if enable_delta:
            builder = (
                builder
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config(
                    "spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog"
                )
            )
        
        # Glue Catalog integration
        builder = (
            builder
            .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
            .config("spark.sql.catalog.glue_catalog.type", "glue")
            .config("spark.sql.catalog.glue_catalog.warehouse", f"s3a://{config.s3_bucket}/warehouse")
            .config("hive.metastore.glue.catalogId", config.glue_database)
        )
        
        spark = builder.getOrCreate()
        
        # Set log level
        spark.sparkContext.setLogLevel(config.log_level)
        
        logger.info(f"Spark session created successfully: {spark.sparkContext.appName}")
        logger.debug(f"Master: {spark.sparkContext.master}")
        logger.debug(f"S3 Bucket: {config.s3_bucket}")
        
        return spark

    @staticmethod
    def get_or_create_session(
        app_name: str,
        config: PlatformConfig,
        **kwargs
    ) -> SparkSession:
        """
        Get existing Spark session or create new one.
        Uses SparkSession.getOrCreate() for idempotency.
        """
        logger.info(f"Getting or creating Spark session: {app_name}")
        return SparkFactory.create_session(app_name, config, **kwargs)
