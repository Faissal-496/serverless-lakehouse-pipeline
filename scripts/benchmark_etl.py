#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETL Pipeline Benchmark Script
Compares performance across 3 cluster configurations:
1. Local mode (current): local[*]
2. Spark Standalone (simulated EMR): local cluster
3. (EMR Serverless - future)
"""

import os
import sys
import time
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyspark.sql import SparkSession
from lakehouse.paths import PathResolver
from lakehouse.monitoring.logging import logger


class ETLBenchmark:
    """Benchmark ETL stages across different Spark configurations"""
    
    def __init__(self, app_name):
        self.app_name = app_name
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "stages": {}
        }
        self.spark = None
        self.resolver = None
    
    def init_spark(self, master, app_name, config_path=None):
        """Initialize Spark based on master URL"""
        builder = SparkSession.builder \
            .appName(f"{app_name} - {master.split('://')[0].upper()}") \
            .master(master)
        
        # Add configurations if provided
        if config_path and os.path.exists(config_path):
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f).get('spark', {}).get('config', {})
                for key, val in config.items():
                    # Skip master if it's in config
                    if key != 'spark.master':
                        builder = builder.config(key, str(val))
        
        self.spark = builder.getOrCreate()
        self.resolver = PathResolver()
        
        return self.spark
    
    def benchmark_stage(self, stage_name, func):
        """Run a transformation and measure time"""
        print(f"\n{'='*60}")
        print(f"📊 Stage: {stage_name}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            result = func()
            elapsed = time.time() - start_time
            
            self.results["stages"][stage_name] = {
                "status": "SUCCESS",
                "duration_seconds": elapsed,
                "duration_human": format_duration(elapsed)
            }
            
            print(f"✅ {stage_name}: {format_duration(elapsed)}")
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.results["stages"][stage_name] = {
                "status": "FAILED",
                "duration_seconds": elapsed,
                "error": str(e)
            }
            print(f"❌ {stage_name} FAILED after {format_duration(elapsed)}: {str(e)}")
            raise
    
    def run_bronze_ingestion(self):
        """Test bronze ingestion performance"""
        from lakehouse.ingestion.bronze_ingest import ingest_bronze_data
        
        def _run():
            # Simulate bronze ingestion
            logger.info("Bronze ingestion started")
            # If you have a dedicated function, use it; otherwise use spark-submit
            return {"status": "completed"}
        
        return self.benchmark_stage("bronze_ingestion", _run)
    
    def run_bronze_to_silver(self):
        """Test bronze-to-silver transformation"""
        from lakehouse.transformation.bronze_to_silver import run as bronze_to_silver
        
        def _run():
            bronze_to_silver(self.spark, self.resolver)
            return {"status": "completed"}
        
        return self.benchmark_stage("bronze_to_silver", _run)
    
    def run_silver_to_gold(self):
        """Test silver-to-gold transformation"""
        from lakehouse.transformation.silver_to_gold import run as silver_to_gold
        
        def _run():
            silver_to_gold(self.spark, self.resolver)
            return {"status": "completed"}
        
        return self.benchmark_stage("silver_to_gold", _run)
    
    def run_full_pipeline(self):
        """Run complete ETL pipeline"""
        print(f"\n{'#'*60}")
        print(f"# RUNNING FULL ETL PIPELINE")
        print(f"{'#'*60}")
        
        start_total = time.time()
        
        try:
            self.run_bronze_to_silver()
            self.run_silver_to_gold()
            
            total_duration = time.time() - start_total
            self.results["total_duration_seconds"] = total_duration
            self.results["total_duration_human"] = format_duration(total_duration)
            
            return total_duration
            
        except Exception as e:
            print(f"\n❌ Pipeline failed: {str(e)}")
            raise
    
    def cleanup(self):
        """Stop Spark session"""
        if self.spark:
            self.spark.stop()
    
    def save_results(self, output_path="/tmp/etl-benchmark-results.json"):
        """Save benchmark results"""
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n✅ Benchmark results saved to: {output_path}")
        return output_path


def format_duration(seconds):
    """Format seconds to human-readable duration"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def run_benchmark(master, config_name, config_path=None):
    """Run complete benchmark for a cluster configuration"""
    print(f"\n{'*'*60}")
    print(f"* BENCHMARK: {config_name}")
    print(f"* Master: {master}")
    print(f"{'*'*60}")
    
    benchmark = ETLBenchmark("ETL-Benchmark")
    
    try:
        # Initialize Spark
        benchmark.init_spark(master, "ETL-Benchmark", config_path)
        
        # Run pipeline
        total_duration = benchmark.run_full_pipeline()
        
        # Save results
        results_path = benchmark.save_results(
            f"/tmp/etl-benchmark-results-{config_name}.json"
        )
        
        print(f"\n{'='*60}")
        print(f"✅ BENCHMARK COMPLETE")
        print(f"{'='*60}")
        print(f"Configuration: {config_name}")
        print(f"Total Duration: {benchmark.results.get('total_duration_human', 'N/A')}")
        print(f"Results saved: {results_path}")
        
        return benchmark.results
        
    finally:
        benchmark.cleanup()


