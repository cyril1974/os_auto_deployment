# Debug: Autoinstall Failure — __ID_SERIAL__ Never Replaced

**Date:** 2026-03-30
**Target Node:** 10.99.236.93
**Kernel:** 6.17.0-5-generic (Ubuntu 25.04 "Questing")
**Symptom:** Installation aborted immediately after early-commands with error:
`{'match': {'serial': '__ID_SERIAL__'}} matched no disk`

---

## 1. IPMI Telemetry (from /var/log/ipmi_telemetry.log)

| Time     | Marker | Meaning              | Status  |
|----------|--------|----------------------|---------|
| 08:59:04 | 0x0F   | Package Pre-install Start | SUCCESS |
| 08:59:52 | 0x1F   | Package Pre-install Complete | SUCCESS |
| 08:59:55 | 0x01   | OS Install Start     | SUCCESS |
| 09:00:34 | 0x03 0x0a 0x63 | IP Part 1 (10.99) | SUCCESS |
| 09:00:36 | 0x13 0xec 0x5d | IP Part 2 (236.93) | SUCCESS |
| 09:00:36 | 0xEE   | **ABORTED**          | SUCCESS |

Missing: `0x06` (Post-Install Start), `0x16` (Post-Install Complete), `0xAA` (Completed).
The abort path (`error-commands`) ran instead of `late-commands`.

---

## 2. Subiquity Error (from /var/log/installer/subiquity-server-debug.log)

```
INFO  considering [Disk(serial='1USB', path='/dev/sda'),
                   Disk(serial='KIOXIA_KCD81PUG7T68_4E10A00B0UW3_1', path='/dev/nvme1n1'),
                   Disk(serial='KIOXIA_KCD81VUG1T60_44H0A02GTLSJ_1', path='/dev/nvme0n1'),
                   Disk(serial='Micron_7400_MTFDKBG960TDZ_213738AC44B0_1', path='/dev/nvme2n1')]
      for {'serial': '__ID_SERIAL__'}
INFO  No devices satisfy criteria [{'serial': '__ID_SERIAL__'}]
ERROR FAIL: {'match': {'serial': '__ID_SERIAL__'}} matched no disk
```

The literal string `__ID_SERIAL__` was still in the config when Subiquity ran. The
`early-commands` disk detection did not replace it.

---

## 3. Root Cause — Two Bugs

### Bug 1 (Primary): All disks have existing data — reinstall scenario

All three NVMe drives had GPT partition tables and filesystems from a previous installation:

```
nvme1n1  7T   gpt  [p1: 512M EFI] [p2: 7T ext4]
nvme0n1  1.5T gpt  [p1: 512M EFI] [p2: 1.5T ext4]
nvme2n1  894G gpt  [p1: 1G]       [p2: 893G ext4]
```

`find_disk.sh` correctly detected filesystem signatures via `wipefs` and skipped all disks.
With no empty disk found, `find_empty_disk_serial` exited with code 1 →
`__ID_SERIAL__` was never replaced → Subiquity failed.

**This is expected behavior for a reinstall scenario. The operator must wipe the
target disk before triggering a reinstall.**

### Bug 2 (Secondary): `lsblk -nk` invalid flag — partition check always returns 0

```
$ lsblk -nk -o TYPE /dev/sda
lsblk: invalid option -- 'k'
```

`-k` is not a valid `lsblk` flag. lsblk prints an error to stderr (suppressed by
`2>/dev/null`) and produces no stdout. Result:

```bash
partition_count=$(lsblk -nk -o TYPE "$device" 2>/dev/null | grep -c "part")
# Always 0 — partition check is completely disabled
```

In this failure case, the wipefs check still caught all occupied disks, so the
partition check bug did not cause additional harm. However, it is a latent bug:
if a disk had been freshly zeroed but still had leftover partition table entries,
wipefs might miss them while lsblk would correctly detect them.

**Fixed:** Changed `lsblk -nk` → `lsblk -n` in `find_disk.sh` (build script line ~430).

### Secondary observation: grub.cfg MD5 checksum mismatch

```
casper-md5check results: {'checksum_missmatch': ['./boot/grub/grub.cfg'], 'result': 'fail'}
```

The ISO's `md5sum.txt` still contains the original `grub.cfg` checksum, but we patched
the file during build. casper logs this as a failure but does not abort installation.
This is cosmetic. To fix: regenerate `md5sum.txt` after patching in the build script.

---

## 4. Fix Applied

**`build-ubuntu-autoinstall-iso.sh` line ~430:**

```sh
# Before (broken):
partition_count=$(lsblk -nk -o TYPE "$device" 2>/dev/null | grep -c "part")

# After (fixed):
partition_count=$(lsblk -n -o TYPE "$device" 2>/dev/null | grep -c "part")
```

---

## 5. Reinstall Procedure

To reinstall a node that already has data on its disks, wipe the target disk
**before** booting the autoinstall ISO:

```bash
# Identify target disk (smallest NVMe or designated install target)
lsblk -o NAME,SIZE,MODEL,SERIAL

# Wipe partition table and filesystem signatures
wipefs -a /dev/nvme2n1

# Zero the first 10MB to clear any remaining boot records
dd if=/dev/zero of=/dev/nvme2n1 bs=1M count=10
```

Then trigger the ISO boot via BMC virtual media. `find_disk.sh` will now detect
the wiped disk as empty and replace `__ID_SERIAL__` correctly.

---

## 6. Summary Table

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | All NVMe drives occupied → no empty disk → `__ID_SERIAL__` not replaced | Critical (root cause) | Operator action: wipe disk before reinstall |
| 2 | `lsblk -nk` invalid flag → partition check always returns 0 | Medium (latent bug) | Fixed in build script |
| 3 | `grub.cfg` md5sum mismatch in casper check | Low (cosmetic) | Open |
