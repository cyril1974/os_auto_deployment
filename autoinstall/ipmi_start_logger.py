#!/usr/bin/env python3
import os
import fcntl
import ctypes
import sys

# Constants for IPMI IOCTL (Standard for x64)
# Some kernels use 0x8028690d (_IOR), others 0x4028690d (_IOW)
IPMICTL_SEND_COMMAND_READ = 0x8028690d
IPMI_SYSTEM_INTERFACE_ADDR_TYPE = 0x0c

# Definitions for C-style structures
class IPMISystemInterfaceAddr(ctypes.Structure):
    _fields_ = [
        ("addr_type", ctypes.c_int),
        ("channel", ctypes.c_short),
        ("lun", ctypes.c_ubyte),
    ]

class IPMIMsg(ctypes.Structure):
    _fields_ = [
        ("netfn", ctypes.c_ubyte),
        ("cmd", ctypes.c_ubyte),
        ("data_len", ctypes.c_ushort),
        ("data", ctypes.c_void_p),
    ]

class IPMIReq(ctypes.Structure):
    _fields_ = [
        ("addr", ctypes.c_void_p),
        ("addr_len", ctypes.c_uint),
        ("msgid", ctypes.c_long),
        ("msg", IPMIMsg),
    ]

def send_ipmi_raw(netfn, cmd, data):
    """
    Sends a RAW IPMI command via /dev/ipmi0.
    Tries different NetFn and IOCTL combinations to handle various kernel implementations.
    """
    try:
        fd = os.open("/dev/ipmi0", os.O_RDWR)
    except Exception as e:
        print(f"[!] /dev/ipmi0 error: {e}")
        return False

    # 1. Prepare Data
    data_bytes = bytes(data)
    data_buffer = ctypes.create_string_buffer(data_bytes)

    # 2. Try common Address/NetFn/IOCTL combinations
    # addr_type: 0x0c (System Interface)
    # channel: 0x00 or 0x0f (BMC)
    # netfn: shifted (netfn << 2) or raw (netfn)
    # ioctl: 0x8028690d or 0x4028690d
    
    success = False
    for channel in [0x00, 0x0f]:
        addr = IPMISystemInterfaceAddr(IPMI_SYSTEM_INTERFACE_ADDR_TYPE, channel, 0)
        for fn_val in [netfn, netfn << 2]:
            msg = IPMIMsg(fn_val, cmd, len(data_bytes), ctypes.addressof(data_buffer))
            req = IPMIReq(ctypes.addressof(addr), ctypes.sizeof(addr), 0, msg)
            for ioctl_code in [IPMICTL_SEND_COMMAND_READ, 0x4028690d]:
                try:
                    fcntl.ioctl(fd, ioctl_code, req)
                    success = True
                    break
                except OSError:
                    continue
            if success: break
        if success: break

    if success:
        print(f"[+] IPMI command sent (NetFn=0x{fn_val:02x}, Channel=0x{channel:02x}).")
    else:
        print("[!] All IPMI IOCTL attempts failed (Invalid argument or device busy).")
    
    os.close(fd)
    return success

if __name__ == "__main__":
    data1_val = 0x01  # Default to "Start"
    if len(sys.argv) > 1:
        try:
            val = sys.argv[1]
            data1_val = int(val, 16) if val.startswith("0x") else int(val)
        except ValueError: pass

    # OS Installation Milestone Entry
    # NetFn: 0x0a (Storage), Cmd: 0x44 (Add SEL Entry)
    netfn = 0x0a
    cmd = 0x44
    data = [
        0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x21, 
        0x00, 0x04, 0x12, 0x00, 0x6f, data1_val, 0x00, 0x00
    ]
    
    send_ipmi_raw(netfn, cmd, data)
