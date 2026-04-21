import json
import time
import requests
from pathlib import Path
import sys
import urllib3
import urllib3.exceptions
import os_deployment.lib.state_manager as state_manager

from . import auth
from . import constants
# from . import generation


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _enable_rmedia_gen8(target: str, auth_header: str) -> None:
    """Gen 8 only: enable remote media via AMIVirtualMedia before querying virtual media.

    Checks VirtualMedia Members first — skips the enable POST if Members is already populated.
    """
    check_url = f"https://{target}/redfish/v1/Managers/Self/VirtualMedia"
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header
    }
    try:
        response = requests.get(check_url, headers=headers, verify=False)
        json_data = response.json()
        members = json_data.get("Members", [])
        if members:
            print(f"[Gen8] Remote media already enabled ({len(members)} member(s) present), skipping EnableRMedia.")
            return
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"[Gen8] VirtualMedia check failed: {e} — proceeding with EnableRMedia anyway.")

    enable_url = f"https://{target}/redfish/v1/Managers/Self/Actions/Oem/AMIVirtualMedia.EnableRMedia"
    enable_headers = {
        "Content-Type": "application/json",
        "Authorization": auth_header
    }
    data = json.dumps({"RMediaState": "Enable"})
    try:
        response = requests.post(enable_url, headers=enable_headers, data=data, verify=False)
        print(f"[Gen8] EnableRMedia status: {response.status_code}")
    except requests.RequestException as e:
        print(f"[Gen8] EnableRMedia request failed: {e}")
    time.sleep(5)

def _fetch_virtual_media(target: str, auth_header: str) -> requests.Response:
    gen = str(state_manager.state.generation)
    if gen == '8':
        _enable_rmedia_gen8(target, auth_header)
    url = f"https://{target}{constants.VIRTUAL_MEDIA_API_DICT[gen]}"
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header
    }
    try:
        return requests.get(url, headers=headers, verify=False)
    except requests.RequestException as e:
        sys.exit(f"❌ Request failed: {e}")

def _get_candidate_mount_point(json_body: dict):
    gen = str(state_manager.state.generation)
    members = json_body.get("Members")
    if not isinstance(members, list):
        print("'Members' not found or is not a valid array.")
        return []
    return [
        m.get("@odata.id") for m in members
        if gen not in ('6', '7') or "WebISO" in (m.get("@odata.id") or "")
    ]

def _check_usable(target: str,auth_header: str,endpoint:str):
    check_url = f"https://{target}{endpoint}"
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header
    }
    try:
        response = requests.get(check_url, headers=headers, verify=False)
        # print(f"Status Code: {response.status_code}")
        # print(f"Output: {json.dumps(response.text,indent=2)}")
        try:
            json_data = response.json()
            if "Inserted" in json_data and json_data["Inserted"] == False:
                try:
                    insert_url = json_data.get("Actions").get("#VirtualMedia.InsertMedia").get("target") 
                    return insert_url
                except Exception as e:
                    return None    
        except json.JSONDecodeError:
            print("❌ Failed to parse response body as JSON.")
            return None
            # sys.exit("❌ Failed to parse response body as JSON.")
        # print("Response Body:")
        # print(json.dumps(json_data, indent=2))
    except requests.RequestException as e:
        return None
        # sys.exit(f"❌ Request failed: {e}")

