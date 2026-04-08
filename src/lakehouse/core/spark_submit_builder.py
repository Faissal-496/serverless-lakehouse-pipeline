#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spark Submit Builder
====================
Generates a spark-submit bash command string from YAML config + environment values.

Design principle
----------------
Static tuning values (memory, AQE flags, S3A settings, …) are resolved
once from the YAML file at DAG-parse time and baked as literals into the
command string.

Dynamic runtime values (master URL, deploy mode) are emitted as shell variable
references (e.g. ${SPARK_MASTER:-…}).  Bash expands them at task-execution time
using the env vars that Airflow passes via BashOperator(env=TASK_ENV).

AWS credentials and APP_ENV are read at DAG-parse time from the container
environment and embedded directly in --conf values (NOT as shell references),
because Spark does not interpret shell variable syntax.

Environment contract (set in TASK_ENV / container env)
-------------------------------------------------------
  SPARK_MASTER        Spark master URL.
                        Local:  spark://spark-master:7077
                        EMR:    yarn
  SPARK_DEPLOY_MODE   Driver placement.
                        Local:  client  (driver runs in Airflow worker)
                        EMR:    cluster (driver runs on EMR cluster)
  APP_ENV             prod | dev | emr (read at DAG-parse time)
  CONFIG_DIR          Path to config/ directory (read at DAG-parse time)
  AWS_ACCESS_KEY_ID   AWS credentials (read at DAG-parse time)
  AWS_SECRET_ACCESS_KEY
  AWS_DEFAULT_REGION
"""

import os
import yaml
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_yaml_config() -> dict:
    """
    Load the Spark YAML config for static tuning values.

    Always tries prod.yaml first (local Docker profile); falls back to an
    empty dict so the builder can still produce a runnable command.  The
    dynamic fields (master, deploy_mode) are handled separately via shell
    variable references, so the 'wrong' profile being loaded here does not
    affect correctness — only tuning knobs differ between profiles.
    """
    config_dir = os.getenv("CONFIG_DIR", "/app/config")
    # Try APP_ENV-specific file first, fall back to prod.yaml
    app_env = os.getenv("APP_ENV", "prod")
    spark_env = "emr" if app_env == "emr" else "prod"
    for profile in (spark_env, "prod", "default"):
        config_path = os.path.join(config_dir, "spark", f"{profile}.yaml")
        try:
            with open(config_path, "r") as fh:
                return yaml.safe_load(fh) or {}
        except FileNotFoundError:
            continue
    logger.warning("No Spark YAML config found — using empty config")
    return {}


def _build_env_conf_shell() -> dict:
    """
    Build spark.driverEnv.* and spark.executorEnv.* entries.

    AWS credentials and APP_ENV are read at DAG-parse time (from container env)
    and embedded directly, since Spark does NOT expand shell variable references
    in --conf values. Static defaults are used for unset vars.

    Other vars like SPARK_MASTER are handled separately as shell references.
    """
    # Read values from environment at DAG-parse time
    app_env = os.getenv("APP_ENV", "prod")
    config_dir = os.getenv("CONFIG_DIR", "/app/config")
    aws_key = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")

    # Log if credentials are missing
    if not aws_key or not aws_secret:
        logger.warning(
            "AWS credentials not set in environment! "
            "S3 read/write will fail. Set AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY in .env.docker or container environment."
        )

    driver_env = {
        "spark.driverEnv.PYTHONPATH": "/app/src",
        "spark.driverEnv.PYSPARK_PYTHON": "/home/airflow/.local/bin/python3",
        "spark.driverEnv.PYSPARK_DRIVER_PYTHON": "/home/airflow/.local/bin/python3",
        "spark.driverEnv.APP_ENV": app_env,
        "spark.driverEnv.CONFIG_DIR": config_dir,
        "spark.driverEnv.DATA_BASE_PATH": "/data",
        "spark.driverEnv.AWS_ACCESS_KEY_ID": aws_key,
        "spark.driverEnv.AWS_SECRET_ACCESS_KEY": aws_secret,
        "spark.driverEnv.AWS_DEFAULT_REGION": aws_region,
    }
    executor_env = {
        "spark.executorEnv.PYTHONPATH": "/app/src",
        "spark.executorEnv.PYSPARK_PYTHON": "/usr/bin/python3",
        "spark.executorEnv.APP_ENV": app_env,
        "spark.executorEnv.CONFIG_DIR": config_dir,
        "spark.executorEnv.DATA_BASE_PATH": "/data",
        "spark.executorEnv.AWS_ACCESS_KEY_ID": aws_key,
        "spark.executorEnv.AWS_SECRET_ACCESS_KEY": aws_secret,
        "spark.executorEnv.AWS_DEFAULT_REGION": aws_region,
    }
    return {**driver_env, **executor_env}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_spark_submit_command(app_file: str, extra_args: str = "") -> str:
    """
    Build a complete spark-submit command string.

    Static Spark tuning values (memory, AQE, S3A) come from the YAML file
    and are baked into the string at call time.  Dynamic values (master,
    deploy mode, AWS credentials, APP_ENV) are shell variable references
    resolved by bash at task-execution time.

    Args:
        app_file:   Absolute path to the PySpark script.
        extra_args: Additional arguments appended after the script path
                    (e.g. '--execution_date "$EXECUTION_DATE"').

    Returns:
        A multiline bash-compatible string for use as BashOperator
        bash_command (or embedded inside a larger bash script).
    """
    raw = _load_yaml_config()
    spark_section = raw.get("spark", {})
    yaml_conf = spark_section.get("config", {}) or {}

    # master and deploy-mode are shell var refs — resolved at bash runtime
    master_ref = "${SPARK_MASTER:-spark://spark-master:7077}"
    deploy_ref = "${SPARK_DEPLOY_MODE:-client}"

    # Merge: YAML static conf (low priority) + shell-ref env conf (high priority)
    env_conf = _build_env_conf_shell()
    merged = {**yaml_conf, **env_conf}

    # Build --conf fragment (one per line for readability in logs)
    conf_lines = [f"--conf {k}={v}" for k, v in merged.items()]

    parts = (
        ["spark-submit", f"--master {master_ref}", f"--deploy-mode {deploy_ref}"]
        + conf_lines
        + [app_file]
        + ([extra_args] if extra_args else [])
    )

    cmd = " \\\n            ".join(parts)

    # Echo block printed before spark-submit so the actual command appears
    # clearly in Airflow task logs (values are bash-expanded at runtime)
    echo_block = (
        'echo "spark-submit  master=${SPARK_MASTER:-spark://spark-master:7077}'
        '  deploy_mode=${SPARK_DEPLOY_MODE:-client}"\n'
        f'        echo "app={app_file}"\n'
        '        echo "---"\n'
    )
    return echo_block + "        " + cmd
