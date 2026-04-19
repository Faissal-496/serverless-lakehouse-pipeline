"""
Unit tests for monitoring/logging — no PySpark required.
Validates logger initialization and structured output.
"""

import pytest


class TestStructuredLogger:
    def test_logger_instance_exists(self):
        from lakehouse.monitoring.logging import logger

        assert logger is not None

    def test_logger_info_does_not_raise(self):
        from lakehouse.monitoring.logging import logger

        logger.info("test message", key="value")

    def test_logger_error_does_not_raise(self):
        from lakehouse.monitoring.logging import logger

        logger.error("error message", error_type="TestError")

    def test_logger_set_context(self):
        from lakehouse.monitoring.logging import logger

        logger.set_context(execution_id="abc-123", job_name="test_job")
        assert logger.context["execution_id"] == "abc-123"
        assert logger.context["job_name"] == "test_job"

    def test_log_job_start_does_not_raise(self):
        from lakehouse.monitoring.logging import log_job_start

        log_job_start("test_job", "exec-123", "2026-01-01")

    def test_log_job_end_does_not_raise(self):
        from lakehouse.monitoring.logging import log_job_end

        log_job_end("test_job", "exec-123", 10.5, "SUCCESS")


class TestJobMetricsContext:
    def test_context_manager_success(self):
        pytest.importorskip("pyspark")
        from lakehouse.monitoring.metrics import JobMetricsContext

        with JobMetricsContext("test_job") as ctx:
            assert ctx.job_name == "test_job"

    def test_context_manager_captures_failure(self):
        pytest.importorskip("pyspark")
        from lakehouse.monitoring.metrics import JobMetricsContext

        with pytest.raises(ValueError):
            with JobMetricsContext("test_job"):
                raise ValueError("intentional")
