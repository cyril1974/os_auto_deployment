import json
import requests
from pathlib import Path
import sys
import urllib3
import urllib3.exceptions
import zipfile
# from . import auth
from . import constants
from . import redfish
import os_deployment.lib.state_manager as state_manager
from time import sleep
from datetime import datetime, timezone
from io import BytesIO
TERMINATE = True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 
# 
# def MsgCtl(string, VERBOSE_LEVEL, *modes):
#     '''MsgCtl(strings,VERBOSE_LEVEL,*mode)
#     mode:               meaning:
#     print_msg_x         append color and prefix, 0 is normal print
#     direct_log_err      direct append err_msg to text
#     direct_log_out      direct append out_msg to text
#     remove_log_out      clear logfile *.out
#     remove_log_err      clear logfile *.err
#     '''
#     if string is None:
#         string = ""
#     string = str(string)
#     for mode in modes:
#         if "debug_log_" in mode:
#             debug_log("debug", string, VERBOSE_LEVEL)
#         if "print_msg_" in mode:
#             print_msg(mode.split("print_msg_")[1], string, VERBOSE_LEVEL)
#         if "direct_log_" in mode:
#             direct_log(mode.split("direct_log_")[1], string, VERBOSE_LEVEL)
#         if "remove_log_" in mode:
#             remove_log(mode.split("remove_log_")[1], string, VERBOSE_LEVEL)
def redfish_get_request(cmd, bmc_ip=None, auth=None, cookies=None, retry=0 , custom_timeout=constants.REDFISH_TIMEOUT):
        cmd = str(cmd)
        try:
            if bmc_ip is None:
                raise Exception("Cannot proceed: bmc_ip must not be None")
            if auth is not None:
                headers = {
                    "Accept": "application/json",
                    "Authorization": auth
                }
            else:
                headers = {"Accept": "application/json"}    
            url = 'https://' + bmc_ip + cmd if not cmd.strip().startswith('http') else cmd
            # print(url)
            # real_timeout = 5 if cmd=="/redfish/v1" else constants.REDFISH_TIMEOUT
            # print(real_timeout)
            return requests.get(url, headers=headers,
                                verify=False, timeout=(3, custom_timeout),
                                cookies=cookies)
        except Exception as excp:
            if cmd!="/redfish/v1" and retry<2:
                # print('Exception: {}...try again !!'.format(excp))
                redfish_get_request(cmd,bmc_ip,auth,retry = retry +1,custom_timeout=custom_timeout)
            else:    
                return None
                # raise excp
       

def check_redfish_api(target,auth):
    try:
        response = redfish_get_request('/redfish/v1',bmc_ip=target,auth=auth)
        return response.status_code == 200
    except Exception:
        return False

def check_auth_valid(target, auth):
    """Check if the provided authentication credentials are valid.

    Uses the Redfish SessionService endpoint (/redfish/v1/SessionService)
    which requires authentication. A successful response (HTTP 200) indicates
    valid credentials, while a 401 response indicates invalid credentials.

    Args:
        target: BMC IP address or hostname.
        auth: Authorization header string (e.g. "Basic <base64>").

    Returns:
        dict: A result dictionary with the following structure:
            - {"status": "ok", "message": "Authentication is valid"}
              when credentials are accepted (HTTP 200).
            - {"status": "unauthorized", "message": "..."}
              when credentials are rejected (HTTP 401).
            - {"status": "error", "message": "..."}
              for any other failure (BMC unreachable, timeout, etc.).
    """
    SESSION_SERVICE_API = "/redfish/v1/SessionService"
    try:
        response = redfish_get_request(SESSION_SERVICE_API, bmc_ip=target, auth=auth)
        if response is None:
            return {
                "status": "error",
                "message": f"Unable to reach BMC at {target} (no response)"
            }
        if response.status_code == 200:
            return {
                "status": "ok",
                "message": "Authentication is valid"
            }
        elif response.status_code == 401:
            return {
                "status": "unauthorized",
                "message": "Authentication failed: invalid username or password"
            }
        else:
            return {
                "status": "error",
                "message": f"Unexpected response code: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Auth check failed: {e}"
        }
    
def wait_for_bmc(target,auth,retries=7, wait_time=30, initial_wait=0, check_reboot_times=1):
    i = 0 
    sleep(initial_wait)
    reboot_times = 0
    while i <= retries:
        sleep(wait_time)
        if check_redfish_api(target,auth):
            reboot_times += 1
            if check_reboot_times > reboot_times:
                sleep(90)
            else:
                return True
        i += 1
    return False   