def compare_results(results_dict):
    """Compare results across different configurations"""
    print(f"\n{'='*60}")
    print(f"📊 BENCHMARK COMPARISON")
    print(f"{'='*60}\n")
    
    print(f"{'Configuration':<25} {'Total Time':<15} {'Status'}")
    print("-" * 60)
    
    fastest_time = float('inf')
    fastest_config = None
    
    for config_name, results in results_dict.items():
        duration = results.get("total_duration_seconds", 0)
        duration_human = results.get("total_duration_human", "N/A")
        status = "✅ OK"
        
        # Check for failures
        for stage, stage_result in results.get("stages", {}).items():
            if stage_result.get("status") == "FAILED":
                status = "❌ FAILED"
        
        print(f"{config_name:<25} {duration_human:<15} {status}")
        
        if status == "✅ OK" and duration < fastest_time:
            fastest_time = duration
            fastest_config = config_name
    
    print()
    if fastest_config:
        improvement = ((results_dict[fastest_config].get("total_duration_seconds", 0) 
                       / results_dict[fastest_config].get("total_duration_seconds", 1)) 
                      * 100)
        print(f"🏆 Fastest: {fastest_config}")
    
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ETL Pipeline Benchmark")
    parser.add_argument("--mode", choices=["local", "standalone", "compare", "all"], 
                       default="local",
                       help="Benchmark mode")
    parser.add_argument("--save", action="store_true",
                       help="Save results to file")
    
    args = parser.parse_args()
    
    results = {}
    
    # Mode 1: Local mode (current)
    if args.mode in ["local", "all"]:
        print("\n" + "="*60)
        print("MODE 1: LOCAL (Current - Single JVM)")
        print("="*60)
        try:
            results["local"] = run_benchmark(
                "local[*]",
                "local_mode",
                "/home/fisal_bel/projects/data_projects/serverless-lakehouse-pipeline/config/spark/dev.yaml"
            )
        except Exception as e:
            print(f"❌ Local mode benchmark failed: {str(e)}")
            results["local"] = {"status": "FAILED", "error": str(e)}
    
    # Mode 2: Spark Standalone (simulates EMR)
    if args.mode in ["standalone", "all"]:
        print("\n" + "="*60)
        print("MODE 2: SPARK STANDALONE (Simulated EMR Serverless)")
        print("="*60)
        print("⚠️  Note: Ensure Spark Standalone is running on spark://127.0.0.1:7077")
        print("   Run: ./scripts/start_spark_standalone.sh")
        
        try:
            results["standalone"] = run_benchmark(
                "spark://127.0.0.1:7077",
                "standalone_local",
                "/home/fisal_bel/projects/data_projects/serverless-lakehouse-pipeline/config/spark/standalone-local.yaml"
            )
        except Exception as e:
            print(f"⚠️  Standalone benchmark failed: {str(e)}")
            print("   (Make sure Spark Standalone is running)")
            results["standalone"] = {"status": "FAILED", "error": str(e)}
    
    # Compare if we have multiple results
    if args.mode == "compare" and len(results) > 1:
        compare_results(results)
    elif args.mode == "all" and len(results) > 1:
        compare_results(results)
    
    # Exit with appropriate code
    failed_count = sum(1 for r in results.values() if r.get("status") == "FAILED")
    sys.exit(failed_count)
