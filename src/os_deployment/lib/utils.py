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

def check_auth_valid(target, auth, redfish_supported=True):
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
    
    query_string = "" if redfish_supported else f"?{auth}"
    SESSION_SERVICE_API = "/redfish/v1/SessionService" if redfish_supported else "/api/session"
    request_url = f"https://{target}{SESSION_SERVICE_API}{query_string}"
    auth = None if not redfish_supported else auth
    try:
        response = redfish_get_request(request_url, bmc_ip=target, auth=auth)
        if response is None:
            return {
                "status": "error",
                "message": f"Unable to reach BMC at {target} (no response)"
            }
        if response.status_code == 200:
            return {
                "status": "ok",
                "message": "Authentication is valid",
                "content": response.json()
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
    gen = str(state_manager.state.generation)
    if check_redfish_api(target,auth): 
        bmc_manager_api = constants.BMC_MANAGER_API[gen]
        response = redfish_get_request(bmc_manager_api,bmc_ip=target,auth=auth)
        try:
            data = response.json()
            # print(data.keys())  
            return {
                "status":"ok",
                "data":{
                    "string":data["DateTime"][:19],
                    "timestamp":datetime.fromisoformat(data["DateTime"][:19]).timestamp()
                    }
            }
        except Exception as e:
            return {"status":"error","data":"Get BMC Manager Data Fail"}        
    
    # print(json.dumps(response.json(),indent=4))

def get_redfish_version(target: str, auth: str) -> str | None:
    """GET /redfish/v1 and return the RedfishVersion string (e.g. '1.9.0'), or None on failure."""
    try:
        response = redfish_get_request("/redfish/v1", bmc_ip=target, auth=auth)
        if response and response.status_code == 200:
            return response.json().get("RedfishVersion", None)
    except Exception as e:
        print(f"[{formatted_time()}] Get Redfish Version FAIL: {e}")
    return None

def getPostCodeLog(target,auth,fromtimestamp):

    return_data = []
    gen = str(state_manager.state.generation)
    if check_redfish_api(target,auth): 
        response = redfish_get_request(constants.POSTCODE_LOG_API,bmc_ip=target,auth=auth)
        # try:
        data = response.json()["Members"]
        if data is not None and len(data) > 0:
            # print(f"From Timestamp:{fromtimestamp}")
            for item in data:
                event_time = int(datetime.fromisoformat(item["Created"][:19]).timestamp())
                bootID = item["Id"]
                # print(f"Boot ID:{bootID} Event Time:{event_time}")
                if gen == "6":
                    boot_count = item["MessageArgs"][0]
                    tmp = item["MessageArgs"][2].split(":")
                    event_code = tmp[0].strip()
                    event_text = tmp[1].strip()
                elif gen == "7":
                    boot_count = item["MessageArgs"][0]
                    event_code = item["MessageArgs"][2]
                    event_text = item["MessageArgs"][3]
                # print(f"Boot ID:{bootID} Event Time:{event_time} Message:{event_text}")
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
                # if row['boot_count'] != "1":
                #    break
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
    
# ─── Gen-8 SEL helpers (ported from sel_raw.py) ──────────────────────────────

_SENSOR_TYPE_MAP = {
    "Temperature": 0x01, "Voltage": 0x02, "Current": 0x03, "Fan": 0x04,
    "Physical Security": 0x05, "Platform Security": 0x06, "Processor": 0x07,
    "Power Supply": 0x08, "Power Unit": 0x09, "Cooling Device": 0x0A,
    "Other Units-based Sensor": 0x0B, "Memory": 0x0C, "Drive Slot": 0x0D,
    "POST Memory Resize": 0x0E, "System Firmware Progress": 0x0F,
    "Event Logging Disabled": 0x10, "Watchdog 1": 0x11,
    "System Event": 0x12, "Critical Interrupt": 0x13,
    "Button / Switch": 0x14, "Module / Board": 0x15,
    "Microcontroller / Coprocessor": 0x16, "Add-in Card": 0x17,
    "Chassis": 0x18, "Chip Set": 0x19, "Other FRU": 0x1A,
    "Cable / Interconnect": 0x1B, "Terminator": 0x1C,
    "System Boot / Restart Initiated": 0x1D, "Boot Error": 0x1E,
    "Base OS Boot / Installation Status": 0x1F,
    "OS Stop / Shutdown": 0x20, "Slot / Connector": 0x21,
    "System ACPI PowerState": 0x22, "Watchdog 2": 0x23,
    "Platform Alert": 0x24, "Entity Presence": 0x25,
    "Monitor ASIC / IC": 0x26, "LAN": 0x27,
    "Management Subsystem Health": 0x28, "Battery": 0x29,
    "Session Audit": 0x2A, "Version Change": 0x2B,
    "FRUState": 0x2C,
}


def _parse_sel_message(message: str) -> dict:
    """Parse the comma-separated 'key : value' pairs in a Redfish SEL Message field."""
    fields = {}
    for part in message.split(","):
        part = part.strip()
        if " : " in part:
            k, v = part.split(" : ", 1)
            fields[k.strip()] = v.strip()
    return fields


def _sel_entry_to_raw_ipmi(entry: dict) -> dict:
    """Convert a single Redfish SEL LogEntry (Gen-8) to raw IPMI hex format."""
    msg = _parse_sel_message(entry.get("Message", ""))

    record_id  = int(msg.get("Record_ID", "0"))
    sensor_num = int(msg.get("Sensor_Number", entry.get("SensorNumber", 0)))
    evt_data1  = int(msg.get("Event_Data_1", "0"))
    evt_data2  = int(msg.get("Event_Data_2", "255")) & 0xFF
    evt_data3  = int(msg.get("Event_Data_3", "255")) & 0xFF

    gen_id_raw  = msg.get("Generator_ID", "0x0000")
    gen_id      = int(gen_id_raw, 16)
    gen_id_low  = gen_id & 0xFF
    gen_id_high = (gen_id >> 8) & 0xFF

    sensor_type = _SENSOR_TYPE_MAP.get(entry.get("SensorType", ""), 0x00)

    assertion    = entry.get("EntryCode", "Assert") == "Assert"
    evt_dir_type = 0x6F if assertion else 0xEF

    ts_str = entry.get("EventTimestamp", "")
    try:
        dt          = datetime.fromisoformat(ts_str)
        unix_ts     = int(dt.timestamp())
        dt_formatted = dt.strftime("%Y/%m/%d %H:%M:%S")
    except (ValueError, TypeError):
        unix_ts      = 0
        dt_formatted = ""

    event_type_raw = msg.get("Event_Type", entry.get("EntryType", ""))
    description = (
        event_type_raw.lower()
        .replace(" ", "_")
        .replace("'", "")
        .replace("/", "_")
        .strip("_")
    )

    return {
        "ID":          f"{record_id:04x}h",
        "Record_Type": "02h",
        "TimeStamp":   f"{unix_ts:08x}h",
        "GenID_Low":   f"{gen_id_low:02x}h",
        "GenID_High":  f"{gen_id_high:02x}h",
        "EvMRev":      "04h",
        "Sensor_Type": f"{sensor_type:02x}h",
        "Sensor_Num":  f"{sensor_num:02x}h",
        "EvtDir_Type": f"{evt_dir_type:02x}h",
        "EvtData1":    f"{evt_data1:02x}h",
        "EvtData2":    f"{evt_data2:02x}h",
        "EvtData3":    f"{evt_data3:02x}h",
        "DateTime":    dt_formatted,
        "Event_Type":  "system_event",
        "Sensor_Name": "Unknown",
        "Description": description,
        "Status":      "asserted" if assertion else "deasserted",
        # Keep the original Redfish fields so filter_custom_event() can inspect
        # Message / AdditionalDataURI just like Gen-6/7 entries.
        "Created":     entry.get("EventTimestamp", ""),
        "Message":     entry.get("Message", ""),
        "Id":          str(record_id),
    }


def get_all_sel_logs_gen8(target: str, auth: str, fromtimestamp: int = 0) -> list:
    """
    Fetch SEL log entries from a Gen-8 BMC via Redfish, using the shared
    ``redfish_get_request`` helper (auth-header based, no raw credentials).

    Paginates through all pages via ``Members@odata.nextLink`` and returns
    only entries whose ``EventTimestamp`` is newer than *fromtimestamp*.
    Each entry is converted to the raw IPMI hex dict format produced by
    ``_sel_entry_to_raw_ipmi`` so the rest of the monitoring loop can treat
    Gen-8 results identically to Gen-6/7 results.

    Args:
        target:        BMC IP address.
        auth:          Authorization header string (e.g. "Basic <base64>").
        fromtimestamp: Unix timestamp; only entries newer than this are returned.

    Returns:
        List of raw-IPMI-format dicts (see ``_sel_entry_to_raw_ipmi``).
    """
    endpoint = constants.LOG_FETCH_API["8"]
    raw_entries = []

    while endpoint:
        response = redfish_get_request(endpoint, bmc_ip=target, auth=auth, custom_timeout=10)
        if response is None or response.status_code != 200:
            print(f"Get Gen-8 SEL Fail !! (endpoint: {endpoint}, status: {getattr(response, 'status_code', 'no response')})")
            break
        try:
            data = response.json()
        except Exception as e:
            print(f"Get Gen-8 SEL JSON parse Fail !! {e}")
            break

        raw_entries.extend(data.get("Members", []))

        next_link = data.get("Members@odata.nextLink", "")
        endpoint  = next_link if next_link and next_link.startswith("/") else None

    result = []
    for entry in raw_entries:
        try:
            ts_str  = entry.get("EventTimestamp", "")
            entry_ts = int(datetime.fromisoformat(ts_str[:19]).timestamp()) if ts_str else 0
            if entry_ts > fromtimestamp:
                result.append(_sel_entry_to_raw_ipmi(entry))
        except Exception:
            continue

    return result


# ─── System Event Log (all generations) ──────────────────────────────────────

def getSystemEventLog(target,auth,fromtimestamp):
    # Gen-8 uses its own Redfish SEL endpoint and entry schema — delegate entirely
    # to get_all_sel_logs_gen8() which handles pagination and timestamp filtering.
    if state_manager.state.generation == 8:
        return get_all_sel_logs_gen8(target, auth, fromtimestamp)

    return_data = []
    if check_redfish_api(target,auth): 
        gen = str(state_manager.state.generation)
        event_cnt = 0
        show_log_cnt = 500
        
        # 1. Get total count of logs to calculate skip offset
        url_count = f"{constants.LOG_FETCH_API[gen]}/?$top=1"
        response = redfish_get_request(url_count, bmc_ip=target, auth=auth, custom_timeout=10)
        try:
            if response and response.status_code == 200:
                event_cnt = int(response.json().get("Members@odata.count", 0))
        except (ValueError, KeyError, AttributeError):
            pass

        # 2. Fetch the latest batch (typically 500 entries)
        if event_cnt > show_log_cnt:
            url = f"{constants.LOG_FETCH_API[gen]}/?$skip={event_cnt - show_log_cnt}&$top={show_log_cnt}"
        else:
            url = f"{constants.LOG_FETCH_API[gen]}/?$top={show_log_cnt}"
            
        # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}] {gen} Platform, fetching from: {url}")
        response = redfish_get_request(url, bmc_ip=target, auth=auth, custom_timeout=10)
        try:
            data = response.json().get("Members", [])
            if data and len(data) > 0:
                for item in data:
                    try:
                        # Full ISO8601 parsing handles timezone (+00:00) correctly
                        # created_str = item["Created"].replace('Z', '+00:00')
                        # event_time = int(datetime.fromisoformat(created_str).timestamp())
                        event_time = int(datetime.fromisoformat(item["Created"][:19]).timestamp())
                        if event_time > fromtimestamp:      
                            return_data.append(item) 
                    except (ValueError, KeyError):
                        continue
        except Exception as e:
            print("Get Event Log Fail !!")    
    # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}] Send Event Log {len(return_data)} !!")
    # print(f"{return_data}")
    return return_data

def _resolve_event_gen() -> str:
    """Return the effective gen key for EventLogPrefix / LOG_FETCH_API.
    
    If the hardware is gen-7 but the Redfish firmware is older than 1.17.0,
    the SEL message format still matches the gen-6 prefix, so fall back to '6'.
    """
    gen = str(state_manager.state.generation)
    if gen == "7":
        ver = state_manager.state.redfish_version  # e.g. '1.9.0' or None
        if ver:
            try:
                parts = [int(x) for x in ver.split(".")]
                if parts < [1, 17, 0]:
                    gen = "6"  # older firmware uses gen-6 SEL format
            except ValueError:
                pass  # unparseable version — keep gen=7
    return gen

def filter_custom_event(data, target=None, auth=None):
    gen = _resolve_event_gen()
    prefix = constants.EventLogPrefix[gen]
    filtered = []

    for item in data:
        message = item.get("Message", "")
        if "SEL Entry Added" not in message:
            continue

        msg_parts = message.split(":")
        if len(msg_parts) < 2:
            continue

        payload = msg_parts[-1].strip()
        if not payload.startswith(prefix):
            continue

        # For Gen-7 with newer firmware, raw markers may be in AdditionalDataURI
        # We fetch it now so main.py doesn't have to worry about connectivity.
        data_uri = item.get("AdditionalDataURI")
        if gen == "7" and data_uri and target and auth:
            try:
                url = f"https://{target}{data_uri}"
                # print(f"{item.get('Id', '')}: {url}")
                # resp = requests.get(url, headers=auth, verify=False, timeout=5)
                resp = redfish_get_request(url, bmc_ip=target, auth=auth)
                # print(f"{resp.status_code}")
                # print(f"{resp.json()}")
                if resp.status_code == 200:
                    sensor_data = resp.json().get("SENSOR_DATA")
                    if sensor_data:
                        item["SENSOR_DATA"] = sensor_data
            except Exception as e:
                print(f"Get Sensor Data Fail !! {e}")
            #    pass  # Fail gracefully if URI is unreachable

        filtered.append(item)

    return filtered
def filter_message_event(data,search_for):
    return [
        item for item in data
        if search_for in item.get("Message", "")
    ]
def decode_event(data):
    gen = _resolve_event_gen()
    prefix = constants.EventLogPrefix[gen]
    export_string = ""
    if data.startswith(prefix):
        suffix = data[len(prefix):]  # get "010000"
        status_code = suffix[0:2]
        
        # Lookup each value in its dict
        status = constants.EventLogMessage.get(status_code, f"UnknownStatus({status_code})")
        export_string = f"{status}"
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

