# Debugging Note: Missing IP Address Part 2 in SEL Logging

**Date**: 2026-03-24
**Target Node**: 10.99.236.85
**Project Version**: v2-rev12 (Initial Reported) -> v2-rev13 (Resolved)

---

## 1. Issue Description
During the `late-commands` phase of the Ubuntu autoinstall, the target server assigned its IP address (10.99.236.85). The script is designed to log this in two parts to the BMC's System Event Log (SEL) due to the 3-byte data limit in standard Type 0x02 records.

- **Expected**: 
    1. Marker 0x01 (Octets 1, 2)
    2. Marker 0x02 (Octets 3, 4)
    3. Marker 0x02 (Installation Completed)
- **Observed**: Part 1 and "Installation Completed" were recorded correctly, but Part 2 (Octets 3, 4) was missing entirely.

## 2. Debugging Steps

### Step 1: Verification of SEL State
Connected to server 10.99.236.85 and executed `ipmitool sel list`.
```text
10d | 03/24/2026 | 00:09:37 | System Event | OEM System boot event | Asserted  <-- (10.99)
10e | 03/24/2026 | 00:09:38 | System Event | Undetermined system hardware failure | Asserted  <-- (Completed)
```
The record for `F02EC55` (Octets 236.85) was absent between entries `10d` and `10e`.

### Step 2: Log Audit (Subiquity Server Debug)
Examined `/var/log/installer/subiquity-server-debug.log` to confirm if the command actually fired.
- `command_7` (IP Logging) finished at `00:09:38,502`.
- `command_8` (Completed) started at `00:09:38,503`.
- **Finding**: The time gap between the IP Part 2 command and the Installation Completed command was precisely **1 millisecond**.

### Step 3: Manual Command Verification
Ran the failing Part 2 command manually via root shell:
`ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x02 0xec 0x55`
- **Result**: **SUCCESS**. The entry appeared in the SEL as entry `110`. 
- **Conclusion**: The command logic and IP parsing are correct; the failure only occurs during high-speed automated execution.

## 3. Root Cause Analysis
**BMC Processing Collision**:
The Mitac/Intel G6 BMC uses an internal queue for IPMI Storage commands (NetFn 0x0a). When multiple `Add SEL Entry` (Cmd 0x44) commands are received using the **same Event Data 1 marker (0x02)** within the same second, the hardware buffer can experience a collision.
The first `0x02` record (IP Part 2) was being overwritten or discarded because the subsequent `0x02` record (Installation Completed) arrived before the BMC could finalize the first write to NVM (Non-Volatile Memory).

## 4. Resolution
**Sequential Staggering**:
Introduced a mandatory `sleep 1` second delay into the `late-commands` block of the autoinstall script.

```bash
# Part 1: IP Octets 1.2
ipmitool raw ... 0x6f 0x01 $h1 $h2
sleep 1
# Part 2: IP Octets 3.4
ipmitool raw ... 0x6f 0x02 $h3 $h4
sleep 1
# Installation Completed
ipmitool raw ... 0x6f 0x02 0x00 0x00
```

This ensures the BMC has a clear processing window for each log entry, preventing data loss during OOB telemetry.

---
**Resolved in Commit**: `v2-rev13`
