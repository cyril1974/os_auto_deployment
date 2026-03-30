# Debug: Autoinstall Failure — multipath ABI Mismatch in curtin clear-holders

**Date:** 2026-03-30
**Target Node:** 10.99.236.95
**Kernel:** 6.17.0-5-generic (Ubuntu 25.04 "Questing")
**Symptom:** Installation aborted during partitioning with:
`FAIL: removing previous storage devices`

---

## 1. IPMI Telemetry

| Time     | Marker | Meaning                   |
|----------|--------|---------------------------|
| 09:27:52 | 0x0F   | Package Pre-install Start |
| 09:28:37 | 0x1F   | Package Pre-install Complete |
| 09:28:39 | 0x01   | OS Install Start          |
| 09:29:40 | 0x03 0x0a 0x63 | IP Part 1 (10.99) |
| 09:29:42 | 0x13 0xec 0x5f | IP Part 2 (236.95) |
| 09:29:42 | 0xEE   | **ABORTED**               |

Missing: `0x06`, `0x16`, `0xAA` — late-commands never ran.

---

## 2. Failure Chain

### Step 1 — Disk detection succeeded

`find_disk.sh` correctly found `nvme2n1` (KIOXIA 1.5T, no partition table) and
replaced `__ID_SERIAL__` with `KIOXIA_KCD81VUG1T60_44H0A02GTLSJ_1`.

Subiquity confirmed the match:
```
For match {'serial': 'KIOXIA_KCD81VUG1T60_44H0A02GTLSJ_1'},
using the first candidate from [Disk(path='/dev/nvme2n1')]
```

### Step 2 — Curtin partitioning failed at clear-holders

Curtin started the `block-meta` partitioning stage and ran `clear-holders` to
wipe any pre-existing storage stacks (LVM, RAID, multipath) on the target disk.

`multipathd` was **active and running** in the installer environment. Curtin
detected multipath support and called `multipath -r` to reload maps:

```
Detected multipath support, reload maps
Running command ['multipath', '-r'] with allowed return codes [0]
multipath: /lib/x86_64-linux-gnu/libdevmapper.so.1.02.1:
           version `DM_1_02_197' not found (required by /lib/libmultipath.so.0)
Exit code: 1
finish: cmd-block-meta/clear-holders: FAIL: removing previous storage devices
```

### Step 3 — ABI mismatch: multipath-tools vs libdevmapper

| Package | Version | Issue |
|---------|---------|-------|
| `multipath-tools` | `0.11.1-3ubuntu2` | requires `DM_1_02_197` from libdevmapper |
| `libdevmapper1.02.1` | `2:1.02.175-2.1ubuntu5` | does **not** provide `DM_1_02_197` |

`multipath -r` prints the error to stderr and exits with code 1.
Curtin only allows exit code 0 for this call → raises `ProcessExecutionError` →
`CurtinInstallError` → abort.

---

## 3. Fix Applied

Added to `early-commands` in `build-ubuntu-autoinstall-iso.sh` (before IPMI module loading):

```yaml
- systemctl stop multipathd 2>/dev/null || true
- systemctl mask multipathd 2>/dev/null || true
```

Stopping and masking `multipathd` before curtin runs prevents curtin from
detecting multipath support in `start_clear_holders_deps()`. The `multipath -r`
call is never made, and partitioning proceeds normally.

---

## 4. Comparison with Previous Failures

| Node | Failure Stage | Root Cause |
|------|--------------|------------|
| 10.99.236.93 | Filesystem config | All disks occupied — no empty disk for `__ID_SERIAL__` replacement |
| 10.99.236.95 | Curtin partitioning | `multipathd` ABI mismatch → `multipath -r` crash in clear-holders |
