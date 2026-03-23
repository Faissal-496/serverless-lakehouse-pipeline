from pyspark.sql import SparkSession
from lakehouse.monitoring.logging import logger
from lakehouse.config_loader import load_yaml
import os

def get_spark_session(app_name="LakehouseApp", enable_hive=True):
    """
    Create or retrieve a Spark session with configurations loaded from YAML files.
    Loads from: default.yaml, then environment-specific (dev.yaml or prod.yaml).
    """
    logger.info(f"Initializing Spark Session for {app_name}...")
    
    try:
        # Load default Spark configuration
        default_config = load_yaml("spark/default.yaml")
        logger.info("Loaded default Spark configuration from spark/default.yaml")
        
        # Get environment and load environment-specific configuration
        app_env = os.getenv("APP_ENV", "dev")
        env_config = load_yaml(f"spark/{app_env}.yaml")
        logger.info(f"Loaded {app_env} Spark configuration from spark/{app_env}.yaml")
        
        # Merge configurations (environment-specific overrides defaults)
        spark_config = default_config.get("spark", {})
        env_spark_config = env_config.get("spark", {})
        
        app_name_cfg = spark_config.get("app_name", app_name)
        master = spark_config.get("master", "local[*]")
        
        # Merge config dictionaries
        merged_config = spark_config.get("config", {}).copy()
        merged_config.update(env_spark_config.get("config", {}))
        
    except Exception as e:
        logger.warning(f"Could not load YAML configs: {str(e)}. Using defaults.")
        app_name_cfg = app_name
        master = "local[*]"
        merged_config = {}
    
    # Initialize Spark builder
    builder = SparkSession.builder.appName(app_name_cfg).master(master)
    
    # Enable Hive if requested
    if enable_hive:
        builder = builder.enableHiveSupport()
    
    # Apply all configurations from YAML
    for key, value in merged_config.items():
        builder = builder.config(key, str(value))
    
    # Apply environment variable overrides (for runtime flexibility)
    if os.getenv("SPARK_SHUFFLE_PARTS"):
        builder = builder.config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTS"))
    if os.getenv("SPARK_DRIVER_MEMORY"):
        builder = builder.config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY"))
    if os.getenv("SPARK_EXECUTOR_MEMORY"):
        builder = builder.config("spark.executor.memory", os.getenv("SPARK_EXECUTOR_MEMORY"))
    
    # Enable Arrow for better performance
    builder = builder.config("spark.sql.execution.arrow.pyspark.enabled", "true")
    
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))
    
    logger.info("Spark Session initialized successfully")
    return spark
 