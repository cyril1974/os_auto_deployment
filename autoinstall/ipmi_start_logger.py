#!/usr/bin/env python3
import os
import struct
import fcntl
import sys

# Linux IPMI IOCTL code and address type (from <linux/ipmi.h>)
IPMICTL_SEND_COMMAND = 0x8028690d
IPMI_SYSTEM_INTERFACE_ADDR_TYPE = 0x0c

def send_ipmi_raw(netfn, cmd, data):
    """
    Sends a RAW IPMI command via /dev/ipmi0 using ioctls.
    """
    # 1. Device Open
    try:
        fd = os.open("/dev/ipmi0", os.O_RDWR)
    except FileNotFoundError:
        print("[!] /dev/ipmi0 not found. Is ipmi_devintf loaded?")
        return False

    # 2. Address Packing (struct ipmi_system_interface_addr)
    # int addr_type, short channel, unsigned char lun
    addr = struct.pack("ishB", IPMI_SYSTEM_INTERFACE_ADDR_TYPE, 0, 0, 0)

    # 3. Message Packing (struct ipmi_msg)
    # unsigned char netfn, unsigned char cmd, unsigned short data_len, unsigned char *data_ptr
    # In Python, we have to handle the pointer. We'll use ctypes to get the address of our data buffer.
    import ctypes
    data_bytes = bytes(data)
    data_ptr = ctypes.c_char_p(data_bytes)
    
    # struct ipmi_msg { netfn, cmd, data_len, data_ptr }
    # Padding/Alignment: B B H L (NetFn, Cmd, Len, Ptr)
    # On 64-bit, pointers are 8 bytes. We use 'P' for pointer.
    msg = struct.pack("BBHP", netfn << 2, cmd, len(data_bytes), ctypes.cast(data_ptr, ctypes.c_void_p).value)

    # 4. Request Packing (struct ipmi_req)
    # struct ipmi_req { addr_ptr, addr_len, msgid, ipmi_msg }
    # Padding: P I q (Pointer, Len, ID, struct)
    addr_ptr = ctypes.c_char_p(addr)
    req = struct.pack("PIqBBHP", 
                      ctypes.cast(addr_ptr, ctypes.c_void_p).value, 
                      len(addr), 
                      0, # msgid
                      netfn << 2, cmd, len(data_bytes), 
                      ctypes.cast(data_ptr, ctypes.c_void_p).value)

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
    data = [
        0x00, 0x00, # CID
        0x02,       # RecType
        0x00, 0x00, 0x00, 0x00, # Timestamp
        0x21, 0x00, # GenID (SW 0x21)
        0x04,       # EvMRev
        0x12,       # SensorType (SystemEvent)
        0x00,       # SensorNum
        0x6f,       # EventType (Specific)
        0x01,       # Data1 (Starting)
        0x00, 0x00  # Data2/3 (Padding)
    ]
    
    send_ipmi_raw(netfn, cmd, data)
