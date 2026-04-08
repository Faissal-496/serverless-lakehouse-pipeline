#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized Configuration Management for Lakehouse Platform
Provides unified configuration across all layers and environments
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import yaml

from lakehouse.core.exceptions import ConfigurationError
from lakehouse.monitoring.logging import logger


class PlatformConfig:
    """
    Centralized configuration management.

    Priority order:
    1. Environment variables (highest)
    2. YAML configurations
    3. Defaults (lowest)

    Supports runtime parameters like execution_date for backfill scenarios.
    """

    def __init__(
        self,
        app_env: Optional[str] = None,
        execution_date: Optional[datetime] = None,
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

        self._load_yaml_configs()
        self._apply_env_overrides()
        self._apply_kwarg_overrides(kwargs)

        logger.info(f"Configuration loaded. Execution date: {self.execution_date}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_execution_date(self) -> datetime:
        exec_date_str = os.getenv("EXECUTION_DATE")
        if exec_date_str:
            try:
                return datetime.fromisoformat(exec_date_str)
            except ValueError:
                logger.warning(f"Invalid EXECUTION_DATE format: {exec_date_str}, using current date")
        return datetime.now()

    def _load_yaml_configs(self):
        config_dir = Path(os.getenv("CONFIG_DIR", "/app/config"))

        # Load paths
        paths_file = config_dir / "paths.yaml"
        self.paths = self._load_yaml(paths_file) if paths_file.exists() else {}

        # Load environment-specific config (optional)
        env_file = config_dir / f"env/{self.app_env}.yaml"
        self.env_config = self._load_yaml(env_file) if env_file.exists() else {}

        # Load spark config: default then env overlay
        spark_default_file = config_dir / "spark/default.yaml"
        spark_env_file = config_dir / f"spark/{self.app_env}.yaml"
        self.spark_config: Dict[str, Any] = {}
        if spark_default_file.exists():
            self.spark_config = self._load_yaml(spark_default_file).get("spark", {})
        if spark_env_file.exists():
            env_spark = self._load_yaml(spark_env_file).get("spark", {})
            # Deep-merge config dicts
            base_cfg = self.spark_config.get("config", {})
            env_cfg = env_spark.get("config", {})
            base_cfg.update(env_cfg)
            self.spark_config.update(env_spark)
            self.spark_config["config"] = base_cfg

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            return {}

    def _apply_env_overrides(self):
        # S3
        self.s3_bucket = os.getenv("S3_BUCKET") or self.env_config.get("s3", {}).get("bucket")
        if not self.s3_bucket:
            raise ConfigurationError("S3_BUCKET not configured")

        self.s3_logs_bucket = os.getenv("S3_LOGS_BUCKET", self.s3_bucket)
        self.s3_logs_prefix = os.getenv("S3_LOGS_PREFIX", "logs/lakehouse")

        # AWS
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "eu-west-3"))

        # Glue
        self.glue_database = os.getenv("GLUE_DATABASE") or self.env_config.get("glue", {}).get("database", "lakehouse")

        # Spark
        self.spark_master = (
            os.getenv("SPARK_MASTER")
            or self.spark_config.get("config", {}).get("spark.master")
            or self.spark_config.get("master", "local[*]")
        )

        self.spark_driver_memory = os.getenv("SPARK_DRIVER_MEMORY") or self.spark_config.get("config", {}).get(
            "spark.driver.memory", "1g"
        )

        self.spark_executor_memory = os.getenv("SPARK_EXECUTOR_MEMORY") or self.spark_config.get("config", {}).get(
            "spark.executor.memory", "1g"
        )

        # Logging
        self.log_level = os.getenv("LOG_LEVEL") or self.env_config.get("logging", {}).get("level", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")
        self.enable_s3_logs = os.getenv("ENABLE_S3_LOGS", "true").lower() == "true"

        # Data paths
        self.data_base_path = Path(os.getenv("DATA_BASE_PATH", "/data"))

    def _apply_kwarg_overrides(self, kwargs: Dict[str, Any]):
        for key, value in kwargs.items():
            if hasattr(self, key):
                logger.debug(f"Overriding config: {key} = {value}")
                setattr(self, key, value)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_s3_layer_path(self, layer: str, dataset: str, partitioned: bool = False) -> str:
        layer_prefix = self.paths.get("paths", {}).get(layer, layer)
        base_path = f"s3a://{self.s3_bucket}/{layer_prefix}/{dataset}"
        if partitioned:
            return (
                f"{base_path}/year={self.execution_year}" f"/month={self.execution_month}" f"/day={self.execution_day}"
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
        """Always read from S3 RAW/ — prod is the default mode."""
        return f"s3a://{self.s3_bucket}/RAW/{filename}"

    def get_local_input_path(self, filename: str) -> str:
        return str(self.data_base_path / filename)

    def get_local_output_path(self, layer: str, dataset: str) -> str:
        return str(self.data_base_path / layer / dataset)

    def to_dict(self) -> dict:
        return {
            "app_env": self.app_env,
            "execution_date": self.execution_date_str,
            "s3_bucket": self.s3_bucket,
            "glue_database": self.glue_database,
            "spark_master": self.spark_master,
            "log_level": self.log_level,
            "log_format": self.log_format,
        }

    def __repr__(self) -> str:
        return f"<PlatformConfig env={self.app_env} exec_date={self.execution_date_str}>"
