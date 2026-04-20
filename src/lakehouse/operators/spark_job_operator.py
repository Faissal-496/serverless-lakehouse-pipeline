"""
SparkJobOperator — Custom Airflow operator for the Lakehouse ETL pipeline.

Supports two execution modes:
  - emr-serverless : submit + poll via boto3 (production default)
  - standalone     : spark-submit on the local Docker Spark cluster

The operator is intentionally *not* a BashOperator.  It builds the
command programmatically, streams logs into the Airflow task log, and
pushes key metrics (duration, job_run_id, status) into XCom.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from airflow.exceptions import AirflowException
from airflow.models import BaseOperator


class SparkJobOperator(BaseOperator):
    """
    Launch a PySpark job on EMR Serverless or a standalone Spark cluster.

    Parameters
    ----------
    job_name : str
        Logical name shown in UI and logs (e.g. ``bronze_ingest``).
    job_script : str
        Absolute path to the PySpark entry-point **inside the Airflow
        worker container** (standalone) or the *basename* that will be
        resolved to an S3 key (EMR Serverless).
    spark_mode : str
        ``"emr-serverless"`` (default) or ``"standalone"``.
    spark_config : dict
        Key/value Spark ``--conf`` pairs loaded from YAML.
    env_vars : dict
        Environment variables forwarded as ``spark.driverEnv.*`` /
        ``spark.executorEnv.*`` (EMR) or injected into the subprocess
        environment (standalone).
    """

    template_fields: Sequence[str] = ("execution_date_str",)
    ui_color = "#f4a460"
    ui_fgcolor = "#000000"

    # ------------------------------------------------------------------

    def __init__(
        self,
        *,
        job_name: str,
        job_script: str,
        spark_mode: str = "emr-serverless",
        # --- EMR Serverless ---
        emr_app_id: str = "",
        emr_execution_role_arn: str = "",
        s3_bucket: str = "",
        s3_scripts_prefix: str = "emr/scripts/lakehouse/jobs",
        s3_wheel_path: str = "",
        s3_venv_path: str = "",
        s3_logs_prefix: str = "logs/emr-serverless",
        aws_region: str = "eu-west-3",
        # --- Standalone ---
        spark_master: str = "spark://spark-master:7077",
        deploy_mode: str = "client",
        properties_file: str = "",
        # --- Common ---
        spark_config: Optional[Dict[str, str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        execution_date_str: str = "{{ ds }}",
        poll_interval: int = 15,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.job_name = job_name
        self.job_script = job_script
        self.spark_mode = spark_mode
        # EMR
        self.emr_app_id = emr_app_id
        self.emr_execution_role_arn = emr_execution_role_arn
        self.s3_bucket = s3_bucket
        self.s3_scripts_prefix = s3_scripts_prefix
        self.s3_wheel_path = s3_wheel_path
        self.s3_venv_path = s3_venv_path
        self.s3_logs_prefix = s3_logs_prefix
        self.aws_region = aws_region
        # Standalone
        self.spark_master = spark_master
        self.deploy_mode = deploy_mode
        self.properties_file = properties_file
        # Common
        self.spark_config = spark_config or {}
        self.env_vars = env_vars or {}
        self.execution_date_str = execution_date_str
        self.poll_interval = poll_interval

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute(self, context: Dict[str, Any]) -> str:
        start = time.time()
        self.log.info("Spark job '%s' starting (mode=%s)", self.job_name, self.spark_mode)

        try:
            if self.spark_mode == "emr-serverless":
                result = self._run_emr_serverless(context)
            elif self.spark_mode == "standalone":
                result = self._run_standalone(context)
            else:
                raise AirflowException(f"Unknown spark_mode: {self.spark_mode}")

            duration = time.time() - start
            self.log.info("Job '%s' succeeded in %.1fs", self.job_name, duration)
            context["ti"].xcom_push(key="duration_seconds", value=round(duration, 2))
            context["ti"].xcom_push(key="status", value="SUCCESS")
            return result

        except Exception:
            duration = time.time() - start
            context["ti"].xcom_push(key="duration_seconds", value=round(duration, 2))
            context["ti"].xcom_push(key="status", value="FAILED")
            raise

    # ------------------------------------------------------------------
    # EMR Serverless
    # ------------------------------------------------------------------

    def _run_emr_serverless(self, context: Dict[str, Any]) -> str:
        import boto3

        if not self.emr_app_id:
            raise AirflowException("EMR_APP_ID is not set. Add it to .env.docker and restart Airflow.")
        if not self.emr_execution_role_arn:
            raise AirflowException("EMR_EXECUTION_ROLE_ARN is not set. Add it to .env.docker and restart Airflow.")

        client = boto3.client("emr-serverless", region_name=self.aws_region)

        script_name = Path(self.job_script).name
        entry_point = f"s3://{self.s3_bucket}/{self.s3_scripts_prefix}/{script_name}"

        # --- Build sparkSubmitParameters ---
        parts: list[str] = []
        for k, v in self.spark_config.items():
            parts.append(f"--conf {k}={v}")
        for k, v in self.env_vars.items():
            parts.append(f"--conf spark.emr-serverless.driverEnv.{k}={v}")
            parts.append(f"--conf spark.executorEnv.{k}={v}")
        if self.s3_wheel_path:
            parts.append(f"--py-files {self.s3_wheel_path}")
        if self.s3_venv_path:
            parts.append(f"--conf spark.archives={self.s3_venv_path}#environment")
            parts.append("--conf spark.emr-serverless.driverEnv.PYSPARK_DRIVER_PYTHON=./environment/bin/python")
            parts.append("--conf spark.emr-serverless.driverEnv.PYSPARK_PYTHON=./environment/bin/python")
            parts.append("--conf spark.executorEnv.PYSPARK_PYTHON=./environment/bin/python")

        spark_params = " ".join(parts)
        run_name = f"lakehouse-{self.job_name}-{self.execution_date_str}"

        job_driver = {
            "sparkSubmit": {
                "entryPoint": entry_point,
                "entryPointArguments": ["--execution_date", self.execution_date_str],
                "sparkSubmitParameters": spark_params,
            }
        }

        monitoring = {
            "s3MonitoringConfiguration": {
                "logUri": f"s3://{self.s3_bucket}/{self.s3_logs_prefix}/",
            }
        }

        self.log.info("Submitting EMR Serverless job: %s", run_name)
        self.log.info("  entryPoint : %s", entry_point)
        self.log.info("  py-files   : %s", self.s3_wheel_path or "(none)")

        resp = client.start_job_run(
            applicationId=self.emr_app_id,
            executionRoleArn=self.emr_execution_role_arn,
            name=run_name,
            jobDriver=job_driver,
            configurationOverrides={"monitoringConfiguration": monitoring},
        )

        job_run_id: str = resp["jobRunId"]
        self.log.info("Job submitted — jobRunId=%s", job_run_id)
        context["ti"].xcom_push(key="emr_job_run_id", value=job_run_id)

        # --- Poll until terminal state ---
        terminal = {"SUCCESS", "FAILED", "CANCELLED"}
        while True:
            run = client.get_job_run(
                applicationId=self.emr_app_id,
                jobRunId=job_run_id,
            )
            state = run["jobRun"]["state"]
            self.log.info("  jobRunId=%s  state=%s", job_run_id, state)
            if state in terminal:
                break
            time.sleep(self.poll_interval)

        if state != "SUCCESS":
            details = run["jobRun"].get("stateDetails", "no details")
            raise AirflowException(f"EMR job {job_run_id} finished with state={state}: {details}")

        return job_run_id

    # ------------------------------------------------------------------
    # Standalone (local Docker Spark cluster)
    # ------------------------------------------------------------------

    def _run_standalone(self, context: Dict[str, Any]) -> str:
        cmd = [
            "spark-submit",
            "--master",
            self.spark_master,
            "--deploy-mode",
            self.deploy_mode,
        ]

        if self.properties_file:
            cmd.extend(["--properties-file", self.properties_file])

        for k, v in self.spark_config.items():
            cmd.extend(["--conf", f"{k}={v}"])

        for k, v in self.env_vars.items():
            cmd.extend(["--conf", f"spark.driverEnv.{k}={v}"])
            cmd.extend(["--conf", f"spark.executorEnv.{k}={v}"])

        cmd.append(self.job_script)
        cmd.extend(["--execution_date", self.execution_date_str])

        self.log.info("Running: %s", " ".join(cmd))

        env = os.environ.copy()
        env.update(self.env_vars)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
        )

        for line in iter(process.stdout.readline, ""):
            self.log.info(line.rstrip())

        rc = process.wait()
        if rc != 0:
            raise AirflowException(f"spark-submit exited with code {rc}")

        return str(rc)
