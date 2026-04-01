# Debug Report: Missing SEL Logs during OS Installation

**Date**: 2026-03-23
**Target Server**: 10.99.236.90 (Testing), 10.99.236.49 (Original)
**Hardware**: MiTAC R1520G6U2XD (Intel BMC)

---

## 1. Problem Description
Deployment logs (IP address, install start, install finish) were not appearing in the BMC's System Event Log (SEL) during the Ubuntu autoinstall phase, despite the build script being configured with `ipmitool raw` commands.

---

## 2. Debugging Steps & Checklist

### Step 1: Authentication Algorithm Mismatch
- **Reason**: Remote `ipmitool` calls from the builder to the BMC were failing with `invalid authentication algorithm`.
- **Check Command**: `ipmitool -I lanplus -H 10.99.236.49 -U admin -P '...' raw 0x0a 0x44 ...`
- **Result**: Failed (Auth Error).
- **Resolution**: Added Cipher Suite `-C 17` to specify the correct RAKP-HMAC-SHA1 algorithm required by this BMC.
- **Success Command**: `ipmitool -I lanplus -H 10.99.236.49 -C 17 ...`

### Step 2: Record Type Compatibility (OEM 0xC0)
- **Reason**: We initially tried writing the 4-octet IP address in a single **OEM Record (Type 0xC0)** to save space.
- **Check Command**: `ipmitool ... raw 0x0a 0x44 0x00 0x00 0xc0 0x00... [IP Bytes]`
- **Result**: `0xCC` completion code (Invalid data field in request).
- **Conclusions**: This Mitac BMC does not support OEM-specific SEL records. It strictly enforces standard **Type 0x02 (System Event)** records, which only allow **3 bytes** of raw payload per entry.

### Step 3: Verification of Binary Presence on Target (`.90`)
- **Reason**: While the commands were now technically "correct", they still weren't logging during the actual installation.
- **Check Command**: `ssh root@10.99.236.90 'ipmitool sel list'`
- **Result**: `bash: ipmitool: command not found`.
- **Conclusion**: The primary tool for SEL logging (`ipmitool`) was never successfully installed during the automated deployment.

### Step 4: Installer Log Audit
- **Reason**: To see if the installer attempted to install `ipmitool`.
- **Check Command**: `tail -n 1000 /var/log/installer/subiquity-server-debug.log`
- **Observations**: 
  - Found `Late/run/command_7` calling `ipmitool`.
  - The script used `2>/dev/null || true`, which masked the `127 (command not found)` error as a `SUCCESS`.
  - The `apt-get install` segment at the beginning of `late-commands` showed no errors, but `ipmitool` was missing from the filesystem.

### Step 5: Build Machine Cache Audit
- **Reason**: Verify if `ipmitool` was actually bundled into the ISO.
- **Check Command**: `ls -l autoinstall/apt_cache/noble/archives/ipmitool*`
- **Result**: `No such file or directory`.
- **Insight**: The build script was failing to populate its own cache.

---

## 3. Root Cause Analysis

### The "Apt-Get Download" Bug
The ISO build script utilized `apt-get download` to fetch the mandatory `ipmitool` package and its dependencies.
- **Expectation**: `Dir::Cache` setting would place `.deb` files in `autoinstall/apt_cache/`.
- **Reality**: The `apt-get download` command always downloads to the **Current Working Directory (CWD)** regardless of the `Dir::Cache` config.
- **Consequence**: The `.deb` files stayed in a temporary directory that was deleted at the end of the script. The script's `find` command (searching the cache) found nothing.
- **Final Result**: The ISO's `pool/extra` directory was empty. When the installer tried to install `ipmitool` (especially when offline or mirror-less), it failed silently.

---

## 4. Resolution Summary

### Fix 1: Cache Population Rewrite (v2-rev9)
Modified `download_extra_packages` to explicitly move downloaded packets into the persistent cache:
```bash
if apt-get download "$pkg"; then
    mv ./*.deb "$persistent_cache/archives/"
fi
```
This ensures `ipmitool` is definitely present in `pool/extra/` on every generated ISO.

### Fix 2: Two-Part IP Logging
Because of the BMC's 3-byte limitation, implemented a two-part log for IP addresses:
- **Part 1**: Records Octets 1-2.
- **Part 2**: Records Octets 3-4.
- **Format**: Both use standard Type 0x02 to ensure 100% platform compatibility.

### Fix 3: GPG Key Paths
Corrected unescaped variables in `late-commands` that were accidentally expanding on the build host instead of the target, which had previously broken Docker/Kubernetes repository setup.

---

## 5. Verification of Final Version
After applying the above fixes, manual execution of the two-part sequence on server `.90` produced the following successful SEL entries:
```text
 10a | 03/23/2026 | 06:52:21 AM UTC | System Event | OEM System boot event | Asserted (Data: 010a63 - IP 10.99)
 10b | 03/23/2026 | 06:52:21 AM UTC | System Event | Undetermined system hardware failure | Asserted (Data: 02ec5a - IP 236.90)
```
**Conclusion**: Observability is restored and the build script is now functionally robust.
