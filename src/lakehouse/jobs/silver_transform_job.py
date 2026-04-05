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

from pyspark.sql.functions import (
    col, when, lit, coalesce, year, current_date, broadcast
)
from lakehouse.jobs.base_job import SparkJob
from lakehouse.monitoring.logging import logger
from lakehouse.monitoring.metrics import record_rows_processed, S3OperationMetricsContext


class SilverTransformJob(SparkJob):
    """Bronze to Silver transformation"""

    JOB_NAME = "silver_transform"

    def run(self):
        """Execute Bronze to Silver transformation"""
        logger.info("Starting Silver Transformation")

        def get_input_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)

        def get_output_path(layer, dataset):
            if self.config.app_env == "dev":
                return self.config.get_local_output_path(layer, dataset)
            return self.config.get_s3_layer_path(layer, dataset)

        # Read Bronze layers (no count calls here - each count would be a full scan)
        logger.info("Reading Bronze data...")
        df_contrat2 = self.spark.read.parquet(get_input_path("bronze", "Contrat2"))
        df_contrat1 = self.spark.read.parquet(get_input_path("bronze", "Contrat1"))
        df_client = self.spark.read.parquet(get_input_path("bronze", "Client"))

        # Consolidate + cast + null handling + deduplication in one lazy chain.
        # dropDuplicates is placed here so it runs in the same Spark job as the
        # union, avoiding a second full scan just for before/after counts.
        df_silver = (
            df_contrat2.unionByName(df_contrat1)
            .withColumn("nusoc", col("nusoc").cast("int"))
            .withColumn("nucon", col("nucon").cast("int"))
            .withColumn("prmaco", col("prmaco").cast("double"))
            .withColumn("pfco", col("pfco").cast("int"))
            .withColumn("asaico", col("asaico").cast("int"))
            .withColumn("pfco", when(col("pfco").isNull(), 0).otherwise(col("pfco")))
            .withColumn("etatco", when(col("etatco").isNull(), "UNKNOWN").otherwise(col("etatco")))
            .withColumn("prmaco", when(col("prmaco").isNull(), 0.0).otherwise(col("prmaco")))
            .dropDuplicates(["nusoc", "nucon"])
        )

        # Business logic: vehicle type, contract status, active flag, usage
        df_silver = (
            df_silver
            .withColumn(
                "type_vehicule",
                when(col("cateco") == "A", "Auto")
                .when(col("cateco") == "M", "Moto")
                .when(col("cateco") == "C", "Cyclo")
                .otherwise("Inconnu")
            )
            .withColumn(
                "etat_contrat_libelle",
                when(col("etatco") == "0", "Annule")
                .when(col("etatco") == "1", "En cours")
                .when(col("etatco") == "2", "Suspendu")
                .when(col("etatco") == "3", "Resilie societaire")
                .when(col("etatco") == "4", "Resilie impaye")
                .when(col("etatco") == "7", "Resilie article 25")
                .when(col("etatco") == "9", "Resilie Mutuelle")
                .otherwise("Autre")
            )
            .withColumn("contrat_actif", when(col("etatco") == "1", 1).otherwise(0))
            .withColumn(
                "usage_vehicule",
                when(col("usagco1") == 0, "Domicile-Travail")
                .when(col("usagco1") == 1, "Promenade")
                .when(col("usagco1") == 3, "Professionnel")
                .otherwise("Autre")
            )
        )

        # Guarantees count: sum only columns that exist in the schema
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

        # Broadcast join: df_client is a small dimension table (one row per client).
        # broadcast() tells Spark to replicate it to every executor instead of
        # doing a sort-merge join, which avoids a shuffle on the contracts side.
        df_silver = df_silver.join(
            broadcast(
                df_client.select("nusoc", "sexsoc", "aadhso", "cspsoc", "sitmat", "sitpav1", "nbenf")
            ),
            on="nusoc",
            how="left"
        )

        # Derived columns: use current_date() function (not col("current_date")).
        # year(current_date()) returns the current calendar year as an integer.
        current_year = year(current_date())
        df_silver = (
            df_silver
            .withColumn(
                "age_client",
                when(col("aadhso").isNotNull(), current_year - col("aadhso")).otherwise(None)
            )
            .withColumn("client_jeune", when(col("age_client") < 30, 1).otherwise(0))
            .withColumn(
                "anciennete_contrat",
                when(col("asaico").isNotNull(), current_year - col("asaico")).otherwise(None)
            )
        )

        # Single count before write - this is the only Spark action in this job
        # before the write itself. Used for final row-count metrics.
        total_rows = df_silver.count()
        output_path = get_output_path("silver", "Client_contrat_silver")

        logger.info(f"Writing {total_rows} rows to Silver...")
        # coalesce(4): produces 4 output files (~500MB each for 2GB data).
        # Avoids the small-files problem on S3 without forcing a full shuffle
        # (coalesce is a narrow transformation, unlike repartition).
        with S3OperationMetricsContext("write_silver"):
            df_silver.coalesce(4).write.mode("overwrite").parquet(output_path)

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
