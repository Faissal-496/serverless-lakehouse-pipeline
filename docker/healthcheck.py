#!/usr/bin/env python3
"""
Health check script for Spark container.
Validates Python environment, Spark availability, and required configs.
"""

import sys
import os
from pathlib import Path

def check_python_environment():
    """Verify Python dependencies are available."""
    try:
        import pyspark
        import pandas
        import boto3
        return True
    except ImportError as e:
        print(f"Missing Python dependency: {e}", file=sys.stderr)
        return False

def check_spark_availability():
    """Verify Spark is accessible."""
    spark_home = os.environ.get('SPARK_HOME', '/opt/spark')
    spark_bin = Path(spark_home) / 'bin' / 'spark-submit'
    
    if not spark_bin.exists():
        print(f"Spark not found at {spark_bin}", file=sys.stderr)
        return False
    
    return True

def check_config_files():
    """Verify required configuration files exist."""
    required_paths = [
        '/opt/lakehouse/config/paths.yaml',
        '/opt/spark/conf/spark-defaults.conf',
    ]
    
    for path in required_paths:
        if not Path(path).exists():
            print(f"Config missing: {path}", file=sys.stderr)
            return False
    
    return True

def main():
    """Run all health checks."""
    print("Running Lakehouse health checks...", file=sys.stderr)
    
    checks = [
        ("Python environment", check_python_environment),
        ("Spark availability", check_spark_availability),
        ("Config files", check_config_files),
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        try:
            result = check_func()
            status = "OK" if result else "FAIL"
            print(f"{status} {check_name}", file=sys.stderr)
            all_passed = all_passed and result
        except Exception as e:
            print(f"ERROR {check_name}: {e}", file=sys.stderr)
            all_passed = False
    
    if all_passed:
        print("All health checks passed", file=sys.stderr)
        sys.exit(0)
    else:
        print("Some health checks failed", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
