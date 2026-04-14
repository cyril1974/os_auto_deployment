#!/bin/sh

# Parse optional --target-size=<value> argument
# When provided, select the disk whose size is within ±10% of the target
# instead of selecting the smallest empty disk.
# Supported units: T/TB/TiB, G/GB/GiB, M/MB/MiB, K/KB/KiB (case-insensitive).
# Examples: --target-size=7T  --target-size=960G  --target-size=1920GB
TARGET_SIZE_BYTES=0
for _arg in "$@"; do
    case "$_arg" in
        --target-size=*)
            _raw="${_arg#--target-size=}"
            # Extract numeric prefix and unit suffix
            _num=$(echo "$_raw" | sed 's/[^0-9].*$//')
            _unit=$(echo "$_raw" | sed 's/^[0-9]*//' | tr '[:lower:]' '[:upper:]')
            case "$_unit" in
                T|TB|TIB)  TARGET_SIZE_BYTES=$(( _num * 1024 * 1024 * 1024 * 1024 )) ;;
                G|GB|GIB)  TARGET_SIZE_BYTES=$(( _num * 1024 * 1024 * 1024 )) ;;
                M|MB|MIB)  TARGET_SIZE_BYTES=$(( _num * 1024 * 1024 )) ;;
                K|KB|KIB)  TARGET_SIZE_BYTES=$(( _num * 1024 )) ;;
                *)         TARGET_SIZE_BYTES=$_num ;;  # already bytes
            esac
            echo "[*] Target size filter: ${_raw} = ${TARGET_SIZE_BYTES} bytes (±10% tolerance)" > /dev/console
            ;;
    esac
done

# Returns true (0) if $1 bytes is within ±10% of TARGET_SIZE_BYTES.
# Always returns true when no target size was specified.
size_matches_target() {
    local actual="$1"
    [ "$TARGET_SIZE_BYTES" -eq 0 ] && return 0
    local lower=$(( TARGET_SIZE_BYTES - TARGET_SIZE_BYTES / 10 ))
    local upper=$(( TARGET_SIZE_BYTES + TARGET_SIZE_BYTES / 10 ))
    [ "$actual" -ge "$lower" ] && [ "$actual" -le "$upper" ]
}

find_empty_disk_serial() {
    local min_size=0
    local target_serial=""
    local target_disk=""

    if [ "$TARGET_SIZE_BYTES" -gt 0 ]; then
        echo "[!] INFO: Starting disk detection (Size filter: target ±10%)..." > /dev/console
    else
        echo "[!] INFO: Starting automated disk detection (Prefer SMALLEST empty)..." > /dev/console
    fi

    # Get all disk devices (sh-compatible)
    for disk in $(lsblk -nd -o NAME --exclude 1,2,11 2>/dev/null); do
        device="/dev/$disk"
        [ -b "$device" ] || continue

        # 1. Partition Check
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
        # Threshold 512 bytes tolerates residual NVMe firmware noise.
        empty_bytes=$(dd if="$device" bs=1M count=1 2>/dev/null | tr -d '\0' | wc -c)
        if [ "$empty_bytes" -gt 512 ]; then
            echo "    [-] Skipping $device: Contains non-zero data in first 1MB ($empty_bytes bytes)" > /dev/console
            continue
        fi

        # 4. Size Filter (when --target-size is provided)
        size=$(lsblk -ndb -o SIZE "$device" 2>/dev/null)
        if ! size_matches_target "$size"; then
            human_size="$((size/1024/1024/1024))GB"
            echo "    [-] Skipping $device: Size ${human_size} not within ±10% of target" > /dev/console
            continue
        fi

        # 5. Success - Candidate Found
        serial=$(udevadm info --query=property --name="$device" 2>/dev/null | grep "^ID_SERIAL=" | cut -d'=' -f2)

        if [ -z "$serial" ]; then
            # Try DEVPATH fallback for some NVMe controllers
            sys_path=$(udevadm info --query=property --name="$device" 2>/dev/null | grep "^DEVPATH=" | cut -d'=' -f2)
            serial=$(cat "/sys${sys_path}/../serial" 2>/dev/null || cat "/sys${sys_path}/device/serial" 2>/dev/null)
        fi

        if [ -n "$serial" ]; then
            human_size="$((size/1024/1024/1024))GB"
            echo "    [*] Valid Candidate: $device ($human_size, Serial: $serial)" > /dev/console

            # When a size filter is active: pick first match (size already constrains selection).
            # When no filter: pick SMALLEST to avoid large data drives.
            if [ "$TARGET_SIZE_BYTES" -gt 0 ]; then
                # Size-filtered mode: first qualifying disk wins
                target_serial="$serial"
                target_disk="$device"
                min_size="$size"
                break
            else
                # Auto-detect mode: prefer smallest
                if [ "$min_size" -eq 0 ] || [ "$size" -lt "$min_size" ]; then
                    min_size="$size"
                    target_serial="$serial"
                    target_disk="$device"
                fi
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

    if [ "$TARGET_SIZE_BYTES" -gt 0 ]; then
        echo "[!] ERROR: No empty disk matching target size detected." > /dev/console
    else
        echo "[!] ERROR: No empty storage devices detected." > /dev/console
    fi
    return 1
}

# Main Execution Logic
echo "[*] Starting disk detection and config patching..." > /dev/console
serial=$(find_empty_disk_serial "$@")
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
    echo "[!] WARNING: No matching storage device found. Abort installation." > /dev/console
    exit 1
fi
