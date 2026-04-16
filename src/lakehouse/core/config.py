"""
Centralized Configuration Management for Lakehouse Platform.

All configuration comes from environment variables.
YAML spark config files have been removed; Spark settings are managed
by the spark-defaults-emr.conf file uploaded to S3 and passed to
EMR Serverless at job submission time.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from lakehouse.core.exceptions import ConfigurationError
from lakehouse.monitoring.logging import logger


class PlatformConfig:
    """
    Environment-variable-driven configuration.

    Priority:
    1. Environment variables (highest)
    2. Sensible defaults (lowest)
    """

    def __init__(
        self,
        app_env: Optional[str] = None,
        execution_date=None,
        **kwargs,
    ):
        self.app_env = app_env or os.getenv("APP_ENV", "prod")

        raw_date = execution_date or self._parse_execution_date()
        if isinstance(raw_date, str):
            try:
                self.execution_date = datetime.fromisoformat(raw_date)
            except ValueError:
                self.execution_date = datetime.strptime(raw_date, "%Y-%m-%d")
        else:
            self.execution_date = raw_date

        if not self.app_env:
            raise ConfigurationError("APP_ENV not set and no app_env provided")

        logger.info(f"Initializing PlatformConfig for environment: {self.app_env}")

        self._apply_env_defaults()
        self._apply_kwarg_overrides(kwargs)

        logger.info(f"Configuration loaded. Execution date: {self.execution_date}")

    # Internal helpers

    def _parse_execution_date(self) -> datetime:
        exec_date_str = os.getenv("EXECUTION_DATE")
        if exec_date_str:
            try:
                return datetime.fromisoformat(exec_date_str)
            except ValueError:
                logger.warning(
                    f"Invalid EXECUTION_DATE format: {exec_date_str}, using current date"
                )
        return datetime.now()

    def _apply_env_defaults(self):
        # S3
        self.s3_bucket = os.getenv("S3_BUCKET")
        if not self.s3_bucket:
            raise ConfigurationError("S3_BUCKET not configured")
        self.s3_logs_bucket = os.getenv("S3_LOGS_BUCKET", self.s3_bucket)
        self.s3_logs_prefix = os.getenv("S3_LOGS_PREFIX", "logs/lakehouse")

        # AWS region
        self.aws_region = os.getenv(
            "AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "eu-west-3")
        )

        # Glue
        self.glue_database = os.getenv("GLUE_DATABASE", "lakehouse")

        # EMR Serverless
        self.emr_application_id = os.getenv("EMR_APPLICATION_ID", "")
        self.emr_execution_role_arn = os.getenv("EMR_EXECUTION_ROLE_ARN", "")
        self.lakehouse_whl_s3 = os.getenv("LAKEHOUSE_WHL_S3", "")
        self.spark_conf_s3 = os.getenv("SPARK_CONF_S3", "")

        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")

        # Paths config loaded from paths.yaml if present
        self.paths = self._load_paths_yaml()

    def _load_paths_yaml(self) -> dict:
        """Load the lightweight paths.yaml file for S3 prefix mappings."""
        import yaml

        config_dir = Path(os.getenv("CONFIG_DIR", "/app/config"))
        paths_file = config_dir / "paths.yaml"
        if paths_file.exists():
            try:
                with open(paths_file, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load {paths_file}: {e}")
        return {}

    def _apply_kwarg_overrides(self, kwargs: Dict[str, Any]):
        for key, value in kwargs.items():
            if hasattr(self, key):
                logger.debug(f"Overriding config: {key} = {value}")
                setattr(self, key, value)

    # Properties

    @property
    def execution_date_str(self) -> str:
        return self.execution_date.strftime("%Y-%m-%d")

    @property
    def execution_year(self) -> int:
        return self.execution_date.year

    @property
    def execution_month(self) -> int:
        return self.execution_date.month

    @property
    def execution_day(self) -> int:
        return self.execution_date.day

    # Path helpers

    def get_s3_layer_path(
        self, layer: str, dataset: str, partitioned: bool = False
    ) -> str:
        layer_prefix = self.paths.get("paths", {}).get(layer, layer)
        base_path = f"s3a://{self.s3_bucket}/{layer_prefix}/{dataset}"
        if partitioned:
            return (
                f"{base_path}/year={self.execution_year}"
                f"/month={self.execution_month}"
                f"/day={self.execution_day}"
            )
        return base_path

    def get_s3_logs_path(self, job_name: str = "unknown") -> str:
        return (
            f"s3a://{self.s3_logs_bucket}/{self.s3_logs_prefix}/"
            f"job={job_name}/"
            f"year={self.execution_year}/"
            f"month={self.execution_month:02d}/"
            f"day={self.execution_day:02d}/"
            f"execution_date={self.execution_date_str}.json"
        )

    def get_input_path(self, filename: str) -> str:
        return f"s3a://{self.s3_bucket}/RAW/{filename}"

    def to_dict(self) -> dict:
        return {
            "app_env": self.app_env,
            "execution_date": self.execution_date_str,
            "s3_bucket": self.s3_bucket,
            "glue_database": self.glue_database,
            "emr_application_id": self.emr_application_id,
            "log_level": self.log_level,
        }

    def __repr__(self) -> str:
        return f"<PlatformConfig env={self.app_env} exec_date={self.execution_date_str}>"
