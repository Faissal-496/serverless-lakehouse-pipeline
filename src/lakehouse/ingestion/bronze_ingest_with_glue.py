#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# src/lakehouse/ingestion/bronze_ingest_with_glue.py

import sys
import traceback
import os
from pyspark.sql import SparkSession
from lakehouse.paths import PathResolver
from lakehouse.ingestion.schema_registry import CONTRAT2_SCHEMA, CLIENT_SCHEMA


def create_spark_session(app_name="BronzeIngestion") -> SparkSession:
    """Créer et retourner une SparkSession avec support Glue catalog"""
    try:
        spark = SparkSession.builder \
            .appName(app_name) \
            .config("spark.sql.catalogImplementation", "hive") \
            .config("hive.metastore.client.factory.class",
                    "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory") \
            .enableHiveSupport() \
            .getOrCreate()
        print(f"[INFO] SparkSession créée avec Glue support : {spark.version}")
        return spark
    except Exception as e:
        print(f"[ERROR] Erreur lors de la création de SparkSession : {e}")
        sys.exit(1)


def read_csv(spark: SparkSession, path: str, schema=None):
    """Lecture sécurisée d'un CSV avec logging"""
    try:
        print(f"[INFO] Lecture du CSV : {path}")
        df = spark.read.option("header", "true") \
                       .option("inferSchema", schema is None) \
                       .option("nullValue", "") \
                       .schema(schema) \
                       .csv(path)
        print(f"[INFO] Lecture terminée : {df.count()} lignes")
        df.printSchema()
        return df
    except Exception as e:
        print(f"[ERROR] Erreur lecture CSV : {e}")
        traceback.print_exc()
        sys.exit(1)


def write_parquet(df, output_path: str):
    """Écriture Parquet avec logging"""
    try:
        print(f"[INFO] Écriture Parquet : {output_path}")
        df.write.mode("overwrite").parquet(output_path)
        print("[INFO] Écriture réussie")
    except Exception as e:
        print(f"[ERROR] Erreur écriture Parquet : {e}")
        traceback.print_exc()
        sys.exit(1)


def create_glue_table(spark: SparkSession, table_name: str, s3_path: str, schema):
    """Créer ou mettre à jour une table Glue à partir d'un DataFrame"""
    db_name = os.getenv("GLUE_DATABASE") or os.getenv("GLUE_DB_NAME", "lakehouse_assurance_moto_catalog")
    try:
        print(f"[INFO] Création / mise à jour table Glue : {db_name}.{table_name}")
        df = spark.read.schema(schema).parquet(s3_path)
        df.write.mode("overwrite") \
                .format("parquet") \
                .option("path", s3_path) \
                .saveAsTable(f"{db_name}.{table_name}")
        print(f"[INFO] Table Glue {db_name}.{table_name} créée/mise à jour")
    except Exception as e:
        print(f"[ERROR] Erreur création table Glue {db_name}.{table_name} : {e}")
        traceback.print_exc()
        sys.exit(1)


def main():
    resolver = PathResolver()
    spark = create_spark_session()

    # Récupération dynamique du bucket S3 depuis .env (obligatoire)
    s3_bucket = os.getenv("S3_BUCKET")
    if not s3_bucket:
        raise EnvironmentError(
            "S3_BUCKET environment variable must be set. "
            "Set it using: export S3_BUCKET=your-bucket-name"
        )

    # -----------------------
    # Contrat2
    # -----------------------
    input_contrat2 = resolver.local_input("Contrat2.csv")
    output_contrat2 = resolver.s3_layer_path("bronze", "Contrat2")
    df_contrat2 = read_csv(spark, input_contrat2, schema=CONTRAT2_SCHEMA)
    write_parquet(df_contrat2, output_contrat2)
    create_glue_table(spark, "bronze_contrat2", output_contrat2, CONTRAT2_SCHEMA)

    # -----------------------
    # Client
    # -----------------------
    input_client = resolver.local_input("client.csv")
    output_client = resolver.s3_layer_path("bronze", "Client")
    df_client = read_csv(spark, input_client, schema=CLIENT_SCHEMA)
    write_parquet(df_client, output_client)
    create_glue_table(spark, "bronze_client", output_client, CLIENT_SCHEMA)

    # -----------------------
    # Fin pipeline
    # -----------------------
    spark.stop()
    print("[INFO] Pipeline Bronze terminé avec succès ")


if __name__ == "__main__":
    main()
