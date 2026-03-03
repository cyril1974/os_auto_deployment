#!/usr/bin/env python3
import argparse
import pathlib
import sys
import tomllib
import json
import subprocess
from datetime import datetime
from time import sleep

import os_deployment.lib.state_manager as state_manager
from .lib import config
from .lib import nfs
from .lib import remote_mount
from .lib import reboot
# from .lib import utility_mount
from .lib import utils
from .lib import auth
# from .lib import constants
from .lib import generation


LOG_SAVE_LOCAL_PATH = ""
def get_version():
    """Read version from pyproject.toml or fallback to _version.py"""
    try:
        # Try to import from _version.py first (works with PyInstaller)
        from os_deployment._version import __version__
        return __version__
    except ImportError:
        pass
    
    try:
        # Fallback: read from pyproject.toml (works in development)
        project_root = pathlib.Path(__file__).parent.parent.parent
        pyproject_path = project_root / "pyproject.toml"
        
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                pyproject_data = tomllib.load(f)
                return pyproject_data.get("tool", {}).get("poetry", {}).get("version", "unknown")
    except Exception:
        pass
    
    return "unknown"


def get_version_info():
    """Get formatted version information with MiTAC branding"""
    version = get_version()
    return (
        f"MiTAC CUP Deploy Tool -- {version}\n"
        f"Copyright (c) 2025 MiTAC Computing Technology Corporation\n"
        f"All rights reserved."
    )


