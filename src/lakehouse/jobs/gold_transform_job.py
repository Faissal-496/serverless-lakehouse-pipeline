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
    countDistinct
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

        def get_input_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)

        def get_output_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)

        # Read Silver and cache it: the DataFrame is scanned twice below
        # (once for client profile, once for contract analysis). Caching
        # avoids reading from S3 a second time.
        silver_path = get_input_path("silver", "Client_contrat_silver")
        df_silver = self.spark.read.parquet(silver_path)
        df_silver.cache()
        logger.info("Silver data loaded and cached")

        # GOLD 1: CLIENT PROFILE
        logger.info("Creating Client Profile Analysis...")
        df_client_profile = (
            df_silver
            .select("nusoc", "age_client", "client_jeune", "sexsoc", "cspsoc", "sitmat", "sitpav1")
            .dropDuplicates(["nusoc"])
            .withColumn(
                "age_segment",
                when(col("age_client") < 25, "18-24")
                .when(col("age_client") < 35, "25-34")
                .when(col("age_client") < 45, "35-44")
                .when(col("age_client") < 55, "45-54")
                .when(col("age_client") < 65, "55-64")
                .otherwise("65+")
            )
        )

        logger.info("Writing client profile to Gold...")

        gold_client_path = get_output_path("gold", "client_profile_analysis")
        # coalesce(4): client profile is a deduplicated table, likely a few MB.
        # 4 files keeps S3 listing fast without producing too-small files.
        with S3OperationMetricsContext("write_gold_client"):
            df_client_profile.coalesce(4).write.mode("overwrite").parquet(gold_client_path)
        logger.info(f"Client profile saved: {gold_client_path}")

        # GOLD 2: CONTRACT ANALYSIS
        logger.info("Creating Contract Analysis...")
        df_contract_vehicle = (
            df_silver
            .groupBy("type_vehicule")
            .agg(
                count("nucon").alias("total_contracts"),
                countDistinct("nusoc").alias("unique_clients"),
                spark_round(avg("prmaco"), 2).alias("avg_premium"),
                spark_round(spark_sum("prmaco"), 0).alias("total_premium"),
                spark_round(avg("anciennete_contrat"), 1).alias("avg_seniority"),
                spark_round(avg("nb_garanties"), 1).alias("avg_guarantees")
            )
            .orderBy(desc("total_contracts"))
        )

        # Cache the aggregated result: 3-5 rows total.
        df_contract_vehicle.cache()

        gold_contract_path = get_output_path("gold", "contract_analysis")
        # coalesce(1): groupBy produces 3-5 rows (one per vehicle type).
        # A single output file is appropriate and avoids empty part-files.
        with S3OperationMetricsContext("write_gold_contract"):
            df_contract_vehicle.coalesce(1).write.mode("overwrite").parquet(gold_contract_path)
        logger.info(f"Contract analysis saved: {gold_contract_path}")

        # Release cached DataFrames from executor memory
        df_contract_vehicle.unpersist()
        df_silver.unpersist()

        # KPI dashboard disabled: createDataFrame([Row(...)]) causes schema
        # inference failures on distributed executors with native Python types.
        # Re-enable once migrated to explicit StructType.

        # Row counts skipped: count() causes EOFException under Docker memory pressure.
        record_rows_processed("gold", "client_profile_analysis", 0)
        record_rows_processed("gold", "contract_analysis", 0)

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
