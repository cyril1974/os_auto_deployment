import json
import requests
from pathlib import Path
import sys
import urllib3
import urllib3.exceptions
import os
import zipfile

from . import auth
from . import constants
from . import utils

from time import sleep
from requests.exceptions import Timeout
from requests.exceptions import TooManyRedirects
from requests.exceptions import RequestException
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
REDFISH_SESSION = None
IMAGE_SIZE = 192

def redfish_post(target,auth, cmd, dataset=None, retry=0, files=None, headers=None, err_log=True, pass_through=False, timeout=constants.REDFISH_TIMEOUT):
    global REDFISH_SESSION
    url =  f"https://{target}{cmd}" 
    try:
        if REDFISH_SESSION is None:
            REDFISH_SESSION = requests.Session()
    except requests.exceptions.RequestException:
        print("Redfish Session Error.")
    response = None
    if  isinstance(headers, dict):
        headers["Authorization"] = auth
    else:
        headers = {
            "Accept": "application/json",
            "Authorization": auth
        }
            
    connect_err_retry = 5
    while retry >= 0:
        try:
            utils.wait_for_bmc(target,auth , 180, wait_time=1)
            redfish_cmd = REDFISH_SESSION.post 
            response = redfish_cmd(url, files=files, headers=headers,
                                   verify=False, timeout=timeout, data=dataset)
        except ConnectionError:
            if connect_err_retry > 0:
                print("Connection Error Occcurred\n")
                # MsgCtl("Connection Error Occcurred\n", False,"print_msg_2", "direct_log_dbg")
                connect_err_retry -= 1
                REDFISH_SESSION.close()
                REDFISH_SESSION = requests.Session()
                sleep(10)
                continue
            retry = utils.redfish_handle_exceptions("Redfish connection error.", 'ENoConnect', retry)
            continue
        except Timeout as e:
            print(f"Exception: {e}\n")
            # MsgCtl("Exception: {}\n".format(e), False,"print_msg_2", "direct_log_dbg")
            retry = utils.redfish_handle_exceptions("Redfish request Timed out.", 'ETimedOut', retry)
            continue
        except TooManyRedirects as e:
            print(f"Exception: {e}\n")
            # MsgCtl("Exception: {}\n".format(e), False,"print_msg_2", "direct_log_dbg")
            retry = utils.redfish_handle_exceptions("Redfish Redirection error.", 'ERedfishRedirect', retry)
            continue
        except RequestException as e:
            print("Exception: {e}\n")
            # MsgCtl("Exception: {}\n".format(e), False,"print_msg_2", "direct_log_dbg")
            retry = utils.redfish_handle_exceptions("Redfish Unexpected Error: " + str(e), 'ERedfishUnexpected', retry)
            continue
        if response.status_code > 300 and err_log:
            utils.MsgCtl("Request URL: {}\n".format(cmd), False,"print_msg_2", "direct_log_dbg")
            utils.MsgCtl("Response Code: {}\n".format(response.status_code), False,"print_msg_2", "direct_log_dbg")
            utils.MsgCtl("Response Content: {}\n".format(response.content.decode('ascii', errors='ignore')), False,"print_msg_2", "direct_log_dbg")
        if pass_through and retry <= 0:
            return response
        if response.status_code == 400 and "ResourceInUse" in response.text:
            return "ResourceInUse"
        if response.status_code not in [200, 202, 204]:
            if retry == 0:
                if response.status_code == 404:
                    utils.redfish_specific_error("Redfish schema error", "ERedfishSchema", url, response.text)
                return 'error'
            else:
                sleep(3)
        else:
            break
        retry -= 1
    return response

def redfish(target,auth, cmd, dataset=None, retry=0, files=None, headers=None, err_log=True, pass_through=False, timeout=constants.REDFISH_TIMEOUT):
    global REDFISH_SESSION
    url =  f"https://{target}{cmd}" 
    try:
        if REDFISH_SESSION is None:
            REDFISH_SESSION = requests.Session()
    except requests.exceptions.RequestException:
        print("Redfish Session Error.")
    response = None
    if  isinstance(headers, dict):
        headers["Authorization"] = auth
    else:
        headers = {
            "Accept": "application/json",
            "Authorization": auth
        }
            
    connect_err_retry = 5
    while retry >= 0:
        try:
            utils.wait_for_bmc(target,auth , 180, wait_time=1)
            redfish_cmd = REDFISH_SESSION.post 
            response = redfish_cmd(url, files=files, headers=headers,
                                   verify=False, timeout=timeout, data=dataset)
        except ConnectionError:
            if connect_err_retry > 0:
                print("Connection Error Occcurred\n")
                # MsgCtl("Connection Error Occcurred\n", False,"print_msg_2", "direct_log_dbg")
                connect_err_retry -= 1
                REDFISH_SESSION.close()
                REDFISH_SESSION = requests.Session()
                sleep(10)
                continue
            retry = utils.redfish_handle_exceptions("Redfish connection error.", 'ENoConnect', retry)
            continue
        except Timeout as e:
            print(f"Exception: {e}\n")
            # MsgCtl("Exception: {}\n".format(e), False,"print_msg_2", "direct_log_dbg")
            retry = utils.redfish_handle_exceptions("Redfish request Timed out.", 'ETimedOut', retry)
            continue
        except TooManyRedirects as e:
            print(f"Exception: {e}\n")
            # MsgCtl("Exception: {}\n".format(e), False,"print_msg_2", "direct_log_dbg")
            retry = utils.redfish_handle_exceptions("Redfish Redirection error.", 'ERedfishRedirect', retry)
            continue
        except RequestException as e:
            print("Exception: {e}\n")
            # MsgCtl("Exception: {}\n".format(e), False,"print_msg_2", "direct_log_dbg")
            retry = utils.redfish_handle_exceptions("Redfish Unexpected Error: " + str(e), 'ERedfishUnexpected', retry)
            continue
        if response.status_code > 300 and err_log:
            utils.MsgCtl("Request URL: {}\n".format(cmd), False,"print_msg_2", "direct_log_dbg")
            utils.MsgCtl("Response Code: {}\n".format(response.status_code), False,"print_msg_2", "direct_log_dbg")
            utils.MsgCtl("Response Content: {}\n".format(response.content.decode('ascii', errors='ignore')), False,"print_msg_2", "direct_log_dbg")
        if pass_through and retry <= 0:
            return response
        if response.status_code == 400 and "ResourceInUse" in response.text:
            return "ResourceInUse"
        if response.status_code not in [200, 202, 204]:
            if retry == 0:
                if response.status_code == 404:
                    utils.redfish_specific_error("Redfish schema error", "ERedfishSchema", url, response.text)
                return 'error'
            else:
                sleep(3)
        else:
            break
        retry -= 1
    return response