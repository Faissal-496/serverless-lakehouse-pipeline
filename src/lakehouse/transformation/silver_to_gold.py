#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Silver to Gold Transformation
Creates business-ready datasets for analytics and dashboards:
- Client Profile Analysis: demographic segmentation
- KPI Dashboard: key performance indicators
- Contract Analysis: contract metrics and trends
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, count, avg, sum as spark_sum, max as spark_max,
    min as spark_min, round as spark_round, lit, desc, coalesce, countDistinct
)
from pyspark.sql.window import Window

from lakehouse.paths import PathResolver
from lakehouse.monitoring.logging import logger
from lakehouse.utils.spark_session import get_spark_session


def run(spark: SparkSession, resolver: PathResolver) -> None:
    """
    Execute Silver to Gold transformation.
    Creates analytics-ready golden tables.
    
    Args:
        spark: SparkSession instance
        resolver: PathResolver instance for S3 paths
    """
    try:
        logger.info("-" * 80)
        logger.info("SILVER TO GOLD TRANSFORMATION - ANALYTICS DASHBOARD")
        logger.info("-" * 80)
        
        # =========================
        # 1. READ SILVER DATA
        # =========================
        logger.info("Loading silver client-contract unified data...")
        
        s3_silver_path = resolver.s3_layer_path(
            layer="silver", dataset="Client_contrat_silver"
        )
        
        df_silver = spark.read.parquet(s3_silver_path)
        total_records = df_silver.count()
        
        logger.info(f"Silver data loaded: {total_records} records")
        logger.info(f"   Columns: {len(df_silver.columns)}")
        
        # =========================
        # 2. GOLD TABLE 1: CLIENT PROFILE ANALYSIS
        # =========================
        logger.info("Creating GOLD 1: CLIENT PROFILE ANALYSIS")
        
        # Unique clients with demographics
        df_client_profile = df_silver.select(
            "nusoc", "age_client", "client_jeune", "sexsoc",
            "cspsoc", "sitmat", "sitpav1"
        ).dropDuplicates(["nusoc"])
        
        total_clients = df_client_profile.count()
        logger.info(f"Total unique clients: {total_clients}")
        
        # Age segments
        df_client_profile = df_client_profile.withColumn(
            "age_segment",
            when(col("age_client") < 25, "18-24")
            .when(col("age_client") < 35, "25-34")
            .when(col("age_client") < 45, "35-44")
            .when(col("age_client") < 55, "45-54")
            .when(col("age_client") < 65, "55-64")
            .otherwise("65+")
        )
        
        # Gender distribution
        df_gender_dist = df_client_profile.groupBy("sexsoc").agg(
            count("nusoc").alias("nb_clients"),
            spark_round(avg("age_client"), 1).alias("avg_age")
        )
        logger.info("Gender distribution:")
        df_gender_dist.show(truncate=False)
        
        # Young customers (<30)
        young_count = df_client_profile.filter(col("client_jeune") == 1).count()
        young_pct = (young_count / total_clients) * 100 if total_clients > 0 else 0
        logger.info(f"Young customers (<30): {young_count} ({young_pct:.2f}%)")
        
        # Write Gold 1
        s3_gold_client_profile = resolver.s3_layer_path(
            layer="gold", dataset="client_profile_analysis"
        )
        df_client_profile.write.mode("overwrite").parquet(s3_gold_client_profile)
        logger.info(f"Client profile saved to {s3_gold_client_profile}")
        
        # =========================
        # 3. GOLD TABLE 2: CONTRACT ANALYSIS
        # =========================
        logger.info("Creating GOLD 2: CONTRACT ANALYSIS")
        
        # Contract stats by vehicle type
        df_contract_vehicle = df_silver.groupBy("type_vehicule").agg(
            count("nucon").alias("total_contracts"),
            countDistinct("nusoc").alias("unique_clients"),
            spark_round(avg("prmaco"), 2).alias("avg_premium"),
            spark_round(spark_sum("prmaco"), 0).alias("total_premium"),
            spark_round(avg("anciennete_contrat"), 1).alias("avg_seniority"),
            spark_round(avg("nb_garanties"), 1).alias("avg_guarantees")
        ).orderBy(desc("total_contracts"))
        
        logger.info("Contracts by vehicle type:")
        df_contract_vehicle.show(truncate=False)
        
        # Contract status distribution
        df_status_dist = df_silver.groupBy("etat_contrat_libelle").agg(
            count("nucon").alias("nb_contracts"),
            spark_round((count("nucon") / total_records * 100), 2).alias("percentage")
        ).orderBy(desc("nb_contracts"))
        
        logger.info("Contract status distribution:")
        df_status_dist.show(truncate=False)
        
        # Activity status metrics
        df_activity = df_silver.select(
            when(col("contrat_actif") == 1, "Active").otherwise("Inactive").alias("status"),
            col("nucon"),
            col("nusoc")  # Added missing column
        ).groupBy("status").agg(
            count("nucon").alias("count"),
            countDistinct("nusoc").alias("unique_clients")
        )
        logger.info("Activity metrics:")
        df_activity.show(truncate=False)
        
        # Write Gold 2
        s3_gold_contract = resolver.s3_layer_path(
            layer="gold", dataset="contract_analysis"
        )
        df_contract_vehicle.write.mode("overwrite").parquet(s3_gold_contract)
        logger.info(f"Contract analysis saved to {s3_gold_contract}")
        
        # =========================
        # 4. GOLD TABLE 3: KPI DASHBOARD
        # =========================
        logger.info("Creating GOLD 3: KPI DASHBOARD")
        
        # Calculate key metrics
        total_contracts = df_silver.count()
        active_contracts = df_silver.filter(col("contrat_actif") == 1).count()
        inactive_contracts = total_contracts - active_contracts
        
        # Premiums
        total_premium = df_silver.agg(spark_sum("prmaco")).collect()[0][0] or 0.0
        avg_premium = df_silver.agg(avg("prmaco")).collect()[0][0] or 0.0
        
        # Young motorcycle drivers (high-risk segment)
        young_moto = df_silver.filter(col("jeune_moto") == 1).count()
        
        # Build KPI dataframe - convert all values to float for consistency
        kpi_data = [
            ("Total Contracts", float(total_contracts)),
            ("Active Contracts", float(active_contracts)),
            ("Inactive Contracts", float(inactive_contracts)),
            ("Retention Rate (%)", float(round(active_contracts / total_contracts * 100, 2)) if total_contracts > 0 else 0.0),
            ("Total Premium (€)", float(round(total_premium, 0))),
            ("Avg Premium per Contract (€)", float(round(avg_premium, 2))),
            ("Unique Clients", float(df_silver.select("nusoc").distinct().count())),
            ("Young Moto Drivers (High Risk)", float(young_moto)),
        ]
        
        df_kpi = spark.createDataFrame(kpi_data, ["metric", "value"])
        
        logger.info("KEY PERFORMANCE INDICATORS:")
        df_kpi.show(truncate=False)
        
        # Write Gold 3
        s3_gold_kpi = resolver.s3_layer_path(
            layer="gold", dataset="kpi_dashboard"
        )
        df_kpi.write.mode("overwrite").parquet(s3_gold_kpi)
        logger.info(f"KPI dashboard saved to {s3_gold_kpi}")
        
        # =========================
        # 5. SUMMARY REPORT
        # =========================
        logger.info("-" * 80)
        logger.info("TRANSFORMATION SUMMARY")
        logger.info("-" * 80)
        
        premium_by_type = df_silver.groupBy("type_vehicule").agg(
            spark_round(spark_sum("prmaco"), 0).alias("revenue")
        ).orderBy(desc("revenue"))
        
        logger.info("Premium by vehicle type:")
        premium_by_type.show(truncate=False)
        
        # Top 5 contracts by premium
        logger.info("Top 5 highest premium contracts:")
        df_silver.select("nusoc", "nucon", "type_vehicule", "prmaco", "anciennete_contrat") \
            .orderBy(desc("prmaco")) \
            .limit(5) \
            .show(truncate=False)
        
        logger.info("-" * 80)
        logger.info("SILVER TO GOLD TRANSFORMATION COMPLETED SUCCESSFULLY")
        logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"Error in silver_to_gold transformation: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    """
    Standalone execution (for testing).
    Set environment variables: APP_ENV, S3_BUCKET, DATA_BASE_PATH
    """
    spark = get_spark_session("SilverToGold")
    resolver = PathResolver()
    
    try:
        run(spark, resolver)
    finally:
        spark.stop()
