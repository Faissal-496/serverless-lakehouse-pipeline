from datetime import datetime
from lakehouse.monitoring.logging import logger


def log_lineage(source: str, target: str, rows: int):
    timestamp = datetime.now().isoformat()
    logger.info(f"LINEAGE | Timestamp: {timestamp} | Source: {source} -> Target: {target} | Rows: {rows}")