def redfish_specific_error(string, error_code, log_str='', response=''):
    if log_str and response:
        # MsgCtl('Request: {}\nResponse: {}\n'.format(log_str, response),False, "print_msg_2", "direct_log_dbg")
        print(f"Error : Request: {log_str} \nResponse: {response}\n")
    if not TERMINATE:
        raise ConnectionError('Redfish response error')
    if error_code == 'NoError':
        print(f"{string}\n")
        # MsgCtl(string + "\n", True, "print_msg_5", "direct_log_out")
    else:
       print(f"{string}\n")
       # MsgCtl(string + "\n", True, "print_msg_2", "direct_log_err")
    # safe_exit(ErrorNumber[error_code])
    
def redfish_handle_exceptions(msg, error_code, retry):
    if retry == 0:
        redfish_specific_error(msg + " Exiting..", error_code)
    # MsgCtl(msg + " Retrying..\n", True, "print_msg_5", "direct_log_err")
    print(f"{msg} Retrying..\n")
    return retry - 1 
def MsgCtl(string, VERBOSE_LEVEL, *modes):
    '''MsgCtl(strings,VERBOSE_LEVEL,*mode)
    mode:               meaning:
    print_msg_x         append color and prefix, 0 is normal print
    direct_log_err      direct append err_msg to text
    direct_log_out      direct append out_msg to text
    remove_log_out      clear logfile *.out
    remove_log_err      clear logfile *.err
    '''
    if string is None:
        string = ""
    string = str(string)
    print(f"{string}")
    # for mode in modes:
    #     if "debug_log_" in mode:
    #         debug_log("debug", string, VERBOSE_LEVEL)
    #     if "print_msg_" in mode:
    #         print_msg(mode.split("print_msg_")[1], string, VERBOSE_LEVEL)
    #     if "direct_log_" in mode:
    #         direct_log(mode.split("direct_log_")[1], string, VERBOSE_LEVEL)
    #     if "remove_log_" in mode:
    #         remove_log(mode.split("remove_log_")[1], string, VERBOSE_LEVEL)
    
def getTargetBMCDateTime(target,auth):
    if check_redfish_api(target,auth): 
        response = redfish_get_request(constants.BMC_MANAGER_API,bmc_ip=target,auth=auth)
        try:
            data = response.json()
            # print(data.keys())  
            return {
                "status":"ok",
                "data":{
                    "string":data["DateTime"][:19],
                    "timestamp":datetime.fromisoformat(data["DateTime"].replace('Z', '+00:00')).timestamp()
                    }
            }
        except Exception as e:
            return {"status":"error","data":"Get BMC Manager Data Fail"}        
    
    # print(json.dumps(response.json(),indent=4))
    
def getPostCodeLog(target,auth,fromtimestamp):
    return_data = []
    gen = str(state_manager.state.generation)
    if check_redfish_api(target,auth): 
        response = redfish_get_request(constants.POSTCODE_LOG_API,bmc_ip=target,auth=auth)
        # try:
        data = response.json()["Members"]
        if data is not None and len(data) > 0:
            for item in data:
                event_time = int(datetime.fromisoformat(item["Created"][:19]).timestamp())
                bootID = item["Id"]

                if gen == "6":
                    boot_count = item["MessageArgs"][0]
                    tmp = item["MessageArgs"][2].split(":")
                    event_code = tmp[0].strip()
                    event_text = tmp[1].strip()
                elif gen == "7":
                    boot_count = item["MessageArgs"][0]
                    event_code = item["MessageArgs"][2]
                    event_text = item["MessageArgs"][3]
                if event_time > fromtimestamp:
                    return_data.append({
                        "boot_id":bootID,
                        "boot_count":boot_count,
                        "time":item["Created"],
                        "PostCode":event_code,
                        "text":event_text
                    }) 
        # except Exception as e:
        #     print("Get Post Log Fail !!")    
    return return_data

def wait_for_reboot(target,auth,fromtimestamp):
    is_boot = False
    timeout_stamp = int(fromtimestamp + constants.REBOOT_TIMEOUT)
    current_timestamp = int(getTargetBMCDateTime(target,auth)["data"]["timestamp"])
    booted_time = ""
    boot_complete_string = {
        "6":"Clear POST Code",
        "7":"Ready To Boot event"
    }
    gen = str(state_manager.state.generation)
    while not is_boot and current_timestamp<=timeout_stamp:
        result_log = getPostCodeLog(target,auth,fromtimestamp)
        if len(result_log) > 0: # and len(result_log)>start_idx:
            export_log = []
            for row in result_log:
                if row['boot_count'] != "1":
                    break
                export_log.append(f"{row['time']}\t{row['PostCode']}\t{row['text']}")
                if boot_complete_string[gen] in row['text']:
                    booted_time = row['time'][:19]
                    is_boot = True
                    break   
            
            if len(export_log)  > 0:
                display_row = export_log[-1]
                print("\r\033[K", end="")  # \r = return to start; \033[K = clear to end of line
                print(f"\r{display_row}",end="",flush=True)  
        if not is_boot:
            # start_idx = len(result_log)
            sleep(1)
            try:
                BMC_time = getTargetBMCDateTime(target,auth)
                current_timestamp = int(BMC_time["data"]["timestamp"]) if "data" in BMC_time else current_timestamp
            except:
                pass    
            # current_timestamp = int(getTargetBMCDateTime(target,auth)["data"]["timestamp"])
    print("")
    return {
                "status": "OK" if is_boot else "FAIL",
                "time_spend":int(current_timestamp - fromtimestamp),
                "booted_time": booted_time,
                "message": f"Reboot Fail (Timeout {constants.REBOOT_TIMEOUT})"
            }
    return  int(current_timestamp - fromtimestamp)
    
