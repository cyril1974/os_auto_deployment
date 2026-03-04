import json
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

def _fetch_virtual_media(target: str, auth_header: str) -> requests.Response:
    gen = str(state_manager.state.generation)
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
    members = json_body.get("Members")
    output = []
    if isinstance(members, list):
        for member in members:
            odata_id = member.get("@odata.id")
            if "WebISO" in odata_id:
                output.append(odata_id)            
    else:
        print("'Members' not found or is not a valid array.")
    
    return output    

def _check_usable(target: str,auth_header: str,endpoint:str):
    check_url = f"https://{target}{endpoint}"
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header
    }
    try:
        response = requests.get(check_url, headers=headers, verify=False)
        # print(f"Status Code: {response.status_code}")
        # print(f"Output: {response.text}")
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
    retValue = False
    mount_url =  f"https://{target}{endpoint}"  
    headers = {
        "Accept": "application/json",
        "Authorization": auth_header,
        'Content-Type': 'application/json'
    }
    data = json.dumps({
        "Image": mount_path,
        "UserName": "",
        "Password": "",
        "WriteProtected": False,
        "TransferProtocolType": "NFS",
        "Inserted": True
    })
    try:
        response = requests.post(mount_url, headers=headers, data=data , verify=False)
        # print(f"Status Code: {response.status_code}")
        # print(f"Output: {response.text}")
        # print(f"{state_manager.state.generation},{state_manager.state.product_model}")
        if response.status_code == 200:
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
    retValue = False
    json_data = {}
    try:
        json_data = response.json()
        # print(f"Get Remote Virtual Media Success \n{json_data}")
    except json.JSONDecodeError:
        print("❌ Failed to parse response body as JSON.")
        return ""

    endpoints = _get_candidate_mount_point(json_data)
    
    if len(endpoints) > 0:
        for endpoint in endpoints:
            use_endpoint = endpoint
            url = _check_usable(target,auth_string,endpoint)
            # print(url)
            if url:
                # print(f"Virtual Media Mount Point : {endpoint}")
                if exec_mount_image(path,target,auth_string,url): 
                    # print(f"Mount OK , Rreturn Value is {use_endpoint}")
                    return use_endpoint 
        # sys.exit("DEBUG!!!")        
    else:
        print("No Mount Point for Mounting Remote Image")
    return  None

  