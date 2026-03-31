import sys
import base64

def get_auth_header(target: str, config: dict) -> str:
    try:
        username = config["auth"][target]["username"]
        password = config["auth"][target]["password"]
    except KeyError:
        sys.exit(f"❌ Missing credentials for target '{target}' in config.")

    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"

def get_auth_form(target: str, config: dict) -> str:
    try:
        username = config["auth"][target]["username"]
        password = config["auth"][target]["password"]
    except KeyError:
        sys.exit(f"❌ Missing credentials for target '{target}' in config.")
    return f"username={username}&password={password}"