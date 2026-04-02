# Debug: Ubuntu 18.04 Preseed Disk Detection & Installation Failures

**Date:** 2026-04-02
**Scope:** `autoinstall/build-ubuntu-autoinstall-iso.sh`, `autoinstall/scripts/find_disk_1804.sh`

---

## Summary

During Ubuntu 18.04 preseed automated installation, a series of bugs were discovered and resolved through iterative hardware testing. The final result is a fully automated, non-interactive 18.04 installation that mirrors the 20.04+ autoinstall behaviour including IPMI SEL logging, offline package installation, and verified disk selection.

---

## Bug 1 — Wrong ISO output path in xorriso (18.04 branch)

**Symptom:** Built ISO was created at a wrong path or not found after build.

**Root cause:** The 18.04 xorriso command used `-o "../$OUT_ISO"` but `$OUT_ISO` is already an absolute path, producing `..//home/...`.

**Fix:** Changed to `-o "$OUT_ISO"` to match the 20.04+ branch.

---

## Bug 2 — ISOLINUX patching silently skipped

**Symptom:** BIOS-booting machines showed the interactive menu instead of auto-installing.

**Root cause:** `ISOLINUX_CFG_FILES` was hardcoded to `./workdir_custom_iso/isolinux/...` without the `${BUILD_ID}` component. The `[ -f "$cfg" ]` check always failed silently.

**Fix:** Changed to `"$WORKDIR/isolinux/..."`.

---

## Bug 3 — `preseed/early_command` failed with exit code 2 (`<<<` not in dash)

**Symptom:** Red screen — "Failed to run preseeded command ... exit code 2"

**Root cause:** `debconf-set-selections <<< "..."` uses bash here-string syntax. The d-i environment runs `/bin/sh` which is `dash` — `<<<` is not supported.

**Fix:** Replaced with `echo "..." | debconf-set-selections`.

---

## Bug 4 — Disk detection ran before storage drivers were loaded

**Symptom:** `find_disk_1804.sh` found no disks — only `loop*` and `sr0` visible in `/sys/block/`.

**Root cause:** `preseed/early_command` runs **before** `hw-detect`. Storage drivers are not loaded at this point so NVMe/SATA disks are not yet present in `/sys/block/`.

**Fix:** Moved disk detection to `partman/early_command` which runs **after** `hw-detect` when all storage drivers are loaded. IPMI module loading and SEL markers remain in `preseed/early_command`.

```
preseed/early_command  → modprobe IPMI, SEL markers (0x0F, 0x1F, 0x01)
partman/early_command  → disk detection, debconf-set
```

---

## Bug 5 — `lsblk` and `wipefs` not available in d-i environment

**Symptom:** `find_disk_1804.sh` exited immediately — `lsblk: not found`.

**Root cause:** The original script used `lsblk` and `wipefs` which are not present in the Ubuntu 18.04 d-i minimal environment.

**Fix:** Rewrote `find_disk_1804.sh` using only d-i-safe tools:

| Operation | Old (broken) | New (d-i safe) |
|---|---|---|
| List whole disks | `lsblk -nd` | `ls /sys/block/` + filter loop/ram/sr/fd |
| Disk size | `lsblk -ndb -o SIZE` | `/sys/block/<name>/size` × 512 |
| Partition check | `lsblk -n -o TYPE` | `ls /sys/block/<name>/` matching `<name>[0-9]` |
| Filesystem signatures | `wipefs` | `blkid` |
| Mount check | not present | `grep /proc/mounts` |

Also removed the `dd` first-1MB zero-data check — it wrongly rejected disks with remnant GRUB bootstrap code from a previous failed install attempt. Partman wipes the disk regardless.

---

## Bug 6 — `tee: not found` in d-i environment

**Symptom:** Script aborted on `| tee /dev/console`.

**Root cause:** `tee` is not available in the d-i 18.04 minimal shell.

