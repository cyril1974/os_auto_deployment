# IPMI SEL Logging Commands Summary

**Version**: v1.0
**Date**: 2026-03-23
**Target Platforms**: Mitac R1520G6, Intel-based BMCs, standard IPMI 2.0.

---

## 1. Overview
The autoinstall ISO uses the **IPMI System Event Log (SEL)** to provide out-of-band observability during the mastering and installation process. This document summarizes all `ipmi raw` commands used for logging.

### All commands use:
- **NetFunction**: `0x0a` (Storage)
- **Command**: `0x44` (Add SEL Entry)
- **Format**: Standard System Event Record (**Type 0x02**, 16 bytes).
- **Generator ID**: `0x21 0x00` (Software ID 1). This bypasses restrictions some BMCs place on the BMC Generator ID (0x20).

---

## 2. Command Reference (v2-rev18 Forensic Spec)

### 2.1 OS Installation Starting
Used in `early-commands` to signal the beginning of the deployment process.
- **Command**: `0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x01 0x00 0x00`
- **Data 1**: `0x01` (Event Marker: Starting)
- **Data 2/3**: `0x00 0x00` (Standardized Padding)

### 2.2 Package Pre-installation (ipmitool dependency)
Fires during `early-commands` as the ISO bundles its own `.deb` installer packages.
- **Pre-install Start**: `0x0a 0x44 0x00 0x00 ... 0x6f 0x0f 0x00 0x00` (Marker: `0x0f`)
- **Pre-install Complete**: `0x0a 0x44 0x00 0x00 ... 0x6f 0x1f 0x00 0x00` (Marker: `0x1f`)

### 2.3 IP Address Logging (Two-Part)
Used in `late-commands` to record the assigned network IP.
- **Part 1 (Octets 1.2)**: `0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x03 [h1] [h2]`
- **Part 2 (Octets 3.4)**: `0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x04 [h3] [h4]`
- **Data 1**: `0x03` (IP Part 1), `0x04` (IP Part 2).

### 2.4 OS Installation Completed
Used after all scripts successfully execute.
- **Command**: `0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0xaa 0x00 0x00`
- **Data 1**: `0xaa` (Event Marker: Completed)
- **Data 2/3**: `0x00 0x00` (Standardized Padding)

### 2.5 OS Installation Aborted/Failed
Triggered by the `error-commands` block if Subiquity encounters a fatal error.
- **Command**: `0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0xee 0x00 0x00`
- **Data 1**: `0xee` (Event Marker: Aborted/Failed)
- **Data 2/3**: `0x00 0x00` (Standardized Padding)

### 2.6 Post-Install Phase (Package Installation)
Used to track the package installation phase in `late-commands`, which is one of the longest-running operations.
- **Post-Install Start**: `0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x06 0x00 0x00` (Marker: `0x06`)
- **Post-Install Complete**: `0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x16 0x00 0x00` (Marker: `0x16`)
- **Data 1**: `0x06` (Start), `0x16` (Complete)
- **Data 2/3**: `0x00 0x00` (Standardized Padding)

### 2.7 Installation Audit: Storage Verification
Used to log the outcome of the root disk serial number check.
- **Success**: `0x0a 0x44 0x00 0x00 0x02 ... 0x6f 0x05 0x4f 0x4b` (ASCII 'OK')
- **Failure**: `0x0a 0x44 0x00 0x00 0x02 ... 0x6f 0x05 0x45 0x52` (ASCII 'ER')
- **Data 1**: `0x05` (Marker: Audit)

---

## 3. Byte Breakdown (IPMI 2.0 Standard)

| Index | Field | Value | Description |
|---|---|---|---|
| 0 | NetFunction | `0x0a` | Storage |
| 1 | Command | `0x44` | Add SEL Entry |
| 2-3 | Record ID | `0x0000` | BMC Auto-assigns next ID |
| 4 | Record Type | `0x02` | Standard System Event |
| 5-8 | Timestamp | `0x00000000` | BMC current clock time |
| 9-10 | Generator ID | `0x2100` | Software ID 1 (SW id 0x21) |
| 11 | EvM Revision | `0x04` | Standard Event Message Revision |
| 12 | Sensor Type | `0x12` | OS Boot / System Event |
| 13 | Sensor Num | `0x00` | Generic Placeholder |
| 14 | Event Type | `0x6f` | Sensor-specific Discrete |
| 15 | Event Data 1 | Var | **Marker:** (0x01=Start, 0x0F=PreStart, 0x1F=PreDone, 0x06=PostStart, 0x16=PostDone, 0xAA=Finish, 0x03=IP1, 0x13=IP2, 0x05=Audit, 0xEE=Abort) |
| 16 | Event Data 2 | Var | Primary payload byte |
| 17 | Event Data 3 | Var | Secondary payload byte |

---

## 4. Why we use Type 0x02 instead of Type 0xC0 (OEM)
During testing on **Mitac G6 (R1520G6U2XD)**, it was discovered that the BMC rejects the `0xc0` record type with an `0xcc` (Invalid data field) error. To ensure maximum platform compatibility across the cluster, we use the standard **Type 0x02** format for all logs, even if multiple entries are required to store larger data like IP addresses.
