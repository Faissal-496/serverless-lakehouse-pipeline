#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Silver Transformation Job
Transforms Bronze data: consolidation, type casting, business logic decoding

Job: silver_transform_job.py
Execution: spark-submit \
    --py-files /opt/lakehouse/src \
    /opt/lakehouse/src/lakehouse/jobs/silver_transform_job.py
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, coalesce, year, month, dayofmonth
)
from lakehouse.jobs.base_job import SparkJob
from lakehouse.monitoring.logging import logger, log_partition_processed
from lakehouse.monitoring.metrics import record_rows_processed, S3OperationMetricsContext


class SilverTransformJob(SparkJob):
    """Bronze to Silver transformation"""
    
    JOB_NAME = "silver_transform"
    
    def run(self):
        """Execute Bronze to Silver transformation"""
        logger.info("Starting Silver Transformation")
        
        # Determine path generation based on environment
        def get_input_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)
        
        def get_output_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)
        
        # Read Bronze layers
        logger.info("Reading Bronze data...")
        df_contrat2 = self.spark.read.parquet(
            get_input_path("bronze", "Contrat2")
        )
        df_contrat1 = self.spark.read.parquet(
            get_input_path("bronze", "Contrat1")
        )
        df_client = self.spark.read.parquet(
            get_input_path("bronze", "Client")
        )
        
        logger.info(f"Contrat2: {df_contrat2.count()} rows")
        logger.info(f"Contrat1: {df_contrat1.count()} rows")
        logger.info(f"Client: {df_client.count()} rows")
        
        # = CONSOLIDATION = #
        df_contracts = df_contrat2.unionByName(df_contrat1)
        logger.info(f"Merged contracts: {df_contracts.count()} rows")
        
        # = TYPE CASTING = #
        df_silver = (
            df_contracts
            .withColumn("nusoc", col("nusoc").cast("int"))
            .withColumn("nucon", col("nucon").cast("int"))
            .withColumn("prmaco", col("prmaco").cast("double"))
            .withColumn("pfco", col("pfco").cast("int"))
            .withColumn("asaico", col("asaico").cast("int"))
        )
        
        # = NULL HANDLING = #
        df_silver = (
            df_silver
            .withColumn("pfco", when(col("pfco").isNull(), 0).otherwise(col("pfco")))
            .withColumn("etatco", when(col("etatco").isNull(), "UNKNOWN").otherwise(col("etatco")))
            .withColumn("prmaco", when(col("prmaco").isNull(), 0.0).otherwise(col("prmaco")))
        )
        
        # = DEDUPLICATION = #
        before_dedup = df_silver.count()
        df_silver = df_silver.dropDuplicates(["nusoc", "nucon"])
        after_dedup = df_silver.count()
        logger.info(f"Removed {before_dedup - after_dedup} duplicates")
        
        # = BUSINESS LOGIC: VEHICLE TYPES = #
        df_silver = df_silver.withColumn(
            "type_vehicule",
            when(col("cateco") == "A", "Auto")
            .when(col("cateco") == "M", "Moto")
            .when(col("cateco") == "C", "Cyclo")
            .otherwise("Inconnu")
        )
        
        # = BUSINESS LOGIC: CONTRACT STATUS = #
        df_silver = df_silver.withColumn(
            "etat_contrat_libelle",
            when(col("etatco") == "0", "Annulé")
            .when(col("etatco") == "1", "En cours")
            .when(col("etatco") == "2", "Suspendu")
            .when(col("etatco") == "3", "Résilié sociétaire")
            .when(col("etatco") == "4", "Résilié impayé")
            .when(col("etatco") == "7", "Résilié article 25")
            .when(col("etatco") == "9", "Résilié Mutuelle")
            .otherwise("Autre")
        )
        
        # = CONTRACT ACTIVE FLAG = #
        df_silver = df_silver.withColumn(
            "contrat_actif",
            when(col("etatco") == "1", 1).otherwise(0)
        )
        
        # = VEHICLE USAGE = #
        df_silver = df_silver.withColumn(
            "usage_vehicule",
            when(col("usagco1") == 0, "Domicile-Travail")
            .when(col("usagco1") == 1, "Promenade")
            .when(col("usagco1") == 3, "Professionnel")
            .otherwise("Autre")
        )
        
        # = GUARANTEES AGGREGATION = #
        garanties = [
            "g01co", "g02co", "g03co", "g04co", "g05co", "g06co", "g09co",
            "g10co", "g13co", "g15co", "g16co", "g17co", "g18co", "g19co",
            "g21co", "g22co", "g23co", "g25co", "g26co", "g28co"
        ]
        existing_garanties = [g for g in garanties if g in df_silver.columns]
        if existing_garanties:
            sum_expr = sum([coalesce(col(g).cast("int"), lit(0)) for g in existing_garanties])
            df_silver = df_silver.withColumn("nb_garanties", sum_expr)
        else:
            df_silver = df_silver.withColumn("nb_garanties", lit(0))
        
        # = JOIN WITH CLIENT DATA = #
        df_silver = df_silver.join(
            df_client.select(
                "nusoc", "sexsoc", "aadhso", "cspsoc", "sitmat", "sitpav1", "nbenf"
            ),
            on="nusoc",
            how="left"
        )
        
        # = DERIVED COLUMNS = #
        df_silver = df_silver.withColumn(
            "age_client",
            when(col("aadhso").isNotNull(), 
                 year(col("current_date")) - col("aadhso"))
            .otherwise(None)
        ).withColumn(
            "client_jeune",
            when(col("age_client") < 30, 1).otherwise(0)
        ).withColumn(
            "anciennete_contrat",
            when(col("asaico").isNotNull(),
                 year(col("current_date")) - col("asaico"))
            .otherwise(None)
        )
        
        # = WRITE TO SILVER = #
        total_rows = df_silver.count()
        output_path = get_output_path("silver", "Client_contrat_silver")
        
        logger.info(f"Writing {total_rows} rows to Silver...")
        with S3OperationMetricsContext("write_silver"):
            df_silver.write.mode("overwrite").parquet(output_path)
        
        logger.info(f"Silver written: {output_path}")
        record_rows_processed("silver", "Client_contrat_silver", total_rows)
        
        logger.info("Silver Transformation completed successfully")


if __name__ == "__main__":
    import sys
    
    execution_date = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--execution_date" and i + 2 < len(sys.argv):
            execution_date = sys.argv[i + 2]
    
    job = SilverTransformJob(execution_date=execution_date)
    success = job.execute()
    sys.exit(0 if success else 1)
