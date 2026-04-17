import sys
import requests
import json
import urllib3
import urllib3.exceptions

import os_deployment.lib.state_manager as state_manager
from . import auth
from . import utils
from . import constants

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ENDPOINT_DICT = {
    "8": "/redfish/v1/Systems/Self",
    "7": "/redfish/v1/Systems/system",
    "6": "/redfish/v1/Systems/system"
}

RESET_ENDPOINT_DICT = {
    "8": "/redfish/v1/Systems/Self/Actions/ComputerSystem.Reset",
    "7": "/redfish/v1/Systems/system/Actions/ComputerSystem.Reset",
    "6": "/redfish/v1/Systems/system/Actions/ComputerSystem.Reset"
}

def _check_power_status(target: str , auth_header: str):
    gen = str(state_manager.state.generation)
    ENDPOINT = ENDPOINT_DICT[gen]
    if utils.check_redfish_api(target,auth_header):
        response = utils.redfish_get_request(f"{ENDPOINT}?$select=PowerState",bmc_ip=target,auth=auth_header) 
        # print(response.__dict__)
        if response is not None and (response.status_code == 200 or response.status_code == 500):
            try:
                data = response.json()
                return data.get("PowerState",None)
            except Exception as e:
                print(f"Check Power Status Fail...({e})")
                return False 
        else:
            print("Request for Power State Fail !!")    
            return False

def _fetch_etag_gen8(target: str, auth_header: str, endpoint: str) -> str:
    """Gen 8 only: fetch the current ETag from the Systems endpoint (required for PATCH)."""
    url = f"https://{target}{endpoint}"
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        # Keep the ETag value exactly as returned by the server (quotes included).
        # The If-Match header must match verbatim, e.g. "1776395333".
        etag = response.headers.get("ETag", "")
        return etag
    except requests.RequestException as e:
        print(f"[{utils.formatted_time()}] Failed to fetch ETag from {url}: {e}")
        return ""

def _set_boot_cdrom(target: str , auth_header: str):
    gen = str(state_manager.state.generation)
    ENDPOINT = ENDPOINT_DICT[gen]
    return_value = False
    url = f"https://{target}{ENDPOINT}"
    data = json.dumps({
        "Boot": {
            "BootSourceOverrideTarget": "UefiShell",
            "BootSourceOverrideEnabled": "Once"
        }
    })

    headers = {
        "Accept": "application/json",
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }

    if gen == '8':
        # Step 1 — fetch current ETag
        etag = _fetch_etag_gen8(target, auth_header, ENDPOINT)
        if not etag:
            print(f"[{utils.formatted_time()}] Set {target} Boot to CD-ROM FAIL: could not retrieve ETag.")
            return False
        # Step 2 — PATCH with If-Match header
        headers["If-Match"] = etag
        data = json.dumps({
            "Boot": {
                "BootSourceOverrideTarget": "UefiShell",
                "BootSourceOverrideEnabled": "Once",
                "BootSourceOverrideMode" : "UEFI"
            }
        })   

    try:
        response = requests.patch(url, headers=headers, data=data, verify=False)
        if response.status_code == 204:
            print(f"[{utils.formatted_time()}] Set Boot Order to CD-ROM Success !!")
            return_value = True
        else:
            try:
                json_data = response.json()
            except Exception:
                json_data = None
            print(f"[{utils.formatted_time()}] Set {target} Boot to CD-ROM FAIL via {url} with data {data} , Status Code {response.status_code}\n{json_data}")

    except requests.RequestException as e:
        print(f"[{utils.formatted_time()}] Set {target} Boot to CD-ROM FAIL via {url} with data {data}")

    return return_value

def _clear_postcode_log(target: str, auth_header: str) -> bool:
    """POST to POSTCODE_LOG_CLEAR_API to wipe the PostCode log on the BMC."""
    return_value = False
    url = f"https://{target}{constants.POSTCODE_LOG_CLEAR_API}"
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, data="{}", verify=False)
        if response.status_code in (200, 204):
            # print(f"[{utils.formatted_time()}] PostCode Log cleared successfully.")
            return_value = True
        else:
            try:
                json_data = response.json()
            except Exception:
                json_data = None
            print(f"[{utils.formatted_time()}] Clear PostCode Log FAIL via {url}, "
                  f"Status Code {response.status_code}\n{json_data}")
    except requests.RequestException as e:
        print(f"[{utils.formatted_time()}] Clear PostCode Log FAIL via {url}: {e}")
    return return_value

