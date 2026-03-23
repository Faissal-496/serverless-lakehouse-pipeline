#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bronze to Silver Transformation
Transforms raw contract data from bronze layer to silver layer:
- Consolidates contract1 and contract2 data
- Applies type casting and null handling
- Decodes business logic variables
- Creates analytical key variables
- Joins with client data
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, sum as spark_sum, lit, year, current_date, coalesce
)

from lakehouse.paths import PathResolver
from lakehouse.monitoring.logging import logger
from lakehouse.utils.spark_session import get_spark_session


def run(spark: SparkSession, resolver: PathResolver) -> None:
    """
    Execute Bronze to Silver transformation.
    
    Args:
        spark: SparkSession instance
        resolver: PathResolver instance for S3 paths
    """
    try:
        logger.info("-" * 80)
        logger.info("BRONZE TO SILVER TRANSFORMATION STARTED")
        logger.info("-" * 80)
        
        # =========================
        # 1. READ BRONZE DATA
        # =========================
        logger.info("Reading bronze contract data...")
        
        s3_bronze_path_contrat2 = resolver.s3_layer_path(
            layer="bronze", dataset="Contrat2"
        )
        s3_bronze_path_contrat1 = resolver.s3_layer_path(
            layer="bronze", dataset="contrat1"
        )
        
        df_contrat2 = spark.read.parquet(s3_bronze_path_contrat2)
        df_contrat1 = spark.read.parquet(s3_bronze_path_contrat1)
        
        logger.info(f"Contrat2 loaded: {df_contrat2.count()} rows")
        logger.info(f"Contrat1 loaded: {df_contrat1.count()} rows")
        
        # =========================
        # 2. UNION CONTRACTS
        # =========================
        logger.info("Merging contract tables...")
        df_contracts = df_contrat2.unionByName(df_contrat1)
        logger.info(f"Merged contracts: {df_contracts.count()} rows")
        
        # =========================
        # 3. TYPE CASTING
        # =========================
        logger.info("Casting column types...")
        df_silver = (
            df_contracts
            .withColumn("nusoc", col("nusoc").cast("int"))
            .withColumn("nucon", col("nucon").cast("int"))
            .withColumn("prmaco", col("prmaco").cast("double"))
            .withColumn("pfco", col("pfco").cast("int"))
            .withColumn("asaico", col("asaico").cast("int"))
        )
        
        # =========================
        # 4. NULL HANDLING
        # =========================
        logger.info("Handling null values...")
        df_silver = (
            df_silver
            .withColumn("pfco", when(col("pfco").isNull(), 0).otherwise(col("pfco")))
            .withColumn("etatco", when(col("etatco").isNull(), "UNKNOWN").otherwise(col("etatco")))
            .withColumn("prmaco", when(col("prmaco").isNull(), 0.0).otherwise(col("prmaco")))
        )
        
        # =========================
        # 5. REMOVE DUPLICATES
        # =========================
        logger.info("Removing contract duplicates...")
        before_dedup = df_silver.count()
        df_silver = df_silver.dropDuplicates(["nusoc", "nucon"])
        after_dedup = df_silver.count()
        logger.info(f"Removed {before_dedup - after_dedup} duplicates")
        
        # =========================
        # 6. DECODE BUSINESS VARIABLES
        # =========================
        logger.info("Decoding business variables...")
        
        # Vehicle type
        df_silver = df_silver.withColumn(
            "type_vehicule",
            when(col("cateco") == "A", "Auto")
            .when(col("cateco") == "M", "Moto")
            .when(col("cateco") == "C", "Cyclo")
            .otherwise("Inconnu")
        )
        
        # Contract state
        df_silver = df_silver.withColumn(
            "etat_contrat_libelle",
            when(col("etatco") == "0", "Annulé")
            .when(col("etatco") == "1", "En cours")
            .when(col("etatco") == "2", "Suspendu")
            .when(col("etatco") == "3", "Résilié sociétaire")
            .when(col("etatco") == "4", "Résilié impayé")
            .when(col("etatco") == "7", "Résilié article 25 (hausse tarifaire)")
            .when(col("etatco") == "9", "Résilié Mutuelle")
            .otherwise("Autre")
        )
        
        # Vehicle usage
        df_silver = df_silver.withColumn(
            "usage_vehicule",
            when(col("usagco1") == 0, "Domicile-Travail")
            .when(col("usagco1") == 1, "Promenade")
            .when(col("usagco1") == 3, "Professionnel")
            .otherwise("Autre")
        )
        
        # =========================
        # 7. GUARANTEES AGGREGATION
        # =========================
        logger.info("Aggregating guarantees...")
        garanties = [
            "g01co", "g02co", "g03co", "g04co", "g05co", "g06co", "g09co",
            "g10co", "g13co", "g15co", "g16co", "g17co", "g18co", "g19co",
            "g21co", "g22co", "g23co", "g25co", "g26co", "g28co"
        ]
        
        # Safely sum only existing columns
        existing_garanties = [g for g in garanties if g in df_silver.columns]
        if existing_garanties:
            # Sum all guarantee columns (cast to int, coalesce to 0)
            sum_expr = sum([coalesce(col(g).cast("int"), lit(0)) for g in existing_garanties])
            df_silver = df_silver.withColumn("nb_garanties", sum_expr)
        else:
            logger.warning("No guarantee columns found")
            df_silver = df_silver.withColumn("nb_garanties", lit(0))
        
        # =========================
        # 8. CREATE ANALYTICAL VARIABLES
        # =========================
        logger.info("Creating analytical variables...")
        
        df_silver = df_silver.withColumnRenamed("asaico", "annee_souscription")
        df_silver = df_silver.withColumn(
            "anciennete_contrat",
            year(current_date()) - col("annee_souscription")
        )
        
        # =========================
        # 9. READ CLIENT DATA
        # =========================
        logger.info("Reading client data...")
        s3_bronze_path_client = resolver.s3_layer_path(
            layer="bronze", dataset="Client"
        )
        
        df_client = spark.read.parquet(s3_bronze_path_client)
        logger.info(f"Client data loaded: {df_client.count()} rows")
        
        # =========================
        # 10. CLIENT TRANSFORMATIONS
        # =========================
        logger.info("Processing client data...")
        
        # Calculate age dynamically based on current year
        df_client_silver = df_client.withColumn(
            "age_client",
            year(current_date()) - col("anaiso")
        )
        
        # Quality checks
        before_qc = df_client_silver.count()
        df_client_silver = df_client_silver.filter(
            (col("age_client") >= 14) & (col("age_client") <= 100)
        )
        after_qc = df_client_silver.count()
        logger.info(f"Quality check: removed {before_qc - after_qc} invalid ages")
        
        # Young client flag
        df_client_silver = df_client_silver.withColumn(
            "client_jeune",
            when(col("age_client") < 30, 1).otherwise(0)
        )
        
        # =========================
        # 11. JOIN CLIENT & CONTRACT
        # =========================
        logger.info("Joining client and contract data...")
        
        df_silver_global = df_silver.join(
            df_client_silver.select(
                "nusoc", "age_client", "client_jeune", "sexsoc",
                "cspsoc", "sitmat", "sitpav1"
            ),
            on="nusoc",
            how="inner"
        )
        logger.info(f"Joint result: {df_silver_global.count()} rows")
        
        # =========================
        # 12. CUSTOMER SEGMENT FLAGS
        # =========================
        logger.info("Creating customer segment flags...")
        
        df_silver_global = df_silver_global.withColumn(
            "jeune_moto",
            when((col("client_jeune") == 1) & (col("cateco") == "M"), 1).otherwise(0)
        )
        
        df_silver_global = df_silver_global.withColumn(
            "contrat_actif",
            when(col("etatco") == 1, 1).otherwise(0)
        )
        
        # =========================
        # 13. WRITE SILVER DATA
        # =========================
        logger.info("Writing silver data to S3...")
        s3_silver_path = resolver.s3_layer_path(
            layer="silver", dataset="Client_contrat_silver"
        )
        
        df_silver_global.write \
            .mode("overwrite") \
            .parquet(s3_silver_path)
        
        logger.info(f"Silver data written to {s3_silver_path}")
        logger.info("-" * 80)
        logger.info("BRONZE TO SILVER TRANSFORMATION COMPLETED SUCCESSFULLY")
        logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"Error in bronze_to_silver transformation: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    """
    Standalone execution (for testing).
    Set environment variables: APP_ENV, S3_BUCKET, DATA_BASE_PATH
    """
    spark = get_spark_session("BronzeToSilver")
    resolver = PathResolver()
    
    try:
        run(spark, resolver)
    finally:
        spark.stop()
