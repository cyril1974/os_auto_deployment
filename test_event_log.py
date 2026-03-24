import base64
import sys
import os
from datetime import datetime

# Ensure we can import the local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from os_deployment.lib import utils, constants

def main():
    # Test Parameters
    bmcip = "10.99.236.59"
    user = "admin"
    password = "ServerTools@test"
    from_timestamp = 1774296172

    print(f"[*] Testing Event Log Fetch on {bmcip}")
    print(f"[*] Search Timestamp: {datetime.fromtimestamp(from_timestamp).isoformat()} ({from_timestamp})")

    # Construct Auth String
    auth_bytes = f"{user}:{password}".encode("ascii")
    auth_string = "Basic " + base64.b64encode(auth_bytes).decode("ascii")

    # 1. Fetch RAW Logs (Verify Line 374)
    print(f"[*] STEP 1: Fetching raw logs from BMC...")
    result = utils.getSystemEventLog(bmcip, auth_string, from_timestamp)
    print(f"[+] Received {len(result)} raw log entries.")

    # 2. Filter Custom Events (Verify Line 375)
    print(f"[*] STEP 2: Filtering for prefix: {constants.EventLogPrefix}")
    export = utils.filter_custom_event(result)
    print(f"[+] Identified {len(export)} custom forensic entries.")

    # 3. Display Results
    if export:
        print("\n--- [ Matched Entries ] ---")
        for item in export:
            msg = item.get("Message", "No Message")
            created = item.get("Created", "No Timestamp")
            print(f"- [{created}] {msg}")
    else:
        print("\n[!] SUCCESS: No custom logs matched (or list is empty).")
        print("[!] If logs were expected, please check if they have been written to the BMC yet.")

if __name__ == "__main__":
    main()
