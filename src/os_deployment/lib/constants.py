import os
import pathlib
import json

PROUDCT_MODEL = ''
GENERATION = ''

VIRTUAL_MEDIA_API_DICT = {
    "6":"/redfish/v1/Managers/bmc/VirtualMedia",
    "7":"/redfish/v1/Managers/bmc/VirtualMedia"
}

INBAND_MEDIA = {
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/",
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/"
}

UMOUNT_IMAGE_API = {
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.UmountImage",
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/Actions/Oem/VirtualMedia.UmountImage"
}

DELETE_IMAGE_API = {
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.DeleteImage",
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/Actions/Oem/VirtualMedia.DeleteImage"
}

CREATE_IMAGE_API = {
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.CreateImage",
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/Actions/Oem/VirtualMedia.CreateImage"
}

PUTFILE_IMAGE_API = {
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.PutFileToImage",
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/Actions/Oem/VirtualMedia.PutFileToImage"
}

GETFILE_IMAGE_API = {
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.GetFileFromImage",
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/Actions/Oem/VirtualMedia.GetFileFromImage"
}

LOG_FETCH_API = {
    "6":"/redfish/v1/Systems/system/LogServices/EventLog/Entries",
    "7":"/redfish/v1/Managers/bmc/LogServices/SEL/Entries"
}

MOUNT_IMAGE_API = {
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.MountImage",
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/Actions/Oem/VirtualMedia.MountImage"
}

BMC_MANAGER_API = "/redfish/v1/Managers/bmc"
POSTCODE_LOG_API = "/redfish/v1/Systems/system/LogServices/PostCodes/Entries"
POSTCODE_LOG_CLEAR_API = "/redfish/v1/Systems/system/LogServices/PostCodes/Actions/LogService.ClearLog"

VERSION_GET_API = {}
VERSION_GET_API["BIOS"] = "/redfish/v1/UpdateService/FirmwareInventory/bios_active"
VERSION_GET_API["BMC"] = "/redfish/v1/UpdateService/FirmwareInventory/bmc_active"
VERSION_GET_API["CPLD"] = "/redfish/v1/UpdateService/FirmwareInventory/cpld_active"
VERSION_GET_API["ROT"] = "/redfish/v1/UpdateService/FirmwareInventory/rot_fw_active"

PLATFROM_STRING = {
    "6":"EGS",
    "7":"BHS"
}

DEFAULT_LOG_PATH = "./logs"
IMAGESIZE = 192
REDFISH_TIMEOUT = 15
REBOOT_TIMEOUT = 1200
PROCESS_TIMEOUT = 7200
REDFISH_SESSION = None
POWER_RESTORE_EVENT = "Power restore policy applied"

EventLogPrefix = {
    "6": "0000020000000021000412006F",
    "7": "210012006F"
}

EventLogMessage = {
    "01": "[Info] OS Installation Start",
    "0F": "[Info] Package Pre-install Start",
    "1F": "[Info] Package Pre-install Complete",
    "AA": "[Info] OS Installation Completed",
    "03": "[Info] IP Address Logging (Part 1)",
    "04": "[Info] IP Address Logging (Part 2, legacy)",
    "13": "[Info] IP Address Logging (Part 2)",
    "05": "[Info] Installation Audit: Storage Verification",
    "EE": "[Error] OS Installation Aborted/Failed"
}
