#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spark Session Factory
Centralized Spark session creation with environment-aware configuration.

When launched via spark-submit --properties-file, all Spark configs are already
set. This factory only adds the appName and optional master, then calls
getOrCreate() to inherit everything from the existing SparkContext.
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
        enable_hive: bool = False,
        enable_delta: bool = False,
    ) -> SparkSession:
        logger.info(f"Creating Spark session: {app_name}")

        builder = SparkSession.builder.appName(app_name)

        # Set master only when explicitly provided (not default local[*])
        if config.spark_master and config.spark_master != "local[*]":
            builder = builder.master(config.spark_master)

        if enable_hive:
            builder = builder.enableHiveSupport()

        # S3A credentials: only set if keys are available and NOT already configured
        # (spark-submit --properties-file may have already set these)
        if config.aws_access_key and config.aws_secret_key:
            builder = (
                builder.config("spark.hadoop.fs.s3a.access.key", config.aws_access_key)
                .config("spark.hadoop.fs.s3a.secret.key", config.aws_secret_key)
                .config(
                    "spark.hadoop.fs.s3a.impl",
                    "org.apache.hadoop.fs.s3a.S3AFileSystem",
                )
                .config("spark.hadoop.fs.s3a.path.style.access", "true")
            )

        spark = builder.getOrCreate()
        spark.sparkContext.setLogLevel(config.log_level)

        logger.info(f"Spark session created: {spark.sparkContext.appName}")
        logger.debug(f"Master: {spark.sparkContext.master}")
        logger.debug(f"S3 Bucket: {config.s3_bucket}")

        return spark
