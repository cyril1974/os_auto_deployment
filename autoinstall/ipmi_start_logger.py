#!/usr/bin/env python3
import os
import fcntl
import ctypes
import sys
from datetime import datetime

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

def parse_val(val):
    try:
        return int(val, 16) if str(val).startswith("0x") else int(val)
    except (ValueError, TypeError):
        return 0

def log_command_execution(marker, b1, b2, success):
    """Logs the command results to a persistent file for post-install review."""
    log_paths = ["/var/log/ipmi_telemetry.log", "/tmp/ipmi_telemetry.log"]
    timestamp = datetime.now().isoformat()
    status = "SUCCESS" if success else "FAILED"
    payload = f"0x{marker:02x} 0x{b1:02x} 0x{b2:02x}"
    log_line = f"[{timestamp}] IPMI Entry: {payload} | Status: {status}\n"
    
    for path in log_paths:
        try:
            # Check if directory exists
            dir_name = os.path.dirname(path)
            if not os.path.exists(dir_name):
                continue
            with open(path, "a") as f:
                f.write(log_line)
            return True
        except Exception:
            continue
    return False

if __name__ == "__main__":
    marker = 0x0f  # Default to Install Initiated
    byte1  = 0x00
    byte2  = 0x00

    if len(sys.argv) > 1:
        marker = parse_val(sys.argv[1])
    if len(sys.argv) > 2:
        byte1 = parse_val(sys.argv[2])
    if len(sys.argv) > 3:
        byte2 = parse_val(sys.argv[3])

    # OS Installation Milestone Entry (Add SEL Entry)
    # NetFn: 0x0a (Storage), Cmd: 0x44 (Add SEL Entry)
    netfn = 0x0a
    cmd = 0x44
    
    # 0. Prevent duplicate logging of the same marker in environments where 
    # early-commands/late-commands are executed multiple times (Subiquity bug)
    marker_lock = f"/tmp/ipmi_marker_{marker:02x}.lock"
    if os.path.exists(marker_lock):
        # Already logged this marker in this OS session
        sys.exit(0)

    # SEL Record Structure (Marker/Payload)
    data = [
        0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x21, 
        0x00, 0x04, 0x12, 0x00, 0x6f, marker, byte1, byte2
    ]
    
    success = send_ipmi_raw(netfn, cmd, data)
    
    if success:
        # Create lock file after successful transmission
        try:
            with open(marker_lock, 'w') as f:
                f.write(f"{datetime.now().isoformat()}")
        except Exception:
            pass

    log_command_execution(marker, byte1, byte2, success)
    
    sys.exit(0 if success else 1)
