import json
import sys

def load_config(config_path: str) -> dict:
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"Config file not found: {config_path}")
    except json.JSONDecodeError:
        sys.exit(f"Failed to parse {config_path}. It is not a legal json file")