**Fix:** Added `_con()` helper that writes directly `> /dev/console`. All stdout redirected to log file via `exec > "$LOG" 2>&1`.

---

## Bug 7 — `exec > "$LOG"` swallowed the script's stdout, breaking command substitution

**Symptom:** `disk=$(sh /cdrom/find_disk_1804.sh)` always returned empty even though the script correctly found `/dev/nvme1n1` (confirmed via `/tmp/find_disk_1804.log`).

**Root cause:** `exec > "$LOG" 2>&1` at the top of `find_disk_1804.sh` redirects all stdout to the log file. `$()` command substitution captures stdout — but stdout was already redirected away, so the caller received nothing.

**Fix:** The script writes its result to `/tmp/find_disk_1804.result`. The caller reads from that file:
```sh
sh /cdrom/find_disk_1804.sh
disk=$(cat /tmp/find_disk_1804.result 2>/dev/null)
```

---

## Bug 8 — `debconf-set-selections` did not update live partman session

**Symptom:** "No root file system is defined" — partman ran but did not use the detected disk.

**Root cause:** `debconf-set-selections` writes to the flat preseed database. By the time `partman/early_command` runs, partman had already initialised its debconf session and cached the value from preseed parse time (`/dev/sda` hardcoded). The override did not propagate into the live session.

**Fix:**
1. Removed the hardcoded `d-i partman-auto/disk string /dev/sda` from preseed.cfg.
2. Replaced `debconf-set-selections` with `. /usr/share/debconf/confmodule` + `db_set` which talks directly to the running debconf daemon:
```sh
. /usr/share/debconf/confmodule
db_set partman-auto/disk "$disk"
db_set grub-installer/bootdev "$disk"
```

---

## Bug 9 — `passwd/user-password-password` is not a valid preseed key

**Symptom:** Interactive "Choose a password for the new user" dialog appeared during installation.

**Root cause:** The key `passwd/user-password-password` does not exist in d-i debconf. d-i ignored it and fell through to the interactive prompt.

**Fix:** Changed to the correct key `passwd/user-password`.

---

## Additional Changes Made During This Session

### Offline package download extended to 18.04
- Removed the `IS_1804 != true` guard from `download_extra_packages()`.
- Packages are now bundled into `pool/extra/` for all Ubuntu versions.
- Preseed `late_command` installs bundled `.deb` files via `dpkg -i` inside the chroot.
- `pkgsel/include` is reduced to `openssh-server` only when `OFFLINE_PACKAGES` is set (remaining packages come from the bundle).

### IPMI SEL logging ported to 18.04
Full marker sequence now matches 20.04+ behaviour:

| Marker | Event | Hook |
|---|---|---|
| `0x0F` | Package Pre-install Start | `preseed/early_command` |
| `0x1F` | Package Pre-install Complete | `preseed/early_command` |
| `0x01` | OS Installation Start | `preseed/early_command` |
| `0x06` | Post-Install Start | `preseed/late_command` |
| `0x16` | Post-Install Complete | `preseed/late_command` |
| `0x03`/`0x13` | IP Address (octets 1–2 / 3–4) | `preseed/late_command` |
| `0xaa` | OS Installation Completed | `preseed/late_command` |
| `0x05` `OK`/`ER` | Disk Verification Result | `preseed/late_command` |
| `0xEE` | Abort / No disk found | error path |

### CDROM enabled as APT source
Changed `d-i apt-setup/cdrom/set-first` from `false` to `true` so offline package installs succeed without a network mirror.

### network-console added for remote debugging
Added `d-i anna/choose_modules string network-console` — enables SSH into the installer during installation:
```sh
ssh installer@<IP>    # password: configured PASSWORD
```

### Download progress bar
Replaced per-package `echo` with an in-place progress bar using ANSI escape codes (`\033[1A\033[2K`). `apt-get download` stdout/stderr fully suppressed to prevent output leaking through the bar.