def clear_postcode_log(target: str, config: dict) -> bool:
    """Public entry point: authenticate then clear the PostCode log."""
    try:
        auth_header = auth.get_auth_header(target, config)
        return _clear_postcode_log(target, auth_header)
    except Exception as e:
        print(f"[{utils.formatted_time()}] Clear PostCode Log exception: {e}")
        return False

def _exec_reboot(target: str , auth_header: str):
    gen = str(state_manager.state.generation)
    ENDPOINT = ENDPOINT_DICT[gen]
    RESET_ENDPOINT = RESET_ENDPOINT_DICT[gen]
    return_value = False
    url = f"https://{target}{RESET_ENDPOINT}" 
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header,
        'Content-Type': 'application/json'
    }
    
    reset_type = "On" if _check_power_status(target , auth_header)=="Off" else "ForceRestart"
    data = json.dumps({"ResetType": reset_type})
    try:
        response = requests.post(url, headers=headers, data=data , verify=False)
        # print(response.text)
        if response.status_code == 200:
            try:
                json_data = response.json()
                if state_manager.state.generation == 7:           
                    try:
                        message = json_data.get("error").get("@Message.ExtendedInfo")[0]
                        if message["MessageSeverity"] == "OK":
                            print(f"[{utils.formatted_time()}] Set Server to Reboot Successful")
                            return_value = True
                        else:
                            Serverity = message["MessageSeverity"]
                            ErrorMessage = message["Message"]
                            Resolution = message["Resolution"]
                            print(f"[{utils.formatted_time()}] Set Server to Reboot FAIL !!!")
                            print(f"{Serverity}:\n{ErrorMessage}\n{Resolution}")    
                    except Exception as e:
                        print(json.dumps(json_data, indent=2))
                        print("Get Message Fail after Reboot") 
                    #print("Response Body:")
                    #print(json.dumps(json_data, indent=2))
                elif state_manager.state.generation == 6:
                    try:
                        message = json_data.get("@Message.ExtendedInfo")[0]
                        if message["MessageSeverity"] == "OK":
                            # print("Reboot Successful")
                            print(f"[{utils.formatted_time()}] Set Server to Reboot Successful")
                            return_value = True
                        else:
                            Serverity = message["MessageSeverity"]
                            ErrorMessage = message["Message"]
                            Resolution = message["Resolution"]
                            print(f"{Serverity}:\n{ErrorMessage}\n{Resolution}")    
                    except Exception as e:
                        print(json.dumps(json_data, indent=2))
                        print("Get Message Fail after Reboot")         
            except json.JSONDecodeError:
                print("❌ Failed to parse response body as JSON.")
        else:
            try:
                json_data = response.json()
                print(f"Request {url} FAIL with status code {response.status_code}")
                print(json.dumps(json_data, indent=2))
            except json.JSONDecodeError:
                print("❌ Failed to parse response body as JSON.")
            
    except requests.RequestException as e:
        print(f"Reboot FAIL via {url} with data {data}")
        
    return return_value        
def set_boot_cdrom(target: str , auth_header: str):
    try:
        _set_boot_cdrom(target ,  auth_header)
        return True
    except Exception as e:
        print("Set Boot to CD-ROM Fail !!")    
        return False
def reboot_cdrom(target:str,config:dict):
    auth_string = auth.get_auth_header(target,config)
    returnValue = ""
    if _set_boot_cdrom(target , auth_string):
        if _exec_reboot(target , auth_string):
            current_timestamp = utils.getTargetBMCDateTime(target,auth_string)["data"]["timestamp"]
            print(f"[{utils.formatted_time()}] Server is Rebooting .... ")
            returnData = utils.wait_for_reboot(target , auth_string,current_timestamp)
            status = returnData["status"]
            reboot_time = returnData["time_spend"]
            returnValue = returnData["booted_time"]
            if status == "OK":
                print(f"[{utils.formatted_time()}] Server Reboot Complete , Time Elapsed : {reboot_time} seconds ")
                return returnValue
            else:
                print(f"[{utils.formatted_time()}] Server Reboot FAIL !!")
                return None
    return None    
                
            