def exec_mount_image(mount_path,target: str,auth_header: str,endpoint:str):
    # print(endpoint)
    gen = str(state_manager.state.generation)
    
    retValue = False
    mount_url =  f"https://{target}{endpoint}"  
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header,
        'Content-Type': 'application/json'
    }
    if gen == '8':
         data = json.dumps({
            "Image": mount_path,
            "WriteProtected": True,
            "TransferProtocolType": "NFS",
            "Inserted": True
        })
    else:    
        data = json.dumps({
            "Image": mount_path,
            "UserName": "",
            "Password": "",
            "WriteProtected": True,
            "TransferProtocolType": "NFS",
            "Inserted": True
        })
    try:
        response = requests.post(mount_url, headers=headers, data=data , verify=False)
        print(f"Status Code: {response.status_code}")
        # print(f"Output: {response.text}")
        print(f"{state_manager.state.generation},{state_manager.state.product_model}")
        if response.status_code in [200,202,204]:
            if state_manager.state.generation == 7:           
                try:
                    json_data = response.json()
                    try:
                        message = json_data.get("error").get("@Message.ExtendedInfo")[0]
                        if message["MessageSeverity"] == "OK":
                            # print(f"Mount Image {mount_path} to {target} Successful")
                            retValue = True
                        else:
                            Serverity = message["MessageSeverity"]
                            ErrorMessage = message["Message"]
                            Resolution = message["Resolution"]
                            print(f"{Serverity}:\n{ErrorMessage}\n{Resolution}")    
                    except Exception as e:
                        print(json.dumps(json_data, indent=2))
                        print(f"Get Message {e} Fail after Mount") 
                    #print("Response Body:")
                    #print(json.dumps(json_data, indent=2))
                except json.JSONDecodeError:
                    print("❌ Failed to parse response body as JSON.")
                    # sys.exit("❌ Failed to parse response body as JSON.")
            else:
                retValue = True
        else:
            try:
                json_data = response.json()
                print("Response Body:")
                print(json.dumps(json_data, indent=2))
            except json.JSONDecodeError:
                print("❌ Failed to parse response body as JSON.")
            print(f"Request {mount_url} FAIL with status code {response.status_code}")    
    except requests.RequestException as e:
        print(f"{target} Mount Image {mount_path} FAIL via {mount_url} ")
    return retValue    

def mount_image(path:str,target:str,config:dict):
    auth_string = auth.get_auth_header(target,config)
    response = _fetch_virtual_media(target, auth_string)
    # print(response.json())
    retValue = False
    json_data = {}
    try:
        json_data = response.json()
        # print(f"Get Remote Virtual Media Success \n{json_data}")
    except json.JSONDecodeError:
        print("❌ Failed to parse response body as JSON.")
        return ""

    endpoints = _get_candidate_mount_point(json_data)
    # print(endpoints)
    if len(endpoints) > 0:
        for endpoint in endpoints:
            use_endpoint = endpoint
            url = _check_usable(target,auth_string,endpoint)
            print(url)
            
            if url:
                # print(f"Virtual Media Mount Point : {endpoint}")
                # sys.exit("DEBUG!!!")
                if exec_mount_image(path,target,auth_string,url):
                    gen = str(state_manager.state.generation)
                    if gen == '8':
                        poll_url = f"https://{target}{endpoint}"
                        poll_headers = {
                            "Accept": "application/json",
                            "Authorization": auth_string
                        }
                        print(f"⏳ Mount starting — waiting for redirection on {endpoint} ...")
                        deadline = time.time() + 60
                        redirection_status = ""
                        while time.time() < deadline:
                            try:
                                poll_resp = requests.get(poll_url, headers=poll_headers, verify=False)
                                poll_data = poll_resp.json()
                                redirection_status = (
                                    poll_data.get("Oem", {})
                                             .get("Ami", {})
                                             .get("RedirectionStatus", "")
                                )
                                if "Started" in redirection_status:
                                    print(f"✅ Mount started: {redirection_status}")
                                    return use_endpoint
                            except (requests.RequestException, json.JSONDecodeError):
                                pass
                            time.sleep(3)
                        sys.exit(f"❌ Mount Fail: RedirectionStatus = \"{redirection_status}\"")
                    print(f"✅ Mount started: {endpoint}")
                    return use_endpoint
                else:
                    sys.exit("Mount FAIL!!!")          
        # sys.exit("DEBUG!!!")        
    else:
        print("No Mount Point for Mounting Remote Image")
    return  None

  