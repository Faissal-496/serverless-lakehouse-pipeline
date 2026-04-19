#!/usr/bin/env python3
"""Validate DAG files for syntax errors."""
import ast
import os
import sys

dag_dir = sys.argv[1] if len(sys.argv) > 1 else "orchestration/airflow/dags"
errors = 0
for f in os.listdir(dag_dir):
    if f.endswith(".py"):
        path = os.path.join(dag_dir, f)
        try:
            ast.parse(open(path).read())
            print(f"  OK: {f}")
        except SyntaxError as e:
            print(f"  FAIL: {f} - {e}")
            errors += 1
if errors:
    print(f"\n{errors} DAG(s) have syntax errors")
    sys.exit(1)
print(f"\nAll DAGs validated successfully")
