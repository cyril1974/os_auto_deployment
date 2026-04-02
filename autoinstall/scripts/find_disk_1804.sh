#!/bin/sh
# Find the smallest available disk suitable as an installation target.
# Uses only tools guaranteed present in Ubuntu 18.04 d-i minimal environment:
#   /sys/block, /proc/partitions, /proc/mounts, blkid, awk, grep
# Output: device path (e.g. /dev/sda), exit 0 on success, exit 1 if none found.

LOG=/tmp/find_disk_1804.log
RESULT=/tmp/find_disk_1804.result
# Redirect all stdout/stderr to log; use explicit "> /dev/console" for console output
# NOTE: do NOT use command substitution to capture output of this script —
# read $RESULT file instead, as exec redirects stdout away from the caller.
exec > "$LOG" 2>&1
set -x

_con() { echo "$1" > /dev/console; }

_con "=== find_disk_1804.sh start ==="

min_size=0
target_disk=""
fallback_disk=""
fallback_size=0

# /sys/block/ contains only whole-disk devices (no partitions), making it the
# most reliable enumeration source in d-i — no awk regex needed.
disk_list=$(ls /sys/block/ 2>/dev/null | grep -v '^loop\|^ram\|^sr\|^fd\|^dm\|^md')

if [ -z "$disk_list" ]; then
    _con "[!] ERROR: No disks found in /sys/block/"
    cat "$LOG" > /dev/console
    exit 1
fi

_con "[*] Disk candidates from /sys/block/: $disk_list"

for disk_name in $disk_list; do
    device="/dev/$disk_name"
    [ -b "$device" ] || { _con "    [-] $device: not a block device, skip"; continue; }

    # Size: /sys/block/<name>/size = number of 512-byte sectors
    sectors=$(cat "/sys/block/${disk_name}/size" 2>/dev/null)
    if [ -z "$sectors" ] || [ "$sectors" -eq 0 ]; then
        _con "    [-] $device: size=0, skip"
        continue
    fi
    size=$(( sectors * 512 ))
    human_size="$((size/1024/1024/1024))GB"

    _con "    [?] Checking $device ($human_size)..."

    # --- Check 1: Not mounted ---
    if grep -q "^${device}" /proc/mounts 2>/dev/null; then
        _con "    [-] $device: mounted, skip"
        continue
    fi

    # --- Check 2: No child partitions in /sys/block/<disk>/ ---
    part_count=$(ls "/sys/block/${disk_name}/" 2>/dev/null | grep -c "^${disk_name}")
    if [ "$part_count" -gt 0 ]; then
        _con "    [-] $device: has $part_count partition(s), fallback candidate"
        if [ "$fallback_size" -eq 0 ] || [ "$size" -lt "$fallback_size" ]; then
            fallback_size="$size"
            fallback_disk="$device"
        fi
        continue
    fi

    # --- Check 3: No filesystem signatures via blkid ---
    sig=$(blkid "$device" 2>/dev/null)
    if [ -n "$sig" ]; then
        _con "    [-] $device: has signatures ($sig), fallback candidate"
        if [ "$fallback_size" -eq 0 ] || [ "$size" -lt "$fallback_size" ]; then
            fallback_size="$size"
            fallback_disk="$device"
        fi
        continue
    fi

    # --- Clean candidate ---
    _con "    [+] Clean candidate: $device ($human_size)"
    if [ "$min_size" -eq 0 ] || [ "$size" -lt "$min_size" ]; then
        min_size="$size"
        target_disk="$device"
    fi
done

# Print full debug log to console before returning result
cat "$LOG" > /dev/console

if [ -n "$target_disk" ]; then
    _con "[+] Selected (clean): $target_disk ($((min_size/1024/1024/1024))GB)"
    echo "$target_disk" > "$RESULT"
    cat "$LOG" > /dev/console
    exit 0
fi

if [ -n "$fallback_disk" ]; then
    _con "[!] No clean disk. Using fallback (partman will wipe): $fallback_disk ($((fallback_size/1024/1024/1024))GB)"
    echo "$fallback_disk" > "$RESULT"
    cat "$LOG" > /dev/console
    exit 0
fi

_con "[!] ERROR: No suitable disk found."
cat "$LOG" > /dev/console
exit 1
