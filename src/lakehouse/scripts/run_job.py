"""
Generic entrypoint for EMR Serverless Spark jobs.

Usage:
    spark-submit run_job.py --job-module lakehouse.jobs.bronze_ingest_job \
                            --execution-date 2026-04-13

The --job-module argument must point to a module that contains a class
inheriting from SparkJob. The first SparkJob subclass found is instantiated
and executed.
"""

import argparse
import importlib
import inspect
import sys

from lakehouse.jobs.base_job import SparkJob


def main():
    parser = argparse.ArgumentParser(description="Run a lakehouse Spark job")
    parser.add_argument("--job-module", required=True, help="Python module path")
    parser.add_argument("--execution-date", default=None, help="YYYY-MM-DD")
    args = parser.parse_args()

    module = importlib.import_module(args.job_module)

    # Find the first SparkJob subclass in the module
    job_class = None
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, SparkJob) and obj is not SparkJob:
            job_class = obj
            break

    if job_class is None:
        print(
            f"No SparkJob subclass found in {args.job_module}. "
            f"Ensure the module contains a class that inherits from SparkJob.",
            file=sys.stderr,
        )
        sys.exit(1)

    job = job_class(execution_date=args.execution_date)
    success = job.execute()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
