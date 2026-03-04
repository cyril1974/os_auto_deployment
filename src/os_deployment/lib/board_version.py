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
from .redfish import redfish_post

from time import sleep
from requests.exceptions import Timeout
from requests.exceptions import TooManyRedirects
from requests.exceptions import RequestException
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
REDFISH_SESSION = None
IMAGE_SIZE = 192


    
def get_bios_version(target,auth_string):
def get_cpld_version(target,auth_string):
def get_rot_version(target,auth_string):    

def generate_utility_package():
    # Define paths
    current_file = Path(__file__)
    lib_dir = current_file.parent
    utility_dir = lib_dir / "uefi_utility"
    zip_path = lib_dir / "uefi_utility.zip"

    if not utility_dir.exists() or not utility_dir.is_dir():
        raise FileNotFoundError(f"Directory '{utility_dir}' does not exist.")

    # Create or overwrite the zip file
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(utility_dir):
                for file in files:
                    file_path = Path(root) / file
                    # Add files without "uefi_utility/" prefix
                    arcname = file_path.relative_to(utility_dir)
                    zipf.write(file_path, arcname=arcname)
    except Exception as e:
        print(f"Utility Package Generate FAIL !! {e}")
        return False

    # print(f"Utility Package Generated: {zip_path}")
    return True
    
    


def unmount_ivm(target,auth,ignore_error=False, add_delay=True):
    # Umount Internal Vmedia
    print("##### Umount Previous Image .....",end="")
    body = {}
    headers = {
        "Accept": "application/json",
        'Content-Type': 'application/json'    
    }
    cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.UmountImage'
    response = redfish_post(target,auth,cmd, dataset=body, headers=headers,err_log=False,retry=5)
    # print(f"{response}")
    if not ignore_error and response == 'error':
        utils.redfish_specific_error(
            "Failed to unmount internal virtual media", 'ERedfishResponse')
        print("Fail")
    print("Success")
    if add_delay:
        sleep(1)
    return True

def delete_ivm(target,auth,ignore_error=False, add_delay=True):
    # Delete Internal Vmedia
    print("##### Delete Previosu Image .....",end="")
    body = {}
    body = {}
    headers = {
        "Accept": "application/json",
        'Content-Type': 'application/json'    
    }
    cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.DeleteImage'
    response = redfish_post(target,auth,cmd, dataset=body, headers=headers,err_log=False)
    # print(f"{response}")
    if not ignore_error and response == 'error':
        utils.redfish_specific_error(
            "Failed to delete internal virtual media", 'ERedfishResponse')
        print("Fail")
    print("Success")
    if add_delay:
        sleep(1)
    return True

def create_ivm(target,auth,size_mb=150):
    # Create
    print("##### Create New Image .....",end="")
    cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.CreateImage'
    body = json.dumps({"ImageSize": size_mb})
    headers = {
        "Accept": "application/json",
        'Content-Type': 'application/json'    
    }
    response = redfish_post(target,auth,cmd, dataset=body, headers=headers,err_log=False)
    # print(f"{response}")
    if response == 'error':
        utils.redfish_specific_error(
            "Failed to create internal virtual media", 'ERedfishResponse')
        print("Fail")
    print("Success")
    # Required on Purley to prevent upload failures
    # print(f"Creating IVM of size {size_mb} MB\n")
    sleep(1)
    return True

def upload_files_ivm(target,auth,path):
    # PutFile
    print("##### Put Utility Files to Image .....",end="")
    cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.PutFileToImage'
    headers = {}
    files = { 'filename': (os.path.basename(path), open(path, 'rb'), 'application/zip') }
    # response = None
    # Fails Intermittently
    for _ in range(4):
        response = redfish_post(target,auth,cmd, files=files,headers=headers)
        # print(f"{response}")
        if response != 'error':
            break
        sleep(1)
    
    if response is not None and response == 'error':
        utils.redfish_specific_error("\nFailed to upload files to internal virtual media", 'ERedfishResponse')
        print("Fail")
        return False
    print("Success")
    sleep(1)
    return True

def mount_ivm(target,auth,ignore_error=False):
    # Mount
    print("##### Mount Image .....",end="")
    cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.MountImage'
    body = {}
    response = redfish_post(target,auth,cmd, dataset=body)
    # print(f"{response}")
    if response == 'error':
        if ignore_error:
            return False
        utils.redfish_specific_error(
            "Failed to mount internal virtual media", 'ERedfishResponse')
        print("Fail")
    print("Success")    
    sleep(1)
    return True

# def download_files(target,auth,file_path)

def mount_utility(target:str,config:dict):
    auth_string = auth.get_auth_header(target,config)
    if generate_utility_package():
        # UnMount Image
        unmount_ivm(target,auth_string,ignore_error=True, add_delay=True)
        # Delete Image
        delete_ivm(target,auth_string,ignore_error=True, add_delay=True)
        try:
            # Create Image
            create_ivm(target,auth_string,size_mb=IMAGE_SIZE)
            try:
                # PUT File to Image
                current_dir = os.path.dirname(__file__)
                zip_path = os.path.join(current_dir, 'uefi_utility.zip')
                upload_files_ivm(target,auth_string,zip_path)
                try:
                    # Mount Image
                    mount_ivm(target,auth_string,ignore_error=False)
                except Exception as e:
                    print(f"Mount Image Fail !! {e}")
                    return False        
            except Exception as e:
                print(f"Put Utility Zip to Image Fail !! {e}")    
                return False   
            
        except Exception as e:
            print(f"Create Utility Image Fail !! {e}")
            return False
        
        # print("Create Utility Image and Mount Success")
        return True
    else:
        return False  
