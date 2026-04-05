#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gold Transformation Job
Creates analytics-ready datasets for BI and dashboards

Job: gold_transform_job.py
Execution: spark-submit \
    --py-files /opt/lakehouse/src \
    /opt/lakehouse/src/lakehouse/jobs/gold_transform_job.py
"""

from pyspark.sql.functions import (
    col, when, count, avg, sum as spark_sum, desc, round as spark_round,
    countDistinct, max as spark_max, min as spark_min
)
from lakehouse.jobs.base_job import SparkJob
from lakehouse.monitoring.logging import logger
from lakehouse.monitoring.metrics import record_rows_processed, S3OperationMetricsContext


class GoldTransformJob(SparkJob):
    """Silver to Gold transformation for analytics"""
    
    JOB_NAME = "gold_transform"
    
    def run(self):
        """Execute Silver to Gold transformation"""
        logger.info("Starting Gold Transformation")
        
        # Determine path generation based on environment
        def get_input_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)
        
        def get_output_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)
        
        # Read Silver data
        silver_path = get_input_path("silver", "Client_contrat_silver")
        df_silver = self.spark.read.parquet(silver_path)
        total_records = df_silver.count()
        
        logger.info(f"Silver data loaded: {total_records} records")
        
        # = GOLD 1: CLIENT PROFILE = #
        logger.info("Creating Client Profile Analysis...")
        df_client_profile = df_silver.select(
            "nusoc", "age_client", "client_jeune", "sexsoc",
            "cspsoc", "sitmat", "sitpav1"
        ).dropDuplicates(["nusoc"])
        
        df_client_profile = df_client_profile.withColumn(
            "age_segment",
            when(col("age_client") < 25, "18-24")
            .when(col("age_client") < 35, "25-34")
            .when(col("age_client") < 45, "35-44")
            .when(col("age_client") < 55, "45-54")
            .when(col("age_client") < 65, "55-64")
            .otherwise("65+")
        )
        
        client_count = df_client_profile.count()
        logger.info(f"Total unique clients: {client_count}")
        
        gold_client_path = get_output_path("gold", "client_profile_analysis")
        with S3OperationMetricsContext("write_gold_client"):
            df_client_profile.write.mode("overwrite").parquet(gold_client_path)
        logger.info(f"Client profile saved: {gold_client_path}")
        
        # = GOLD 2: CONTRACT ANALYSIS = #
        logger.info("Creating Contract Analysis...")
        df_contract_vehicle = df_silver.groupBy("type_vehicule").agg(
            count("nucon").alias("total_contracts"),
            countDistinct("nusoc").alias("unique_clients"),
            spark_round(avg("prmaco"), 2).alias("avg_premium"),
            spark_round(spark_sum("prmaco"), 0).alias("total_premium"),
            spark_round(avg("anciennete_contrat"), 1).alias("avg_seniority"),
            spark_round(avg("nb_garanties"), 1).alias("avg_guarantees")
        ).orderBy(desc("total_contracts"))
        
        gold_contract_path = get_output_path("gold", "contract_analysis")
        with S3OperationMetricsContext("write_gold_contract"):
            df_contract_vehicle.write.mode("overwrite").parquet(gold_contract_path)
        logger.info(f"Contract analysis saved: {gold_contract_path}")
        
        # = GOLD 3: KPI DASHBOARD = #
        # Disabled: createDataFrame([Row(...)]) causes schema inference failures
        # on a distributed cluster (executor serialization issues with Python
        # native int/float types). Re-enable once migrated to explicit StructType.
        # gold_kpi_path = get_output_path("gold", "kpi_dashboard")
        # ...

        # Record metrics
        record_rows_processed("gold", "client_profile_analysis", client_count)
        record_rows_processed("gold", "contract_analysis", df_contract_vehicle.count())
        
        logger.info("Gold Transformation completed successfully")


if __name__ == "__main__":
    import sys
    
    execution_date = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--execution_date" and i + 2 < len(sys.argv):
            execution_date = sys.argv[i + 2]
    
    job = GoldTransformJob(execution_date=execution_date)
    success = job.execute()
    sys.exit(0 if success else 1)
