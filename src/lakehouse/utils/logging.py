import logging
import sys
from pathlib import Path
from lakehouse.paths import PathResolver

resolver = PathResolver()
log_dir = Path("/tmp") if resolver.app_env == "dev" else Path(f"s3a://{resolver.s3_bucket}/{resolver.paths_cfg['paths']['logs']}")

def get_logger(name="lakehouse"):
    """
    Configured logger with console + file handlers.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # file (local dev only)
    if resolver.app_env == "dev":
        log_file = log_dir / f"{name}.log"
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

logger = get_logger()
