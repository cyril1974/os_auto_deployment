#!/usr/bin/env python3
import argparse
import pathlib
import sys
import tomllib
import json
import subprocess
from datetime import datetime
from time import sleep


class _StorageAction(argparse.Action):
    """Custom action that records storage flags in argv order (first wins)."""
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        existing = getattr(namespace, '_storage_flags', [])
        existing.append((self.dest, values))
        namespace._storage_flags = existing

import os_deployment.lib.state_manager as state_manager
from .lib import config
from .lib import nfs
from .lib import remote_mount
from .lib import reboot
# from .lib import utility_mount
from .lib import utils
from .lib import auth
from .lib import constants
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
    parser.add_argument("-O","--os", required=False, default=None,
                        help="Specific OS ISO Name (Support Ubuntu Only). "
                             "Required unless --iso is provided.")
    parser.add_argument("-OU","--osuser", default="autoinstall",help="Specific OS Login User")
    parser.add_argument("-OP","--ospasswd", default="ubuntu",help="Specific OS Login Password")
    parser.add_argument(
        "-c", "--config", default="config.json",
        help="Path to JSON config file (default: config.json)"
    )
    parser.add_argument(
        "--no-reboot", action="store_true",
        help="Skip rebooting the target server"
    )
    parser.add_argument(
        "--iso", default=None,
        help="Path to a pre-built ISO file. When provided, the ISO generation "
             "step is skipped and the specified ISO is used directly for deployment."
    )
    parser.add_argument(
        "--storage-serial", default=None, dest="storage_serial",
        metavar="VALUE", action=_StorageAction,
        help="Match target disk by serial number (passed to ISO builder; disables find_disk.sh auto-detection)"
    )
    parser.add_argument(
        "--storage-model", default=None, dest="storage_model",
        metavar="VALUE", action=_StorageAction,
        help="Match target disk by model string (passed to ISO builder; disables find_disk.sh auto-detection)"
    )
    parser.add_argument(
        "--storage-size", default=None, dest="storage_size",
        metavar="VALUE", action=_StorageAction,
        help="Match target disk by size value (passed to ISO builder; disables find_disk.sh auto-detection)"
    )
    parser.add_argument(
        "--gen-by-go", action="store_true", dest="gen_by_go",
        help="Use the Go ISO builder (build-iso-go/build-iso) instead of the shell script"
    )
    args = parser.parse_args()

    # Resolve storage flag: first in argv order wins; warn about extras
    storage_flags = getattr(args, '_storage_flags', [])
    storage_flag_arg = None
    if storage_flags:
        key, value = storage_flags[0]
        flag_name = key.replace("storage_", "")   # e.g. "storage_serial" -> "serial"
        storage_flag_arg = f"--storage-{flag_name}={value}"
        for extra_key, extra_value in storage_flags[1:]:
            extra_name = extra_key.replace("storage_", "")
            print(f"[WARN] Ignoring extra storage flag: --storage-{extra_name}={extra_value} "
                  f"(only one storage match allowed)")

    bmcip = args.bmcip
    bmcuser = args.bmcuser
    bmcpasswd = args.bmcpasswd
    # nfsip = args.nfsip
    os = args.os
    osuser = args.osuser
    ospasswd = args.ospasswd
    config_path = args.config
    no_reboot = args.no_reboot
    pre_built_iso = args.iso
    gen_by_go = args.gen_by_go

    # Validate: -O is required when --iso is not provided
    if not pre_built_iso and not os:
        parser.error("-O/--os is required when --iso is not provided.")

    if no_reboot:
        print("Option no-reboot is set !!")
    if pre_built_iso:
        print(f"Option --iso is set: {pre_built_iso}")
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
    
    # Validate Redfish API
    print(f"[{utils.formatted_time()}] Validating Redfish API ({bmcip}) ....", end="")
    redfish_supported = False
    redfish_result = utils.check_redfish_api(bmcip, "")
    if redfish_result==False:
        print("Redfish API Not Supported ... (Old Platform)")
    else:
        print("Redfish API Supported")
        redfish_supported = True
    # Validate BMC Authentication
    print(f"[{utils.formatted_time()}] Validating BMC authentication ({bmcip}) ....", end="")
    if redfish_supported:
        auth_string = auth.get_auth_header(bmcip, config_json)
        auth_result = utils.check_auth_valid(bmcip, auth_string, redfish_supported)
        if auth_result["status"] == "ok":
            print("OK")
        else:
            print("FAIL")
            sys.exit(f"BMC Auth Validation Failed: {auth_result['message']} (Please check your parameter or config.json)")
    else:
        auth_query = auth.get_auth_form(bmcip, config_json)
        auth_result = utils.check_auth_valid(bmcip, auth_query, redfish_supported)
        if auth_result["status"] == "ok":
            print("OK")
            sys.exit(f"Redfish UnSupported , Login Response {auth_result['content']}")
        else:
            print("FAIL")
            sys.exit(f"BMC Auth Validation Failed: {auth_result['message']} (Please check your parameter or config.json)")
    # Generate Custom ISO or use pre-built ISO
    if pre_built_iso:
        # --iso option provided: validate and use the pre-built ISO
        iso_path = pathlib.Path(pre_built_iso)
        if not iso_path.exists():
            sys.exit(f"Pre-built ISO not found: {pre_built_iso}")
        if not iso_path.is_file():
            sys.exit(f"Pre-built ISO path is not a file: {pre_built_iso}")
        iso = str(iso_path.resolve())
        print(f"[{utils.formatted_time()}] *** Bypassing ISO generation (--iso provided) ***")
        print(f"[{utils.formatted_time()}] Using pre-built ISO: {iso}")
    else:
        # Normal flow: generate custom autoinstall ISO
        print(f"[{utils.formatted_time()}] Generating custom autoinstall ISO...")
        print(f"OS: {os}, User: {osuser}")
        
        # Resolve autoinstall/ directory.
        # When running as a Nuitka onefile binary, __file__ is inside the
        # temp extraction dir (e.g. /tmp/onefile_xxx/os_deployment/main.py)
        # and bundled data files sit two levels up at /tmp/onefile_xxx/autoinstall/.
        # When running from source, autoinstall/ is three levels up from main.py.
        if "__compiled__" in globals():
            # Nuitka compiled binary — data files extracted alongside package dir
            script_dir = pathlib.Path(__file__).parent.parent / "autoinstall"
        else:
            # Source tree
            script_dir = pathlib.Path(__file__).parent.parent.parent / "autoinstall"
        if gen_by_go:
            build_script = script_dir / "build-iso-go" / "build-iso"
            generator_label = "Go"
        else:
            build_script = script_dir / "build-ubuntu-autoinstall-iso.sh"
            generator_label = "Shell"

        if not build_script.exists():
            sys.exit(f"Build script not found: {build_script}"
                     + (" (run 'go build -o build-iso .' inside autoinstall/build-iso-go/)"
                        if gen_by_go else ""))

        # Execute the build script with sudo (requires root for apt and ISO operations)
        try:
            storage_info = f" {storage_flag_arg}" if storage_flag_arg else ""
            print(f"[{utils.formatted_time()}] Executing [{generator_label}]: sudo {build_script.name} {os} {osuser} ****{storage_info}")

            cmd = ["sudo", str(build_script), os, osuser, ospasswd]
            if storage_flag_arg:
                cmd.append(storage_flag_arg)

            # Use Popen to stream output in real-time
            process = subprocess.Popen(
                cmd,
                cwd=str(script_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            full_output = []
            # Read and print output line by line as it is generated
            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    print(line, end="")
                    full_output.append(line)
            
            process.wait()
            
            if process.returncode != 0:
                # Replicate CalledProcessError behavior for consistent error handling
                raise subprocess.CalledProcessError(
                    process.returncode,
                    cmd,
                    output="".join(full_output)
                )

            # Extract the generated ISO path from the output
            # Looking for line: "[*] Done. Autoinstall ISO created at: ./output_custom_iso/..."
            iso_path = None
            for line in full_output:
                if "Autoinstall ISO created at:" in line:
                    iso_path = line.split("Autoinstall ISO created at:")[-1].strip()
                    break
            
            if not iso_path:
                print("ERROR: Failed to extract ISO path from build script output")
                print("Script output was:")
                print("".join(full_output))
                sys.exit("Failed to extract ISO path from build script output")
            
            # Convert relative path to absolute
            iso = str((script_dir / iso_path).resolve())
            print(f"[{utils.formatted_time()}] \nCustom ISO generated:\n Path: {iso}")
            
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
        # exports_list = nfs.get_nfs_exports(nfs_ip)
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

    redfish_ver = utils.get_redfish_version(bmcip, auth_string)
    state_manager.state.redfish_version = redfish_ver
    print(f"[{utils.formatted_time()}] Redfish Version : {redfish_ver if redfish_ver else 'Unknown'}")

    
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
    
       
    ## Reboot to CD-ROM ##
    from_timestamp  = 0 
    if not no_reboot:
        print(f"[{utils.formatted_time()}] Ready to Reboot Target Server ({bmcip}) .....")
        #try:
        if gen[1]== 7:
            print(f"[{utils.formatted_time()}] Clear PostCode Log .....",end="")
            try:
                reboot.clear_postcode_log(bmcip,config_json)
                print("OK")
            except Exception as e:
                print(f"FAIL {e}")
                sys.exit(f"Clear PostCode Log FAIL !! Exit")
        from_datetime = reboot.reboot_cdrom(bmcip,config_json)
        print(f"[{utils.formatted_time()}] Load initrd and kernel  ({from_datetime}) .....") 
        if from_datetime is None:
            raise RuntimeError("Reboot Server Fail (TimeOut)")
        else:
            from_timestamp = int(datetime.fromisoformat(from_datetime).timestamp())
        #except Exception as e:
        #    sys.exit(f"Processs Aborted !! Reboot Server FAIL...{e}")
    
    ## Monitor BMC FW update process and receive stauts ##
    is_complete = False
    
    if from_timestamp is None or int(from_timestamp) <= 0:
        from_timestamp = current_timestamp = int(utils.getTargetBMCDateTime(bmcip,auth_string)["data"]["timestamp"])
    stop_timestamp = from_timestamp + constants.PROCESS_TIMEOUT
    current_timestamp = from_timestamp
    # print(f"From TimeStamp : {from_timestamp} , Date Time String {datetime.fromtimestamp(from_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    # print(f"Stop TimeStamp : {stop_timestamp} , Date Time String {datetime.fromtimestamp(stop_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    last_log_id = ""
    # reboot.set_boot_cdrom(bmcip,auth_string)
    # print(f"[{utils.formatted_time()}] Get Event Log From Timestamp {datetime.fromtimestamp(from_timestamp).isoformat()} ({from_timestamp})")
    IP = ["NA","NA","NA","NA"]
    while not is_complete and current_timestamp < stop_timestamp:
        # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}] Check Redfish API...")
        if utils.check_redfish_api(bmcip,auth_string): 
            # print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}]Redfish API is available")
            if utils.reboot_detect(bmcip,auth_string,current_timestamp):
               pass
            
            result = utils.getSystemEventLog(bmcip,auth_string,from_timestamp)
            export = utils.filter_custom_event(result, bmcip, auth_string)
            # print(f"Get {len(result)} Event Log from {from_timestamp}")
            # print(f"Export {len(export)} Event Log from {from_timestamp}")
            # print(f"{export}")
            # check_power_restore = utils.filter_message_event(result,constants.POWER_RESTORE_EVENT)
            currentID =last_log_id 
            # event_debug_message = f"(Event : {eventMessage})"
            event_debug_message = ""
            for item in export:
                # if int(item["Id"]) >last_log_id:
                if item["Id"] >last_log_id:
                    eventTime = item["Created"][:19]
                    eventMessage_raw = str(item["Message"]).split(":")[-1].strip()
                    # If gen 7, we might have SENSOR_DATA from AdditionalDataURI
                    if "SENSOR_DATA" in item:
                        # Concatenate full 6-character payload (Marker + 2 Bytes) to ensure indexing works
                        # eventMessage_raw typically ends with the forensic prefix
                        eventMessage = eventMessage_raw + item["SENSOR_DATA"]
                    else:
                        eventMessage = eventMessage_raw

                    eventString = utils.decode_event(eventMessage)
                    #if eventMessage[-6:] == "00000A" and use_enquit
                    # dpoint != "":

                    StatusCode = eventMessage[-6:-4]
                    if eventMessage[-6:-4] in ["AA","EE"]:
                        is_complete = True
                        if eventMessage[-6:-4] == "AA":
                            # execute umount_media of utils
                            utils.umount_media(bmcip, auth_string, use_endpoint)
                        
                    if eventMessage[-6:-4] == "03":        
                        IP[0] = str(int(eventMessage[-4:-2], 16))
                        IP[1] = str(int(eventMessage[-2:], 16))
                    if eventMessage[-6:-4] in ["04", "13"]:        
                        IP[2] = str(int(eventMessage[-4:-2], 16))
                        IP[3] = str(int(eventMessage[-2:], 16))
                   
                    print(f"[{eventTime}] {eventString} {event_debug_message} (Code : {StatusCode})")
                    if eventMessage[-6:-4] in ["13"] and all(x != "NA" for x in IP):
                        print(f"IP Address : {IP[0]}.{IP[1]}.{IP[2]}.{IP[3]}")
                    if eventMessage[-6:-4] == "05":
                        text1 = chr(int(eventMessage[-4:-2], 16))
                        text2 = chr(int(eventMessage[-2:], 16))
                        audit_result = text1 + text2
                        print(f"Audit Result : {audit_result}")
                currentID = item["Id"]      
            last_log_id = currentID   
        else:
            current_time_string = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            print(f"[{current_time_string}] Server is Unavailable ... (Unable to connect to BMC)")    
            sleep(5)        
        current_timestamp = int(utils.getTargetBMCDateTime(bmcip,auth_string)["data"]["timestamp"])    
    
if __name__ == "__main__":
    main()    