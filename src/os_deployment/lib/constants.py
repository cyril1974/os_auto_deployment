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
MOUNT_IMAGE_API = {
    "7":"/redfish/v1/Managers/bmc/VirtualMedia/Inband/Actions/Oem/VirtualMedia.MountImage",
    "6":"/redfish/v1/Managers/bmc/VirtualMedia/Internal/Actions/Oem/VirtualMedia.MountImage"
    }
BMC_MANAGER_API = "/redfish/v1/Managers/bmc"
POSTCODE_LOG_API = "/redfish/v1/Systems/system/LogServices/PostCodes/Entries"
LOG_FETCH_API = "/redfish/v1/Systems/system/LogServices/EventLog/Entries"

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
REBOOT_TIMEOUT = 300
PROCESS_TIMEOUT = 180
REDFISH_SESSION = None
POWER_RESTORE_EVENT = "Power restore policy applied"

EventLogPrefix = "FFFF02000020040F6F04"
EventLogSServerity = {
    "00": "[Notice]",
    "01": "[OK]",
    "02": "[Warning]",
    "03": "[Critical]",
    "04": "[Debug]"
    
}

EventLogCategory = {
    "00":"[Flow]",
    "01":"[SUP]",
    "02":"[Component]",
    "03":"[SSD]"
}

EventMessage = {
    "000000":"Process Complete",
    "000001":"Server Boot Up OK and Enter startup.nsh",
    "000002":"Files Copy Complete",
    "000003":"Found no Utility Package image is mounted , stop update",
    "000004":"Found no Custom Firmwate Update Package image is mounted , stop update",
    "000005":"Utility package is copied to RAM Disk Complete",
    "000006":"Custom Firmwate Update Package is cpoied to RAM Disk Complete",
    "000007":"Copy Utility Files to RAM Disk Start",
    "000008":"Copy Custom Firmwate Update Files to RAM Disk Start",
    "000009":"Copy Utility Files to RAM Disk Complete",
    "00000A":"Copy Custom Firmwate UpdateFiles to RAM Disk Complete",
    "00000B":"Start to Update Firmware",
    "00000C":"Find Board Firmware , Start to Update Board Firmware (CPLD/BMC/BIOS/ROT)",
    "00000D":"Find No Board Firmware , Bypass Board Firmware Update",
    "00000E":"Find Component Firmware , Start to Update Component Firmware (NIC/RAID)",
    "00000F":"Find No Component Firmware , Bypass Component Firmware Update",
    "000010":"Find SSD Firmware , Start to Update SSD Firmware",
    "000011":"Find No SSD Firmware , Bypass SSD Firmware Update",
    "000012":"LOG Collecting Start",
    "000013":"Board Firmware (SUP/FUP) Update Success",
    "000014":"Board Firmware (SUP/FUP) Update Fail",
    "000015":"Components Firmware (RAID/NIC) Update Success",
    "000016":"Components Firmware (RAID/NIC) Update Fail",
    "000017":"Board Firmware is Updated and Reboot",
    "000018":"Start to Update BIOS Firmware",
    "000019":"Update BIOS Firmware Complete",
    "00001A":"Start to Update BMC Firmware",
    "00001B":"Update BMC Firmware Complete",
    "00001C":"Start to Update CPLD Firmware",
    "00001D":"Update CPLD Firmware Complete",
    "00001E":"Start to Update ROT Firmware",
    "00001F":"Update ROT Firmware Complete",
    "000020":"SSD Firmware Update Success",
    "000021":"SSD Firmware Update Fail",
    "000022":"Copy SSD Firmware Update Boot Image to RAM Disk",
    "000023":"Try to Boot system and load initrd to execute SSD Firmware Update",
    "000024":"Success boot into initrd and try to mount internalVM for logging",
    "000025":"Fail to mount internalVM for logging , exit Update",
    "000026":"Success to mount internalVM for logging and try to trigger ssd firmware update tool issdfut",
    "000027":"Fail to execute firmware update tool issdfut , SSD update exit",
    "000028":"Reboot System",
    "000029":"Component Firmware is Updated and Reboot",
    "FFFFFF":"Process Abort"
}