def main():
    parser = argparse.ArgumentParser(
        description="1) Get ISO File ISO repository according to user specific\n"
                    "2) Generate custom autoinstall ISO via executing autoinstall script\n"
                    "3) Deploy ISO to NFS Server\n"
                    "4) Mount ISO to target server\n"
                    "5) Set boot option to CD\n"
                    "6) Reboot target server"
    )
    parser.add_argument(
        "-V", "--version", action="version",
        version=get_version_info(),
        help="Show version information"
    )
    parser.add_argument("-B","--bmcip", required=True, help="BMC IP")
    parser.add_argument("-BU","--bmcuser",help="BMC Login User")
    parser.add_argument("-BP","--bmcpasswd",help="BMC Login Password")
    parser.add_argument("-N","--nfsip", required=True, help="NFS IP (NFS information should be defined in config.json)")
    parser.add_argument("-O","--os", required=True, help="Specific OS ISO Name (Support Ubuntu Only)")
    parser.add_argument("-OU","--osuser", default="admin",help="Specific OS Login User")
    parser.add_argument("-OP","--ospasswd", default="ubuntu",help="Specific OS Login Password")
    parser.add_argument(
        "-c", "--config", default="config.json",
        help="Path to JSON config file (default: config.json)"
    )
    parser.add_argument(
        "--no-reboot", action="store_true",
        help="Skip rebooting the target server"
    )
    args = parser.parse_args()
    
    bmcip = args.bmcip
    bmcuser = args.bmcuser
    bmcpasswd = args.bmcpasswd
    nfsip = args.nfsip
    os = args.os
    osuser = args.osuser
    ospasswd = args.ospasswd
    config_path = args.config
    no_reboot = args.no_reboot
    if no_reboot:
        print("Otion no-reboot is set !!")
    ## Load Config ##
    try:
        # Ensure args.config is a string
        if not isinstance(args.config, str):
            raise ValueError("The provided config path is not a string.")
        config_path = pathlib.Path(args.config)
        # Check if the path exists
        if not config_path.exists():
            raise FileNotFoundError(f"The configuration file does not exist: {args.config}")
        # Resolve the absolute path
        absolute_config_path = config_path.resolve()
    except ValueError as ve:
        sys.exit(f"Invalid configuration path: {ve}")
    except FileNotFoundError as fnfe:
        sys.exit(f"Configuration File ({args.config}) not found: {fnfe}")
    except Exception as e:
        sys.exit(f"An error occurred: {e}")
    
    
   
    # Convert Path to string for Cython compatibility (Cython enforces type annotations)
    config_json = config.load_config(str(absolute_config_path))
    if bmcip and bmcuser and bmcpasswd:
        # Ensure auth section exists
        config_json.setdefault("auth", {})
        # Add BMC credentials if not already present
        config_json["auth"][bmcip] = {"username": bmcuser, "password": bmcpasswd}
        # Write updated config_json back to file
        with open(absolute_config_path, 'w') as f:
            json.dump(config_json, f, indent=4)
        config_json = config.load_config(str(absolute_config_path))    
    elif bmcip and bmcip not in config_json.get("auth", {}):
        sys.exit(f"BMC IP ({bmcip}) configuration not found in config.json")
    print(f"[{utils.formatted_time()}] Loading config.json .... OK")
    # print(config_json)
    
    # try:
    #     print(f"######## Mount Necessary Utility to BMC ########") 
    #     utility_mount.mount_utility(target,config_json)
    # except Exception as e:
    #     sys.exit(f"Mount Utility Image FAIL !! Exit")  
    # 
    # sys.exit("DEBUG!!!")
    
    # Validate BMC Authentication
    auth_string = auth.get_auth_header(bmcip, config_json)
    print(f"[{utils.formatted_time()}] Validating BMC authentication ({bmcip}) ....", end="")
    auth_result = utils.check_auth_valid(bmcip, auth_string)
    if auth_result["status"] == "ok":
        print("OK")
    else:
        print("FAIL")
        sys.exit(f"BMC Auth Validation Failed: {auth_result['message']} (Please check your parameter or config.json)")

    # Generate Custom ISO
    print(f"[{utils.formatted_time()}] Generating custom autoinstall ISO...")
    print(f"OS: {os}, User: {osuser}")
    
    # Path to the build script
    script_dir = pathlib.Path(__file__).parent.parent.parent / "autoinstall"
    build_script = script_dir / "build-ubuntu-autoinstall-iso.sh"
    
    if not build_script.exists():
        sys.exit(f"Build script not found: {build_script}")
    
    # Execute the build script with sudo (requires root for apt and ISO operations)
    try:
        print(f"[{utils.formatted_time()}] Executing: sudo {build_script} {os} {osuser} ****")
        result = subprocess.run(
            ["sudo", str(build_script), os, osuser, ospasswd],
            cwd=str(script_dir),
            capture_output=True,
            text=True,
            check=True
        )
        
        # Print script output
        if result.stdout:
            print(result.stdout)
        
        # Print stderr if any (warnings, etc.)
        if result.stderr:
            print(f"Script warnings/errors:\n{result.stderr}", file=sys.stderr)
        
        # Extract the generated ISO path from the output
        # Looking for line: "[*] Done. Autoinstall ISO created at: ./output_custom_iso/..."
        iso_path = None
        for line in result.stdout.split('\n'):
            if "Autoinstall ISO created at:" in line:
                iso_path = line.split("Autoinstall ISO created at:")[-1].strip()
                break
        
        if not iso_path:
            print("ERROR: Failed to extract ISO path from build script output")
            print("Script output was:")
            print(result.stdout)
            sys.exit("Failed to extract ISO path from build script output")
        
        # Convert relative path to absolute
        iso = str((script_dir / iso_path).resolve())
        print(f"[{utils.formatted_time()}] Custom ISO generated: {iso}")
        
    except subprocess.CalledProcessError as e:
        print(f"\n{'='*60}")
        print(f"BUILD SCRIPT FAILED")
        print(f"{'='*60}")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print(f"\nStdout:\n{e.stdout}")
        if e.stderr:
            print(f"\nStderr:\n{e.stderr}")
        print(f"{'='*60}")
        sys.exit(f"Failed to generate custom autoinstall ISO (exit code: {e.returncode})")
    except Exception as e:
        sys.exit(f"Error executing build script: {e}")
    
    

    ## Deploy ISO to NFS Server ##
           
    if "ip" in config_json.get("nfs_server", {}):
        nfs_ip = config_json["nfs_server"]["ip"]
        nfs_path = config_json["nfs_server"]["path"]
        print(f"[{utils.formatted_time()}] Deploy {pathlib.Path(iso).name} to NFS Server ({nfs_ip}) .....",end="")
        
        # Write updated config_json back to file
        with open(absolute_config_path, 'w') as f:
            json.dump(config_json, f, indent=4)
        
        # print(f"Start to deploy {iso} to NFS Server ({nfs_ip}) .....")
        exports_list = nfs.get_nfs_exports(nfs_ip)
        mount_path = nfs.drop_file_to_nfs(nfs_ip,nfs_path,pathlib.Path(iso))
        # sys.exit(f"Deploy to NFS success...{mount_path}")   
    else:
        print("FAIL")
        sys.exit("Get NFS Server Config Fail , Please configure NFS Server...")    
    print("OK")
    
    # Get Generation

    gen = generation.get_generation_redfish(bmcip,auth_string)
    state_manager.state.generation = gen[1]
    state_manager.state.product_model = gen[0]
    
    print(f"[{utils.formatted_time()}] Detect Product Generation {gen}.....")
    
    
    # Check Virtual Media Permission
    print(f"[{utils.formatted_time()}] Check Virtual Media Permission .....",end="")
    vm_permission = utils.get_virtual_media_permission(bmcip,auth_string)
    #print(vm_permission)
    
    
    if vm_permission:
        try:
            enable_outband = all(vm_permission.get('outband', {}).values())
            enable_inband = all(vm_permission.get('inband', {}).values())
            if enable_outband and enable_inband:
                print("OK")
            else:
                print("Fail")
                if not enable_outband:
                    print("Outband Virtual Media Not Enable...")
                    print(vm_permission["outband"])
                if not enable_inband:
                    print("Inband Virtual Media Not Enable...")
                    print(vm_permission["inband"])   
                sys.exit("No Virtual Media Permission , Please enter BMC to configure Virtual Media Permission ...Abort")           
        except Exception as e:
            print("FAIL")
            print(f"Get Virtual Media Permission Fail...{e}")
            sys.exit("Cannot Determine Virtual Media Permission , Please enter to confirm Virtual Media Permission ...Abort")     
    else:
        print("FAIL")
        print("Get Virtual Media Permission Fail...")    
        sys.exit("Cannot Determine Virtual Media Permission , Please enter BMC confirm Virtual Media Permission ...Abort")
    
    
    LOG_SAVE_LOCAL_PATH = f"./collected_log/{bmcip}/{datetime.now().strftime('%Y%m%d_%H%M%S')}/"
    ## Mount Image ##
    print(f"[{utils.formatted_time()}] Remote Mount Image ..... ")
    print(f"Remote Image : {mount_path}")
    print(f"Target Server : {bmcip}")
    
    use_endpoint = ""
    try:
        # print(f"Start to Remote Mount {mount_path} to Target Server ({target}) .....")
        use_endpoint = remote_mount.mount_image(mount_path,bmcip,config_json)
        if use_endpoint is None or use_endpoint == "":
            raise Exception("Remote Mount Image FAIL !! (No Mount Point is available)")
        else:
            print(f"Mount Point : {use_endpoint}")
            print("Mount Image Successful !!")
            # print(f"Remote Mount {mount_path} to Target Server ({target}) OK .....")       
    except Exception as e:
        print(f"FAIL {e}")
        sys.exit(f"Remote Mount Image {mount_path} FAIL !! Exit")    
    
    sys.exit("DEBUG!!!")
       
    ## Reboot to CD-ROM ##
    from_timestamp  = 0 
    if not no_reboot:
        print(f"[{utils.formatted_time()}] Ready to Reboot Target Server ({bmcip}) .....")
        #try:
        from_datetime = reboot.reboot_cdrom(target,config_json)
        print(f"[{utils.formatted_time()}] Return TimeStamp after reboot {from_datetime}") 
        if from_datetime is None:
            raise RuntimeError("Reboot Server Fail (TimeOut)")
        else:
            from_timestamp = int(datetime.fromisoformat(from_datetime).timestamp())
        #except Exception as e:
        #    sys.exit(f"Processs Aborted !! Reboot Server FAIL...{e}")
    
    ## Monitor BMC FW update process and receive stauts ##
    is_complete = False
    
    if from_timestamp is None or int(from_timestamp) <= 0:
        from_timestamp = current_timestamp = int(utils.getTargetBMCDateTime(target,auth_string)["data"]["timestamp"])
    stop_timestamp = from_timestamp + constants.PROCESS_TIMEOUT
    current_timestamp = from_timestamp
    # print(f"From TimeStamp : {from_timestamp} , Date Time String {datetime.fromtimestamp(from_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    # print(f"Stop TimeStamp : {stop_timestamp} , Date Time String {datetime.fromtimestamp(stop_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    loop = 0
    sup_updating = False
    bios_updating = bmc_updating = rot_updating = cpld_updating = False
    cpld_log_got = False
    sup_updating_reboot = False
    last_log_id = ""
    reboot.set_boot_cdrom(target,auth_string)
    print(f"[{utils.formatted_time()}] Get Event Log From Timestamp {datetime.fromtimestamp(from_timestamp).isoformat()} ({from_timestamp})")
    # sys.exit("DEBUG")
    while not is_complete and current_timestamp < stop_timestamp:
        # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}] Check Redfish API...")
        if utils.check_redfish_api(target,auth_string): 
            # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}]Redfish API is available")
            if utils.reboot_detect(target,auth_string,current_timestamp):
               
                bmcDateTime = utils.getTargetBMCDateTime(target,auth_string)
                waitfromtime = int(bmcDateTime["data"]["timestamp"])
                waitfromtimestring = bmcDateTime["data"]["string"]
                print(f"[{waitfromtimestring}] Server Automatically Reboot is detected , wait for reboot complete...")
                returnData = utils.wait_for_reboot(target,auth_string,waitfromtime)
                current_timestamp = int(datetime.fromisoformat(returnData["booted_time"]).timestamp())
                mount_loss = False
                if cpld_updating:
                    support_category = constants.VERSION_GET_API.keys()
                    updated_ver_info = {cate: utils.get_version(target, auth_string, cate) for cate in support_category}
                    utils.print_message(target,auth_string,"Print Updated Versions")
                    print("Updated Version :")
                    print(utils.print_board_version(updated_ver_info))
                data_check_inband = utils.check_mount_status(target,auth_string,constants.INBAND_MEDIA,allData=True)
                if data_check_inband  and "Inserted" in data_check_inband and data_check_inband["Inserted"]==False:
                    mount_loss = True
                    size = data_check_inband["Oem"]["OpenBMC"]["ImageSize"]
                    print("Utility Mount is Loss !!")
                    print(f"ImageSize : {size}")
                    print(f"Mount Image Again...",end="")
                    if int(size) > 128:
                        print("(Mount Only !!)")
                        utility_mount.mount_ivm(target,auth_string)
                    else:
                        print("(Create Image and Mount !!)")
                        if cpld_updating:
                            utility_mount.mount_utility(target,config_json,option="sup_updated") 
                        elif  bios_updating:
                            utility_mount.mount_utility(target,config_json,option="bios_updated")   
                        else:
                            utility_mount.mount_utility(target,config_json)    
                
                cpld_updating = False if cpld_updating else cpld_updating
                bios_updating = False if bios_updating else bios_updating
                bmc_updating = False if bmc_updating else bmc_updating
                rot_updating = False if rot_updating else rot_updating
                if utils.check_mount_status(target,auth_string,use_endpoint) == False:
                    mount_loss = True
                    print("Image Mount is Loss !!")
                    print(f"Mount Image Again...")
                    # utils.umount_media(target,auth_string,use_endpoint)
                    remote_mount.mount_image(mount_path,target,config_json)
               
                if mount_loss:
                    reboot_datetime = reboot.reboot_cdrom(target,config_json)     
                else:
                    reboot.set_boot_cdrom(target,auth_string)
                    reboot_datetime = utils.getTargetBMCDateTime(target,auth_string)["data"]["string"]
                current_timestamp = int(datetime.fromisoformat(reboot_datetime).timestamp())    
            
            result = utils.getSystemEventLog(target,auth_string,from_timestamp)
            export = utils.filter_custom_event(result)
            # print(f"Get {len(result)} Event Log from {from_timestamp}")
            # print(f"Export {len(export)} Event Log from {from_timestamp}")
            # print(f"{export}")
            check_power_restore = utils.filter_message_event(result,constants.POWER_RESTORE_EVENT)
            if sup_updating and len(check_power_restore) > 0:
                eventTime = check_power_restore[0]["Created"][:19]
                eventString = "Server is Reboot OK ... Board Firmware Update Complete"
                sup_updating = False
            currentID =last_log_id 
            for item in export:
                # if int(item["Id"]) >last_log_id:
                if item["Id"] >last_log_id:
                    eventTime = item["Created"][:19]
                    eventMessage = str(item["Message"]).split(":")[1].strip()
                    eventString = utils.decode_event(eventMessage)
                    #if eventMessage[-6:] == "00000A" and use_enquit
                    # dpoint != "":
                    if eventMessage[-6:] == "00001C":
                        cpld_updating = True
                    if eventMessage[-6:] == "00001D":        
                        cpld_updating = False
                    if eventMessage[-6:] == "00000C":
                        sup_updating = True
                        utils.print_message(target,auth_string,"Print Current Versions")
                        support_category = constants.VERSION_GET_API.keys()
                        print("Current Version :")
                        current_ver_info = {cate: utils.get_version(target, auth_string, cate) for cate in support_category}
                        print(utils.print_board_version(current_ver_info))
                    if eventMessage[-6:] in ["000013","000014"]:
                        sup_updating = False     
                    if  eventMessage[-6:] in ["000000","FFFFFF","000020","000021"]:  # If message is Abort or Complete , End process
                        print(f"[{utils.formatted_time()}] Collecting Log and dumping to ({constants.DEFAULT_LOG_PATH})....")
                        result = utils.log_collect(target,auth_string,constants.DEFAULT_LOG_PATH,local_path=LOG_SAVE_LOCAL_PATH)
                        sys.exit("DEBUG!!!")
                        # print("Successful!!") if result else print("Fail!!")
                        utils.print_message(target,auth_string,f"Umount Virtual Media : {use_endpoint}")
                        utils.umount_media(target,auth_string,use_endpoint)
                        reboot_datetime = reboot.reboot_cdrom(target,config_json)  
                        
                        is_complete = True  
                    print(f"[{eventTime}] {eventString}")
                currentID = item["Id"]
                if cpld_updating and not cpld_log_got:
                    utils.print_message(target,auth_string,"Collect Logs Before CPLD update force reboot...")
                    result = utils.log_collect(target,auth_string,constants.DEFAULT_LOG_PATH,local_path=LOG_SAVE_LOCAL_PATH)
                    cpld_log_got = result
                    
            last_log_id = currentID   
        else:
            if sup_updating:
               sup_updating_reboot = True  
            current_time_string = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            print(f"[{current_time_string}] Server is Unavailable ... (Unable to connect to BMC)")    
            sleep(5)        
            
    
if __name__ == "__main__":
    main()    