def getSystemEventLog(target,auth,fromtimestamp):
    return_data = []
    if check_redfish_api(target,auth): 
        gen = str(state_manager.state.generation)
        event_cnt = 0
        show_log_cnt = 500
        
        # 1. Get total count of logs to calculate skip offset
        url_count = f"{constants.LOG_FETCH_API}/?$top=1"
        response = redfish_get_request(url_count, bmc_ip=target, auth=auth, custom_timeout=10)
        try:
            if response and response.status_code == 200:
                event_cnt = int(response.json().get("Members@odata.count", 0))
        except (ValueError, KeyError, AttributeError):
            pass

        # 2. Fetch the latest batch (typically 500 entries)
        if event_cnt > show_log_cnt:
            url = f"{constants.LOG_FETCH_API}/?$skip={event_cnt - show_log_cnt}&$top={show_log_cnt}"
        else:
            url = f"{constants.LOG_FETCH_API}/?$top={show_log_cnt}"
            
        # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}] {gen} Platform, fetching from: {url}")
        response = redfish_get_request(url, bmc_ip=target, auth=auth, custom_timeout=10)
        try:
            data = response.json().get("Members", [])
            if data and len(data) > 0:
                for item in data:
                    try:
                        # Full ISO8601 parsing handles timezone (+00:00) correctly
                        created_str = item["Created"].replace('Z', '+00:00')
                        event_time = int(datetime.fromisoformat(created_str).timestamp())
                        if event_time > fromtimestamp:      
                            return_data.append(item) 
                    except (ValueError, KeyError):
                        continue
        except Exception as e:
            print("Get Event Log Fail !!")    
    # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}] Send Event Log {len(return_data)} !!")
    # print(f"{return_data}")
    return return_data 

def filter_custom_event(data):
    prefix = constants.EventLogPrefix
    return [
        item for item in data
        if "SEL Entry Added" in item.get("Message", "")
        and (msg := item["Message"].split(":")[-1].strip()).startswith(prefix)
        and len(msg) > len(prefix)
    ]
def filter_message_event(data,search_for):
    return [
        item for item in data
        if search_for in item.get("Message", "")
    ]
def decode_event(data):
    export_string = ""
    if data.startswith(constants.EventLogPrefix):
        suffix = data[len(constants.EventLogPrefix):]  # get "000000000008"
        sev_code = suffix[0:2]
        cat_code = suffix[2:4]
        msg_code = suffix[6:12]  # skip 2 reserved chars
        
        # Lookup each value in its dict
        severity = constants.EventLogSServerity.get(sev_code, f"UnknownSeverity({sev_code})")
        category = constants.EventLogCategory.get(cat_code, f"UnknownCategory({cat_code})")
        message = constants.EventMessage.get(msg_code, f"UnknownMessage({msg_code})")
        export_string = f"{severity} {category} {message}"
    return export_string

def umount_media(target,auth,vmedia_point):
    result = False
    response = redfish_get_request(vmedia_point,bmc_ip=target,auth=auth) 
    try:
        data = response.json()
        umount_url = data["Actions"]["#VirtualMedia.EjectMedia"]["target"]
        # print(umount_url)
        resp = redfish.redfish_post(target,auth,umount_url)
        if resp.status_code < 400:
            #print(f"Umount {vmedia_point} Success...")
            result = True
        else:
            print(f"Umount {vmedia_point} Fail...({resp.text})")    
            result = False
    except Exception as e: 
        print(f"Umount {vmedia_point} fail...({e})")
        
    return result

def formatted_time():
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")  

