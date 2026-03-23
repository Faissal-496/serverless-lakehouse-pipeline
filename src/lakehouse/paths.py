import os
from pathlib import Path
from lakehouse.config_loader import load_yaml

class PathResolver:
    """
    Resolve logical paths to real local or S3 paths.
    Loads configuration from YAML files:
    - paths.yaml: Layer paths (bronze, silver, gold)
    - env/dev.yaml or env/prod.yaml: Environment-specific config
    No infrastructure details are stored in Git.
    """

    def __init__(self):
        # Mandatory environment
        self.app_env = os.environ.get("APP_ENV")
        if not self.app_env:
            raise RuntimeError("APP_ENV environment variable is required")

        # Load logical paths configuration
        self.paths_cfg = load_yaml("paths.yaml")
        
        # Load environment-specific configuration
        try:
            self.env_cfg = load_yaml(f"env/{self.app_env}.yaml")
        except FileNotFoundError:
            self.env_cfg = {}

        # local data root (DEV only)
        self.data_root = Path(
            os.getenv("DATA_BASE_PATH", "/opt/lakehouse/data")
        )

        # S3 bucket can come from environment or YAML config
        self.s3_bucket = os.environ.get("S3_BUCKET")
        if not self.s3_bucket and self.env_cfg:
            self.s3_bucket = self.env_cfg.get("s3", {}).get("bucket")
        
        if not self.s3_bucket:
            raise RuntimeError("S3_BUCKET environment variable is required or s3.bucket must be set in env/{app_env}.yaml")
        
        # Glue database configuration
        self.glue_database = os.environ.get("GLUE_DATABASE")
        if not self.glue_database and self.env_cfg:
            self.glue_database = self.env_cfg.get("glue", {}).get("database")
        
        # Logging level from config
        self.log_level = os.environ.get("LOG_LEVEL")
        if not self.log_level and self.env_cfg:
            self.log_level = self.env_cfg.get("logging", {}).get("level", "INFO")

    def local_input(self, filename: str) -> str:
        """
        Resolve a local input file path.
        """
        return str(self.data_root / filename)

    def s3_layer_path(self, layer: str, dataset: str) -> str:
        """
        Resolve an S3 path for a given layer and dataset.
        """
        try:
            prefix = self.paths_cfg["paths"][layer]
        except KeyError:
            raise ValueError(f"Unknown data layer: {layer}")

        return f"s3a://{self.s3_bucket}/{prefix}/{dataset}"
