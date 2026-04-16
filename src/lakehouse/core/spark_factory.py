"""
Spark Session Factory.

On EMR Serverless the SparkSession is pre-configured by the runtime.
This factory simply calls getOrCreate() and sets the app name.
S3A credentials come from the IAM execution role, not from env vars.
"""

from pyspark.sql import SparkSession
from lakehouse.core.config import PlatformConfig
from lakehouse.monitoring.logging import logger


class SparkFactory:
    """Creates or retrieves a Spark session."""

    @staticmethod
    def create_session(
        app_name: str,
        config: PlatformConfig,
        enable_hive: bool = False,
    ) -> SparkSession:
        logger.info(f"Creating Spark session: {app_name}")

        builder = SparkSession.builder.appName(app_name)

        if enable_hive:
            builder = builder.enableHiveSupport()

        spark = builder.getOrCreate()
        spark.sparkContext.setLogLevel(config.log_level)

        logger.info(f"Spark session created: {spark.sparkContext.appName}")
        logger.debug(f"Master: {spark.sparkContext.master}")
        return spark
