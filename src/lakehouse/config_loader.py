from pathlib import Path
import yaml
import os

CONFIG_DIR = Path(
    os.getenv("CONFIG_DIR", "/opt/lakehouse/config")
)

def load_yaml(relative_path: str) -> dict:
    """
    Load a YAML file from the config directory.

    :param relative_path: Path relative to CONFIG_DIR
    :return: Parsed YAML as dict
    """
    path = CONFIG_DIR / relative_path

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        return yaml.safe_load(f)
