import json
import urllib3
import urllib3.exceptions
# from . import auth
from . import constants
from . import redfish
from . import utility_mount
from . import utils

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
def testFunction():
    print("Enter Generation TEST")
    return True

# Functions for get generation

def get_generation(model):
    gen_dict = {
        "S2600WF": 2,
        "S2600BP": 2,
        "S2600ST": 2,
        "S9200WK": 2,
        "M50CYP": 3,
        "D50TNP": 3,
        "D40AMP": 3,
        "M50FCP": 6,
        "D50DNP": 6,
        "R520G6": 7,
        "G520G6": 7,
        "S7149GMRE": 7,
        "SC513G6": 7,
        "G527G6": 7,
        "E7142DCPSB":7

    }
    for platform in gen_dict:
        if model.startswith(platform):
            return model, gen_dict[platform]
    return model, 0


def get_generation_redfish(target,auth_string):
    
    member = get_baseboard_api(target,auth_string)
    # print(member)
    # r = redfish(member, init=1)
    r = utils.redfish_get_request(member,target,auth_string,custom_timeout=10)
    # print(r.json())
    model = str(r.json()['Model'])
    #utils.MsgCtl("Model found: {}\n".format(model), False,"print_msg_5", "direct_log_out")
    platform, gen = get_generation(model)
    if gen != 0:
        GENERATION = gen
        PRODUCT_MODEL = model
        return PRODUCT_MODEL, GENERATION

    return None, 0

def get_baseboard_api(target,auth_string):
    members = redfish_getMembersArray('/redfish/v1/Chassis', target,auth_string,retry=1)
    for member in members:
        if 'baseboard' in member.lower():
            return member
    utils.redfish_specific_error('Redfish Baseboard Error', 'ERedfishResponse')

def redfish_getMembersArray(cmd, target,auth_string, retry=0, check_member_exist=False):
    members = []
    try:
        # content = redfish(cmd)
        content = utils.redfish_get_request(cmd,target,auth_string,custom_timeout=10)
        output = content.json()
        cnt = int(output['Members@odata.count'])
        if cnt == 0:
            return members
        for entry in range(0, cnt):
            members.append(output['Members'][entry]['@odata.id'])
    except (KeyError, IndexError):
        if retry > 0:
            return redfish_getMembersArray(cmd, target,auth_string,retry-1, check_member_exist)
        elif check_member_exist == True:
            return ''
        else:
            utils.redfish_specific_error("Redfish key error", 'ERedfishAttribute')
    return members
# Functions for get generation