def log_collect(target,auth,log_path,local_path="./collected_log/"):
    local_dir_path = local_path
    utility_mount.unmount_ivm(target,auth,ignore_error=True)
    body = json.dumps({'ImagePath': log_path})
    headers = {
 #       "Accept":"application/json",
        "Content-Type":"application/json"
    }
    # print(body)
    gen = str(state_manager.state.generation)
    response = redfish.redfish_post(target,auth,constants.GETFILE_IMAGE_API[gen],dataset=body,headers=headers,retry=5)
    if response.status_code == 200:
        try:
            Path(local_dir_path).mkdir(exist_ok=True,parents=True)
            zip_obj = zipfile.ZipFile(BytesIO(response.content))
            zip_obj.extractall(local_dir_path)
            zip_obj.close()
            print(f"[{formatted_time()}] Log Collection Success , Dump to {local_dir_path}")
            return True
        except Exception as e:
            print(f"[{formatted_time()}] Log Collection Fail {e}")
            return False
    else:
       print(f"[{formatted_time()}] Log Collection Fail {response.text}")
       return False    

def check_mount_status(target,auth,endpoint,allData=False):
    if check_redfish_api(target,auth): 
        response = redfish_get_request(endpoint,target,auth,custom_timeout=10)
        if response is not None and response.status_code == 200:
            try:
                data = response.json()
                if allData:
                    return data
                else:
                    return data.get("Inserted",False)
            except Exception as e:
                print(f"Get Media {endpoint} Information fail...({e})")
                return False    
        elif response is None:
            print(f"Request {endpoint} Fail without Response")
            return False
        else:    
            print(f"Request {endpoint} Fail with code {response.status_code}")
            return False
    else:
        return False    

def reboot_detect(target,auth,checktimestamp):
    check_data = getPostCodeLog(target,auth,checktimestamp)
    if check_data and len(check_data) > 0:
        start_idx = 0
        for i in range(start_idx,len(check_data)):
            row = check_data[i]
            if row['PostCode'] == "0x01" or "Power On" in row['text']:
                return True
        return False # No Power On Post Code Detect , return     
    else:
        return False

def print_message(target,auth,message):
    time_string = ""
    result = getTargetBMCDateTime(target,auth)
    if result is not None and result["status"] == "ok":
        time_string = result["data"]["string"]
    else:
        time_string = formatted_time()  
        
    print(f"[{time_string}] {message}")
    return True      

def get_version(target,auth_string,category):
    if category in constants.VERSION_GET_API:
        if check_redfish_api(target,auth_string):
            response = redfish_get_request(constants.VERSION_GET_API[category],target,auth_string,custom_timeout=10)
            try:
                data = response.json()
                return data.get("Version","N/A")
            except Exception as e:
                print_message(target,auth_string,f"Get {category} Version Information fail...({e})")
                return "N/A"    
        else:
            print_message(target,auth_string,f"Get {category} Version Fail due to BMC is not accessible")
            return "N/A" 
    else:
        print_message(target,auth_string,f"{category} Version is not Supported")
        return "N/A"


def print_board_version(ver_info):
    export_text = "No Data"
    if ver_info is not None and isinstance(ver_info, dict):
        export_text = "******** Versions List ********\n"
        export_text = f"{export_text}** BIOS : {ver_info['BIOS'] if 'BIOS' in ver_info else 'N/A'}\n"
        export_text = f"{export_text}**  BMC : {ver_info['BMC'] if 'BMC' in ver_info else 'N/A'}\n"
        export_text = f"{export_text}** CPLD : {ver_info['CPLD'] if 'CPLD' in ver_info else 'N/A'}\n"
        export_text = f"{export_text}**  ROT : {ver_info['ROT'] if 'ROT' in ver_info else 'N/A'}\n"
    print(export_text)
    return True

def get_virtual_media_permission(target,auth_string):
   gen = str(state_manager.state.generation)
   if check_redfish_api(target,auth_string):
        permission_table = {
            "outband":{}, 
            "inband":{}
            }
        response = redfish_get_request(constants.VIRTUAL_MEDIA_API_DICT[gen],target,auth_string,custom_timeout=10) 
        try:
            data = response.json()
            vm_list = data["Members"]
            for vm in vm_list:
                # print(vm["@odata.id"])
                vm_endpoint = vm["@odata.id"]
                if check_redfish_api(target,auth_string):
                    mount_point = str(vm_endpoint).split("/")[-1]
                    response_vm = redfish_get_request(vm_endpoint,target,auth_string,custom_timeout=10)
                    if response_vm.status_code == 200:
                        if mount_point=="Inband":
                            permission_table["inband"][mount_point] = True
                        else:
                            permission_table["outband"][mount_point] = True
                    else:
                        if mount_point=="Inband":
                            permission_table["inband"][mount_point] = False
                        else:
                            permission_table["outband"][mount_point] = False           
            return permission_table
        except Exception as e:
            print_message(target,auth_string,f"Get Virtual Media Fail...({e})")
            return False  

