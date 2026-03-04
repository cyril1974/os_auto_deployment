#!/usr/bin/env python3
import argparse
import pathlib
import os
import stat
import subprocess
import sys
from datetime import datetime
from time import sleep
import json

from .lib import config
from .lib import auth
# from .lib import nfs
# from .lib import remote_mount
# from .lib import reboot
from .lib import utility_mount
from .lib import constants
from .lib import utils

target = "10.99.236.49"
absolute_config_path = pathlib.Path("config.json").resolve()
config_json = config.load_config(str(absolute_config_path))
# print(config_json)

auth_string = auth.get_auth_header(target,config_json)
result = utils.getTargetBMCDateTime(target,auth_string)
timestamp = int(result["data"]["timestamp"])

# 1749022780
print(result)
fromtimestamp = 1749023879
# print(f"Reboot Time Elapsed :  {utils.wait_for_reboot(target,auth_string,timestamp)} ")
# print(result)
# if result["status"]== "ok":
#    print(f"TimeStamp : {int(result["data"]["timestamp"])}")
# timestamp = 1747119072

from_timestamp = fromtimestamp
result = utils.getSystemEventLog(target,auth_string,from_timestamp)
# print(json.dumps(result,indent=2))

#result = utils.log_collect(target,auth_string,constants.DEFAULT_LOG_PATH)
# result = utils.getSystemEventLog(target,auth_string,1749000000)
# check_power_restore = utils.filter_message_event(result,constants.POWER_RESTORE_EVENT)
# print(result)

# print(utils.check_mount_status(target,auth_string,constants.INBAND_MEDIA))
# print(utils.check_mount_status(target,auth_string,"/redfish/v1/Managers/bmc/VirtualMedia/WebISO_0"))
# print(utils.check_mount_status(target,auth_string,"/redfish/v1/Managers/bmc/VirtualMedia/WebISO_1"))
# utility_mount.mount_utility(target,config_json)

        
