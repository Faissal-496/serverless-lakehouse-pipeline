#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abstract Base Job for Spark Pipeline Jobs
All spark-submit jobs must extend this class to ensure proper initialization,
error handling, metrics collection, and idempotency support
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pyspark.sql import SparkSession
from typing import Optional, Dict, Any
import uuid
import traceback

from lakehouse.core.config import PlatformConfig
from lakehouse.core.spark_factory import SparkFactory
from lakehouse.core.exceptions import LakehouseException
from lakehouse.monitoring.logging import logger, log_job_start, log_job_end
from lakehouse.monitoring.metrics import JobMetricsContext


class SparkJob(ABC):
    """
    Abstract base class for Spark ETL jobs.
    
    Provides:
    - Unified configuration management
    - Spark session factory
    - Structured logging and metrics
    - Error handling and recovery
    - Execution context (execution_id, execution_date)
    
    Usage:
        class MyJob(SparkJob):
            def run(self):
                # Your ETL logic here
                pass
        
        if __name__ == "__main__":
            job = MyJob()
            job.execute()
    """
    
    # Must be overridden by subclasses
    JOB_NAME: str = "UnnamedJob"
    
    def __init__(
        self,
        config: Optional[PlatformConfig] = None,
        execution_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Spark job.
        
        Args:
            config: PlatformConfig instance (created if not provided)
            execution_id: Unique execution ID (generated if not provided)
            **kwargs: Additional config overrides
        """
        self.execution_id = execution_id or str(uuid.uuid4())
        self.config = config or PlatformConfig(**kwargs)
        self.spark: Optional[SparkSession] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        logger.set_context(
            execution_id=self.execution_id,
            job_name=self.JOB_NAME,
            environment=self.config.app_env
        )
    
    def execute(self) -> bool:
        """
        Main entry point for job execution.
        Handles initialization, error handling, and cleanup.
        
        Returns:
            True if successful, False otherwise
        """
        self.start_time = datetime.now()
        
        log_job_start(
            job_name=self.JOB_NAME,
            execution_id=self.execution_id,
            execution_date=self.config.execution_date_str
        )
        
        try:
            with JobMetricsContext(self.JOB_NAME) as metrics:
                # Initialize Spark session
                self.spark = self._initialize_spark()
                
                # Execute job
                logger.info(f"Executing {self.JOB_NAME}")
                self.run()
                
                self.end_time = datetime.now()
                duration = (self.end_time - self.start_time).total_seconds()
                
                log_job_end(
                    job_name=self.JOB_NAME,
                    execution_id=self.execution_id,
                    duration_seconds=duration,
                    status="SUCCESS"
                )
                
                logger.info(f"{self.JOB_NAME} completed successfully in {duration:.2f}s")
                return True
        
        except Exception as e:
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds() if self.start_time else 0
            
            logger.error(
                f"{self.JOB_NAME} failed after {duration:.2f}s",
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True
            )
            
            log_job_end(
                job_name=self.JOB_NAME,
                execution_id=self.execution_id,
                duration_seconds=duration,
                status="FAILURE"
            )
            
            self._handle_error(e)
            return False
        
        finally:
            self._cleanup()
    
    def _initialize_spark(self) -> SparkSession:
        """Initialize Spark session with platform configuration"""
        logger.info("Initializing Spark session")
        spark = SparkFactory.create_session(
            app_name=self.JOB_NAME,
            config=self.config
        )
        logger.info(f"Spark session ready: {spark.sparkContext.appName}")
        return spark
    
    @abstractmethod
    def run(self):
        """
        Execute the job logic. Must be implemented by subclasses.
        
        Raises:
            LakehouseException: For any data or configuration errors
            Exception: For unexpected errors
        """
        pass
    
    def _handle_error(self, error: Exception):
        """
        Handle job errors. Can be overridden for custom error handling.
        
        Args:
            error: The exception that occurred
        """
        logger.error(
            f"Error handling for {self.JOB_NAME}",
            error_type=type(error).__name__
        )
        
        # Can implement custom recovery logic here
        # e.g., calling alerting, rollback, etc.
    
    def _cleanup(self):
        """Clean up resources (Spark session, temporary files, etc.)"""
        if self.spark:
            try:
                logger.info("Stopping Spark session")
                self.spark.stop()
                logger.info("Spark session stopped")
            except Exception as e:
                logger.error(f"Error stopping Spark session: {e}", exc_info=True)
    
    @property
    def execution_date(self) -> datetime:
        """Get execution date from configuration"""
        return self.config.execution_date
    
    @property
    def execution_date_str(self) -> str:
        """Get execution date as YYYY-MM-DD string"""
        return self.config.execution_date_str
    
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"id={self.execution_id[:8]}... "
            f"env={self.config.app_env} "
            f"date={self.execution_date_str}>"
        )
