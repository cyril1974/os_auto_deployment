#!/usr/bin/env python3
import os
import fcntl
import ctypes
import sys

# Linux IPMI IOCTL code and address type (from <linux/ipmi.h>)
IPMICTL_SEND_COMMAND = 0x8028690d
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
    Sends a RAW IPMI command via /dev/ipmi0 using ctypes for correct structure alignment.
    """
    try:
        fd = os.open("/dev/ipmi0", os.O_RDWR)
    except FileNotFoundError:
        print("[!] /dev/ipmi0 not found. Is ipmi_devintf loaded?")
        return False
    except PermissionError:
        print("[!] Permission denied opening /dev/ipmi0. Need root.")
        return False

    # 1. Prepare Data Buffer
    data_bytes = bytes(data)
    data_buffer = ctypes.create_string_buffer(data_bytes)

    # 2. Prepare Address Structure
    addr = IPMISystemInterfaceAddr()
    addr.addr_type = IPMI_SYSTEM_INTERFACE_ADDR_TYPE
    addr.channel = 0
    addr.lun = 0

    # 3. Prepare Message Structure
    msg = IPMIMsg()
    msg.netfn = netfn << 2  # NetFn is 6 bits, shift by 2
    msg.cmd = cmd
    msg.data_len = len(data_bytes)
    msg.data = ctypes.addressof(data_buffer)

    # 4. Prepare Request Structure
    req = IPMIReq()
    req.addr = ctypes.addressof(addr)
    req.addr_len = ctypes.sizeof(addr)
    req.msgid = 0
    req.msg = msg

    # 5. Execute IOCTL
    try:
        fcntl.ioctl(fd, IPMICTL_SEND_COMMAND, req)
        print("[+] IPMI command sent successfully.")
        return True
    except OSError as e:
        print(f"[!] IOCTL failed: {e}")
        return False
    finally:
        os.close(fd)

if __name__ == "__main__":
    # OS Installation Starting (Marker 0x01)
    # NetFn: 0x0a (Storage), Cmd: 0x44 (Add SEL Entry)
    netfn = 0x0a
    cmd = 0x44
    # 16-byte SEL Data (Type 0x02 Record)
    # CID[2] RecType Timestamp[4] GenID[2] EvMRev SensorType SensorNum EventType EvData1 EvData2 EvData3
    data = [
        0x00, 0x00, # CID (auto-generated)
        0x02,       # Record Type (System Event)
        0x00, 0x00, 0x00, 0x00, # Timestamp (auto-generated)
        0x21, 0x00, # Generator ID (Software ID 0x21)
        0x04,       # EvM Revision
        0x12,       # Sensor Type (System Event)
        0x00,       # Sensor Number
        0x6f,       # Event Type (Specific)
        0x01,       # Event Data 1 (OS Installation Starting)
        0x00, 0x00  # Event Data 2/3 (Padding)
    ]
    
    send_ipmi_raw(netfn, cmd, data)
