# Technical Note #20 — Offline Installation Hardening

**Date:** 2026-03-25  
**Nodes:** `10.99.236.85` (R2520G6), `10.99.236.87` (D50DNP)  
**Status:** Resolved in `v2-rev35`, `v2-rev36`, `v2-rev37`

---

## Overview

This document describes two distinct installation failures discovered through post-mortem SSH log analysis, and the applied fixes. Both failures are related to the **offline environment** and the **Subiquity version-dependent schema validation** that enforces constraints on the `updates` field.

---

## Failure 1 — Node 10.99.236.85: `curthooks` Crash (Missing UEFI Bootloader)

### Symptom

Installation proceeded through partitioning and package setup but crashed during the `curthooks` phase with:

```
finish: cmd-install/stage-curthooks/builtin/cmd-curthooks: FAIL:
    Installing packages on target system: ['efibootmgr', 'grub-efi-amd64', 'grub-efi-amd64-signed', 'shim-signed']
Exit code: 100
```

The server left a fully partitioned target but could not finalize the bootloader installation.

### Root Cause Analysis

The Subiquity `curthooks` step validates that mandatory UEFI bootloader packages are present on the installed target. When they are absent, it tries to download them via `apt-get` from `archive.ubuntu.com`. In a **network-restricted environment**, this download fails silently in the installer log, and curtin exits with code `100`.

Evidence from `/var/log/installer/curtin-install.log`:
```
E: Failed to fetch http://archive.ubuntu.com/ubuntu/pool/main/g/grub2-unsigned/grub-efi-amd64_2.06-2ubuntu14.8_amd64.deb
   Cannot initiate the connection to archive.ubuntu.com:80 (2620:...). - connect (101: Network is unreachable)
```

### Resolution (v2-rev35 / v2-rev36)

Updated `build-ubuntu-autoinstall-iso.sh` to include mandatory UEFI bootloader packages in the default offline bundle:

**Before:**
```bash
local pkgs_to_download="${OFFLINE_PACKAGES:-ipmitool}"
```

**After:**
```bash
local pkgs_to_download="${OFFLINE_PACKAGES:-ipmitool grub-efi-amd64-signed shim-signed efibootmgr}"
```

This ensures `curthooks` finds the packages locally in `/cdrom/pool/extra/` without internet access.

---

## Failure 2 — Node 10.99.236.87: `AutoinstallValidationError` (updates: none rejected)

### Symptom

The Subiquity installer failed **immediately upon loading autoinstall configuration** before any installation steps:

```
ERROR: finish: subiquity/Updates/load_autoinstall_data: FAIL: Malformed autoinstall in 'updates' section
jsonschema.exceptions.ValidationError: 'none' is not one of ['security', 'all']
```

### Root Cause Analysis

The `updates: none` value was introduced in `v2-rev35` as a way to prevent the installer from performing network-based security updates during offline deployments. However, the Subiquity installer in **Ubuntu 22.04 (snap version `6066`)** enforces a strict JSON schema:

```json
{'enum': ['security', 'all'], 'type': 'string'}
```

The value `none` is simply **not in the allowed enum** for this version. The installer fails at startup and triggers `error-commands`, sending the `0xEE` IPMI forensic marker.

### Resolution (v2-rev37)

Reverted `updates: none` to **`updates: security`** along with two complementary offline-compatibility settings:

| Setting | Value | Purpose |
|---|---|---|
| `updates` | `security` | Satisfies strict schema validation |
| `apt.fallback` | `offline-install` | Prevents apt from failing if network is unavailable |
| `apt.geoip` | `false` | Prevents DNS lookups for geo-based mirror selection |

The combination passes schema validation while still allowing a fully offline installation.

---

## Design Discussion: Is `updates` Version-Dependent?

**Yes, it is strongly version-dependent.**

### How the `updates` Field Works

The `updates` field in `user-data` controls whether Subiquity runs `unattended-upgrades` during the installation:

| Value | Behavior |
|---|---|
| `security` | Apply available security patches from the network |
| `all` | Apply all available updates from the network |
| `none` | *(invalid in most versions)* — Disable all updates |

### Version Behavior Matrix

| Ubuntu Release | Subiquity Version | `updates: none` | `updates: security` |
|---|---|---|---|
| 22.04 LTS (Jammy) | ~6066 | ❌ Schema Error | ✅ Valid |
| 24.04 LTS (Noble) | newer | ❌ Still rejected | ✅ Valid |
| Future | unknown | Unknown | ✅ Likely valid |

> **Key finding:** The Subiquity installer does **not** accept `none` as a valid `updates` value in any currently observed version. To prevent online update downloads in offline environments, the correct approach is to combine `updates: security` with `apt.fallback: offline-install`.

### Offline Isolation Strategy

The recommended approach for a version-agnostic offline ISO:

```yaml
updates: security          # Required by schema; ignored gracefully if offline
refresh-installer:
  update: no               # Prevent sub-installer upgrades at boot
apt:
  fallback: offline-install  # Graceful fallback when apt can't reach mirrors
  geoip: false               # No DNS lookup for geographic mirror selection
  preserve_sources_list: false
  primary:
    - arches: [default]
      uri: http://archive.ubuntu.com/ubuntu
```

When the network is unavailable:
1.  `apt` will fail to fetch from `archive.ubuntu.com`.
2.  `fallback: offline-install` catches the failure and falls back to the packages already bundled in `/cdrom/pool/`.
3.  The UEFI bootloader packages (`grub-efi-amd64-signed`, `shim-signed`, `efibootmgr`) are now pre-bundled in the ISO's `/pool/extra/`, so `curthooks` finds what it needs locally.

---

## Summary of Changes

| Rev | File | Change |
|---|---|---|
| v2-rev35 | `build-ubuntu-autoinstall-iso.sh` | Added UEFI pkgs to mandatory offline bundle |
| v2-rev36 | `build-ubuntu-autoinstall-iso.sh` | Set `updates: none` (later reverted) |
| v2-rev37 | `build-ubuntu-autoinstall-iso.sh` | Reverted `updates: security`; `geoip: false` |

---

## Related Documents

- `change_log.md` — Rev 35–37 entries
- `debug_note.md` — Node `.85` and `.87` post-mortems
- `17_sel_logging_commands.md` — IPMI `0xEE` forensic marker spec
