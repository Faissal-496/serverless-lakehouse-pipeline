"""
Unit tests for PlatformConfig — no PySpark required.
These tests validate configuration loading, path generation,
and environment-based behavior.
"""

import os
import pytest
from unittest.mock import patch
from datetime import datetime


class TestPlatformConfigInit:
    """Test config initialization and env var handling."""

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "prod",
            "S3_BUCKET": "test-bucket",
            "AWS_DEFAULT_REGION": "eu-west-3",
            "CONFIG_DIR": "/nonexistent",
        },
    )
    def test_config_loads_with_required_env_vars(self):
        from lakehouse.core.config import PlatformConfig

        cfg = PlatformConfig()
        assert cfg.app_env == "prod"
        assert cfg.s3_bucket == "test-bucket"
        assert cfg.aws_region == "eu-west-3"

    @patch.dict(os.environ, {"APP_ENV": "prod", "CONFIG_DIR": "/nonexistent"}, clear=False)
    def test_config_fails_without_s3_bucket(self):
        env = os.environ.copy()
        env.pop("S3_BUCKET", None)
        with patch.dict(os.environ, env, clear=True):
            from lakehouse.core.config import PlatformConfig
            from lakehouse.core.exceptions import ConfigurationError

            with pytest.raises(ConfigurationError):
                PlatformConfig()

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "prod",
            "S3_BUCKET": "bucket",
            "CONFIG_DIR": "/nonexistent",
        },
    )
    def test_execution_date_defaults_to_now(self):
        from lakehouse.core.config import PlatformConfig

        cfg = PlatformConfig()
        assert cfg.execution_date.date() == datetime.now().date()

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "prod",
            "S3_BUCKET": "bucket",
            "CONFIG_DIR": "/nonexistent",
            "EXECUTION_DATE": "2026-03-15",
        },
    )
    def test_execution_date_from_env(self):
        from lakehouse.core.config import PlatformConfig

        cfg = PlatformConfig()
        assert cfg.execution_date_str == "2026-03-15"


class TestPlatformConfigPaths:
    """Test S3 path generation."""

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "prod",
            "S3_BUCKET": "my-bucket",
            "CONFIG_DIR": "/nonexistent",
        },
    )
    def _make_config(self):
        from lakehouse.core.config import PlatformConfig

        return PlatformConfig()

    def test_get_input_path(self):
        cfg = self._make_config()
        path = cfg.get_input_path("Client.csv")
        assert path == "s3a://my-bucket/RAW/Client.csv"

    def test_get_s3_layer_path_bronze(self):
        cfg = self._make_config()
        path = cfg.get_s3_layer_path("bronze", "Contrat2")
        assert "my-bucket" in path
        assert "Contrat2" in path

    def test_get_s3_layer_path_silver(self):
        cfg = self._make_config()
        path = cfg.get_s3_layer_path("silver", "Client_contrat_silver")
        assert "silver" in path.lower() or "Client_contrat_silver" in path

    def test_get_s3_layer_path_gold(self):
        cfg = self._make_config()
        path = cfg.get_s3_layer_path("gold", "contract_analysis")
        assert "contract_analysis" in path

    def test_get_s3_logs_path(self):
        cfg = self._make_config()
        path = cfg.get_s3_logs_path("bronze_ingest")
        assert "bronze_ingest" in path
        assert "s3a://" in path


class TestPlatformConfigOverrides:
    """Test kwarg and env var overrides."""

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "prod",
            "S3_BUCKET": "bucket",
            "CONFIG_DIR": "/nonexistent",
            "LOG_LEVEL": "DEBUG",
        },
    )
    def test_log_level_from_env(self):
        from lakehouse.core.config import PlatformConfig

        cfg = PlatformConfig()
        assert cfg.log_level == "DEBUG"

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "prod",
            "S3_BUCKET": "bucket",
            "CONFIG_DIR": "/nonexistent",
            "SPARK_DRIVER_MEMORY": "4g",
        },
    )
    def test_spark_driver_memory_override(self):
        from lakehouse.core.config import PlatformConfig

        cfg = PlatformConfig()
        assert cfg.spark_driver_memory == "4g"

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "prod",
            "S3_BUCKET": "original",
            "CONFIG_DIR": "/nonexistent",
        },
    )
    def test_to_dict(self):
        from lakehouse.core.config import PlatformConfig

        cfg = PlatformConfig()
        d = cfg.to_dict()
        assert d["app_env"] == "prod"
        assert d["s3_bucket"] == "original"
        assert "execution_date" in d
