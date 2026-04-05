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
        **kwargs
    ):
        """
        Initialize platform configuration.
        
        Args:
            app_env: Environment (dev/prod). Defaults to APP_ENV env var
            execution_date: Execution date for parameterized jobs (important for backfill)
            **kwargs: Additional config overrides
        """
        # Runtime parameters
        self.app_env = app_env or os.getenv("APP_ENV", "dev")
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
        
        # Load base configurations
        self._load_yaml_configs()
        self._apply_env_overrides()
        self._apply_kwarg_overrides(kwargs)
        
        logger.info(f"Configuration loaded. Execution date: {self.execution_date}")

    def _parse_execution_date(self) -> datetime:
        """Parse execution_date from env var or use current date"""
        exec_date_str = os.getenv("EXECUTION_DATE")
        if exec_date_str:
            try:
                return datetime.fromisoformat(exec_date_str)
            except ValueError:
                logger.warning(f"Invalid EXECUTION_DATE format: {exec_date_str}, using current date")
        return datetime.now()

    def _load_yaml_configs(self):
        """Load YAML configurations for current environment"""
        config_dir = Path(os.getenv("CONFIG_DIR", "/opt/lakehouse/config"))
        
        # Load paths
        paths_file = config_dir / "paths.yaml"
        self.paths = self._load_yaml(paths_file) if paths_file.exists() else {}
        
        # Load environment-specific config
        env_file = config_dir / f"env/{self.app_env}.yaml"
        self.env_config = self._load_yaml(env_file) if env_file.exists() else {}
        
        # Load spark config
        spark_default_file = config_dir / "spark/default.yaml"
        spark_env_file = config_dir / f"spark/{self.app_env}.yaml"
        self.spark_config = {}
        if spark_default_file.exists():
            self.spark_config = self._load_yaml(spark_default_file).get("spark", {})
        if spark_env_file.exists():
            env_spark = self._load_yaml(spark_env_file).get("spark", {})
            self.spark_config.update(env_spark)

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        """Safely load YAML file"""
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            return {}

    def _apply_env_overrides(self):
        """Apply environment variable overrides"""
        # S3 Configuration
        self.s3_bucket = os.getenv("S3_BUCKET") or \
                        self.env_config.get("s3", {}).get("bucket")
        if not self.s3_bucket:
            raise ConfigurationError("S3_BUCKET not configured")
        
        # S3 Logs Configuration (for Airflow + Application logs)
        self.s3_logs_bucket = os.getenv("S3_LOGS_BUCKET", self.s3_bucket)
        self.s3_logs_prefix = os.getenv("S3_LOGS_PREFIX", "logs/lakehouse")
        
        # AWS Configuration
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        
        # Glue Configuration
        self.glue_database = os.getenv("GLUE_DATABASE") or \
                           self.env_config.get("glue", {}).get("database", "lakehouse")
        
        # Spark Configuration
        self.spark_master = os.getenv("SPARK_MASTER") or \
                           self.spark_config.get("master", "local[*]")
        self.spark_driver_memory = os.getenv("SPARK_DRIVER_MEMORY") or \
                                  self.spark_config.get("config", {}).get("spark.driver.memory", "2g")
        self.spark_executor_memory = os.getenv("SPARK_EXECUTOR_MEMORY") or \
                                   self.spark_config.get("config", {}).get("spark.executor.memory", "2g")
        
        # Logging Configuration
        self.log_level = os.getenv("LOG_LEVEL") or \
                        self.env_config.get("logging", {}).get("level", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")  # json or text
        self.enable_s3_logs = os.getenv("ENABLE_S3_LOGS", "true").lower() == "true"
        
        # Data paths
        self.data_base_path = Path(os.getenv("DATA_BASE_PATH", "/opt/lakehouse/data"))
        # Only create the local data directory in non-prod environments.
        # In prod all I/O goes to S3; /data does not exist in containers.
        if self.app_env != "prod":
            self.data_base_path.mkdir(parents=True, exist_ok=True)

    def _apply_kwarg_overrides(self, kwargs: Dict[str, Any]):
        """Apply keyword argument overrides (highest priority)"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                logger.debug(f"Overriding config: {key} = {value}")
                setattr(self, key, value)

    @property
    def execution_date_str(self) -> str:
        """Return execution date as YYYY-MM-DD string"""
        return self.execution_date.strftime("%Y-%m-%d")

    @property
    def execution_year(self) -> int:
        """Return execution year"""
        return self.execution_date.year

    @property
    def execution_month(self) -> int:
        """Return execution month"""
        return self.execution_date.month

    @property
    def execution_day(self) -> int:
        """Return execution day"""
        return self.execution_date.day

    def get_s3_layer_path(self, layer: str, dataset: str, partitioned: bool = False) -> str:
        """
        Get S3 path for a data layer.
        
        Args:
            layer: bronze, silver, or gold
            dataset: dataset name
            partitioned: if True, appends date partitioning
            
        Returns:
            S3 path (s3a://)
        """
        layer_prefix = self.paths.get("paths", {}).get(layer, layer)
        base_path = f"s3a://{self.s3_bucket}/{layer_prefix}/{dataset}"
        
        if partitioned:
            return f"{base_path}/year={self.execution_year}/month={self.execution_month}/day={self.execution_day}"
        
        return base_path

    def get_s3_logs_path(self, job_name: str = "unknown") -> str:
        """
        Get S3 path for job logs with date partitioning.
        
        Args:
            job_name: name of the job
            
        Returns:
            S3 path (s3a://)
        """
        return (
            f"s3a://{self.s3_logs_bucket}/{self.s3_logs_prefix}/"
            f"job={job_name}/"
            f"year={self.execution_year}/"
            f"month={self.execution_month:02d}/"
            f"day={self.execution_day:02d}/"
            f"execution_date={self.execution_date_str}.json"
        )

    def get_input_path(self, filename: str) -> str:
        """Get input path — S3 RAW prefix for prod, local data_base_path for dev"""
        if self.app_env == "prod":
            return f"s3a://{self.s3_bucket}/RAW/{filename}"
        return str(self.data_base_path / filename)

    def get_local_input_path(self, filename: str) -> str:
        """Get local input file path"""
        return str(self.data_base_path / filename)

    def get_local_output_path(self, layer: str, dataset: str) -> str:
        """
        Get local filesystem output path for a data layer (dev/test mode).
        
        Args:
            layer: bronze, silver, or gold
            dataset: dataset name
            
        Returns:
            Local filesystem path
        """
        return str(self.data_base_path / layer / dataset)

    def to_dict(self) -> dict:
        """Return configuration as dictionary (for logging/debugging)"""
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
