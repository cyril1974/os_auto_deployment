#!/bin/sh
find_empty_disk_serial() {
    local min_size=0
    local target_serial=""
    local target_disk=""

    echo "[!] INFO: Starting automated disk detection (Prefer SMALLEST empty)..." > /dev/console

    # Get all disk devices (sh-compatible)
    for disk in $(lsblk -nd -o NAME --exclude 1,2,11 2>/dev/null); do
        device="/dev/$disk"
        [ -b "$device" ] || continue

        # 1. Partition Check
        # Note: lsblk -n (no header) without -d (no children) lists device + all children;
        # -k is NOT a valid lsblk flag and causes silent empty output — use -n only.
        partition_count=$(lsblk -n -o TYPE "$device" 2>/dev/null | grep -c "part")
        if [ "$partition_count" -gt 0 ]; then
            echo "    [-] Skipping $device: Contains $partition_count partition(s)" > /dev/console
            continue
        fi

        # 2. Filesystem Signature Check
        signatures=$(wipefs "$device" 2>/dev/null | grep -v "^offset")
        if [ -n "$signatures" ]; then
            echo "    [-] Skipping $device: Contains filesystem signatures" > /dev/console
            continue
        fi

        # 3. Data Check (First 1MB)
        # Use portable tr to check for non-zero bytes (Dash compatible)
        empty_bytes=$(dd if="$device" bs=1M count=1 2>/dev/null | tr -d '\0' | wc -c)
        if [ "$empty_bytes" -gt 0 ]; then
            echo "    [-] Skipping $device: Contains non-zero data in first 1MB" > /dev/console
            continue
        fi

        # 4. Success - Candidate Found
        size=$(lsblk -ndb -o SIZE "$device" 2>/dev/null)
        serial=$(udevadm info --query=property --name="$device" 2>/dev/null | grep "^ID_SERIAL=" | cut -d'=' -f2)

        if [ -z "$serial" ]; then
            # Try DEVPATH fallback for some NVMe controllers
            sys_path=$(udevadm info --query=property --name="$device" 2>/dev/null | grep "^DEVPATH=" | cut -d'=' -f2)
            serial=$(cat "/sys${sys_path}/../serial" 2>/dev/null || cat "/sys${sys_path}/device/serial" 2>/dev/null)
        fi

        if [ -n "$serial" ]; then
            human_size="$((size/1024/1024/1024))GB"
            echo "    [*] Valid Candidate: $device ($human_size, Serial: $serial)" > /dev/console

            # Implementation of SMALLEST logic to avoid large data drives
            if [ "$min_size" -eq 0 ] || [ "$size" -lt "$min_size" ]; then
                min_size="$size"
                target_serial="$serial"
                target_disk="$device"
            fi
        else
            echo "    [!] Warning: $device is empty but has no accessible serial. Skipping." > /dev/console
        fi
    done

    if [ -n "$target_serial" ]; then
        echo "[+] Final Selection: $target_disk ($((min_size/1024/1024/1024))GB, Serial: $target_serial)" > /dev/console
        echo "$target_serial"
        return 0
    fi

    echo "[!] ERROR: No empty storage devices detected." > /dev/console
    return 1
}

# Main Execution Logic
echo "[*] Starting disk detection and config patching..." > /dev/console
serial=$(find_empty_disk_serial)
if [ $? -eq 0 ]; then
    echo "[*] Detected disk serial: $serial" > /dev/console
    # CRITICAL: Patch /autoinstall.yaml FIRST (symlink to /cdrom/autoinstall/user-data)
    # This file is read by subiquity BEFORE any other configs are created
    if [ -f /autoinstall.yaml ]; then
        echo "[*] Patching /autoinstall.yaml with serial: $serial" > /dev/console
        sed -i "s/__ID_SERIAL__/${serial}/g" /autoinstall.yaml
    fi
    # Also patch any runtime configs that subiquity may have already created
    for cfg in /run/subiquity/autoinstall.yaml /run/subiquity/cloud.autoinstall.yaml /tmp/autoinstall.yaml; do
        if [ -f "$cfg" ]; then
            echo "[*] Patching $cfg with serial: $serial" > /dev/console
            sed -i "s/__ID_SERIAL__/${serial}/g" "$cfg"
        fi
    done
    echo "[+] Disk serial replacement completed" > /dev/console
else
    echo "[!] WARNING: No empty storage device found. Abort installation." > /dev/console
    exit 1
fi
