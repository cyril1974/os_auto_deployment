import json
import requests
from pathlib import Path
import sys
import urllib3
import urllib3.exceptions
import os
import zipfile
from io import BytesIO

from . import auth
from . import constants
from . import utils
from .redfish import redfish_post

import os_deployment.lib.state_manager as state_manager
from time import sleep
from requests.exceptions import Timeout
from requests.exceptions import TooManyRedirects
from requests.exceptions import RequestException
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
REDFISH_SESSION = None
IMAGE_SIZE = {"7":192 , "6":128}

def generate_utility_package(option=""):
    # Define paths
    current_file = Path(__file__)
    lib_dir = current_file.parent
    utility_dir = lib_dir / "uefi_utility"
    zip_path = lib_dir / "uefi_utility.zip"

    if not utility_dir.exists() or not utility_dir.is_dir():
        raise FileNotFoundError(f"Directory '{utility_dir}' does not exist.")

    # Create or overwrite the zip file
    try: 
        skip_dir_names = {"backup", "Backup"}  # add other variants if needed
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(utility_dir):
                dirs[:] = [d for d in dirs if d not in skip_dir_names]
                for file in files:
                    file_path = Path(root) / file
                    # Add files without "uefi_utility/" prefix
                    arcname = file_path.relative_to(utility_dir)
                    zipf.write(file_path, arcname=arcname)
            # Add Platform description file
            platformstr = constants.PLATFROM_STRING[str(state_manager.state.generation)]
            zipf.writestr("platform_config.nsh", f"set PLATFORM {platformstr}")
            # Add SUP_updated file to root of ZIP if option is "sup_updated"
            if option == "sup_updated":
                zipf.writestr("SUP_updated", "SUP update is executed")
            elif option == "bios_updated":
                zipf.writestr("FUP/BIOS_pass.tmp", "BIOS is updating....")
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
    # cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.UmountImage'
    cmd = constants.UMOUNT_IMAGE_API[str(state_manager.state.generation)]
    # print(cmd)
    response = redfish_post(target,auth,cmd, dataset=body, headers=headers,err_log=False,retry=5)
    # print(f"{response}")
    if not ignore_error and response == 'error':
        utils.redfish_specific_error(
            "Failed to unmount internal virtual media", 'ERedfishResponse')
        print("Fail")
    print("Success")
    if add_delay:
        sleep(1)
    return False

def delete_ivm(target,auth,ignore_error=False, add_delay=True):
    # Delete Internal Vmedia
    print("##### Delete Previosu Image .....",end="")
    body = {}
    body = {}
    headers = {
        "Accept": "application/json",
        'Content-Type': 'application/json'    
    }
    # cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.DeleteImage'
    cmd = constants.DELETE_IMAGE_API[str(state_manager.state.generation)]
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
    # cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.CreateImage'
    cmd = constants.CREATE_IMAGE_API[str(state_manager.state.generation)]
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
    # cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.PutFileToImage'
    cmd = constants.PUTFILE_IMAGE_API[str(state_manager.state.generation)]
    headers = {}
    files = None
    filename = os.path.basename(path)
    ext = Path(path).suffix.lower()
    mime = {
            ".zip": "application/zip",
            ".gz":  "application/gzip",
            ".bz2": "application/x-bzip2",
            ".bz":  "application/x-bzip",
            ".tar": "application/x-tar",
    }.get(ext, "application/octet-stream")
    if state_manager.state.generation == 7:
        files = { 'filename': (os.path.basename(path), open(path, 'rb'), 'application/zip') }
    elif  state_manager.state.generation == 6:
        # print("Process Generation 6")
        with open(path, 'rb') as f:
            payload = f.read()
        headers = {"Accept": "application/json"} 
        files1 = { "file": (filename, BytesIO(payload), mime) }  # 每回合新建 BytesIO
        # files2 = { "filename": (filename, BytesIO(payload), mime) }  # 每回合新建 BytesIO
        # files3 = [(filename, BytesIO(payload), mime)]  
        #files = [
        #    ('', (os.path.basename(path), open(path, 'rb'), 'application/zip'))]   
    # response = None
    # Fails Intermittently
    for _ in range(4):
        if state_manager.state.generation == 7:
            response = redfish_post(target,auth,cmd, files=files,headers=headers)
        elif  state_manager.state.generation == 6:
            response = redfish_post(target,auth,cmd, files=files1,headers=headers,timeout=constants.REDFISH_TIMEOUT)
            # response = redfish_post(target,auth,cmd, files=files2,headers=headers,timeout=constants.REDFISH_TIMEOUT) 
            # response = redfish_post(target,auth,cmd, files=files3,headers=headers)       
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
    # cmd = '/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.MountImage'
    cmd = constants.MOUNT_IMAGE_API[str(state_manager.state.generation)]
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

def mount_utility(target:str,config:dict,option=""):
    auth_string = auth.get_auth_header(target,config)
    if generate_utility_package(option):
        # UnMount Image
        unmount_ivm(target,auth_string,ignore_error=True, add_delay=True)
        # Delete Image
        delete_ivm(target,auth_string,ignore_error=True, add_delay=True)
        
        """
        create_ivm(target,auth_string,size_mb=IMAGE_SIZE[str(state_manager.state.generation)])
        current_dir = os.path.dirname(__file__)
        zip_path = os.path.join(current_dir, 'uefi_utility.zip')
        print(zip_path)
        upload_files_ivm(target,auth_string,zip_path)
        """
        
        try:
            # Create Image
            create_ivm(target,auth_string,size_mb=IMAGE_SIZE[str(state_manager.state.generation)])
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
