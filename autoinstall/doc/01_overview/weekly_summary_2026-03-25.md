# Weekly Development Summary: 2026-03-25 to 2026-04-01

**Period:** 2026-03-25 → 2026-04-01
**Total Commits:** 52
**Versions Released:** v2-rev37 through v2-rev49

---

## Overview

The week covered five major workstreams:
1. **Gen-7 / Redfish multi-gen infrastructure** — version-gated API selection, timeout tuning, PostCode clear
2. **Ubuntu 24.04 / 25.10 compatibility** — autoinstall hardening, new platform support
3. **UEFI boot flow** — `startup.nsh` integration, `UefiShell` boot target
4. **Forensic IPMI telemetry** — IP logging, duplicate marker prevention, persistent monitoring
5. **ISO build reliability** — codename detection fix, `find_disk.sh` refactor, awk escaping, parallel builds

---

## 2026-04-01 — v2-rev49: UefiShell Boot, IPMI Dedup, Non-Redfish Auth

### Boot Flow
- `reboot.py`: changed `BootSourceOverrideTarget` from `"Cd"` to `"UefiShell"` so the BMC boots into the UEFI Shell environment
- `startup.nsh`: enhanced scan loop to check for `EFI\BOOT\grub.cfg` on each filesystem before invoking `bootx64.efi`; fixed garbled error message

### IPMI Marker Dedup
- Root cause: Subiquity re-triggers `early-commands` up to 3× on some hardware (e.g., Mitac G7), causing `0x0F` (Package Pre-install Start) to appear 3 times in the BMC SEL
- Fix: lock-file mechanism in `ipmi_start_logger.py` — checks `/tmp/ipmi_marker_XX.lock` before sending; creates it on success
- Result: each deployment marker now appears exactly once per OS session

### Non-Redfish Auth Support
- `auth.py`: added `get_auth_form()` — URL-encoded `username=...&password=...` for BMCs without Redfish
- `utils.py`: extended `check_auth_valid()` with optional `redfish_supported=False` path targeting `/api/session` with query-string auth

### Other
- Added `video=1024x768` to all GRUB and ISOLINUX boot parameter lines (ensures consistent framebuffer on server hardware)
- Rolled back `umount_media()` auto-call introduced in rev48 — premature unmount caused issues on some targets

---

## 2026-03-31 — v2-rev46 / v2-rev47 / v2-rev48

### Critical Fix: Multi-line Codename Extraction (v2-rev46)
- **Bug:** `get_ubuntu_codename()` returned multi-line output that corrupted the `sources.list` heredoc, causing `E: Malformed entry 1` and blocking all package downloads on Ubuntu 22.04+ builds
- **Root cause:** the function appended extra debug lines to stdout; these were captured as part of the codename variable
- **Fix:** sanitized output to return a single clean codename string
- **Enhanced:** added automatic ISO content detection so the function can infer the codename from ISO metadata without relying on the host system
- **Reference:** `autoinstall/doc/26_codename_multiline_bug_fix.md`

### Kubernetes GPG Fix
- Resolved GPG key ordering issue in the Kubernetes repository configuration during package bundling

### UEFI Shell Integration (v2-rev47)
- Added `startup.nsh` to the EFI boot image so it executes automatically when a target boots into the UEFI Shell

### Build Script Refactor + IP Logging Fix (v2-rev48)
- Extracted `find_disk.sh` from an inline heredoc in the build script to `autoinstall/scripts/find_disk.sh` for maintainability
- Fixed `awk` variable escaping in `error-commands`: `$1`, `$2` were being expanded by the enclosing shell instead of being treated as `awk` field references, causing IP logging to always emit `0.0.0.0` on install failure
- Added automatic ISO unmount on completion (`0xAA`) and abort (`0xEE`) markers *(later reverted in rev49)*

---

## 2026-03-30 — Ubuntu 25.10, Mermaid Docs, Build Fixes

### New Platform Support
- Added Ubuntu 25.10 (`oracular`) to the supported ISO list

### Bug Fixes
- Disabled `multipathd` in `early-commands` to prevent `curtin clear-holders` crash on Ubuntu 24.04 targets
- Fixed invalid `lsblk -nk` flag (no such flag) in `find_disk.sh` — replaced with `lsblk -n`
- Added `trap` cleanup to auto-remove `WORKDIR` on build script exit

### Documentation
- Added `22_autoinstall_mermaid_charts.md`: comprehensive architecture and flow diagrams covering ISO structure, boot flow, hardware generation support, and component interactions
- Fixed multiple Mermaid syntax errors across diagrams (block-beta → graph TB, node label quoting, `\n` → `<br/>`)
- Added Installation System Architecture (Component View) diagram
- Added Claude Code documentation suite for project onboarding

---

## 2026-03-27 — Ubuntu 24.04 Hardening

### Critical Fixes
- Fixed MBR extraction step that was failing silently on 24.04 ISOs
- Added `autoinstall.yaml` symlink at `/autoinstall.yaml` → `/cdrom/autoinstall/user-data` for 24.04 Subiquity compatibility
- Fixed IP capture location: moved from inside chroot to installer host context — resolved persistent `0.0.0.0` IP logging issue
- Added post-install IPMI markers:
  - `0x06` — Package Install Start
  - `0x16` — Package Install Complete

---

## 2026-03-26 — v2-rev40 / v2-rev41 / v2-rev42: Forensic Monitoring & Build Stability

### Forensic IPMI Telemetry
- Persistent forensic logging: IPMI telemetry now survives monitor restarts and reconnects
- Gen-7 `AdditionalData` retrieval for `SENSOR_DATA` events
- IP address logging in `error-commands` for post-mortem diagnostics on failed installations
- Binary-less IP logging via `ipmi_start_logger.py` IOCTL — no `ipmitool` binary required on target
- Hardened `EventLogPrefix` constant: fixed `TypeError` (was string, accessed as dict)

### Build Stability
- Parallelized ISO build directories using a unique `BUILD_ID` suffix — allows concurrent builds without collisions
- Fixed `SIGPIPE(141)` error in `BUILD_ID` generation
- Fixed `xorriso` stdio path error by switching to absolute paths for `WORKDIR` and `OUT_ISO`
- Robust IP extraction with fallback strategies and forensic payload reconstruction

---

## 2026-03-25 — v2-rev37 / v2-rev38 / v2-rev39: Redfish Multi-Gen Infrastructure

### Version-Gated Gen-7 / Gen-6 API Selection (v2-rev39)
- `utils.get_redfish_version()`: fetches `RedfishVersion` from `GET /redfish/v1`
- `_resolve_event_gen()`: selects effective generation based on Redfish version:
  - Gen-7 + Redfish ≥ 1.17.0 → new SEL API + prefix
  - Gen-7 + Redfish < 1.17.0 → legacy EventLog API + prefix
  - Gen-6 (any) → legacy
- `LOG_FETCH_API`, `EventLogPrefix` converted from strings to generation-keyed dicts
- PostCode log clear (`clear_postcode_log`) added before reboot on Gen-7 nodes
- Timeouts increased: `REBOOT_TIMEOUT` 300s → 1200s; `PROCESS_TIMEOUT` 3600s → 7200s

### Data Corrections (v2-rev38)
- IP Part 2 SEL offset corrected: `0x04` → `0x13`
- Audit result bytes now decoded as ASCII for human-readable SEL output

### Offline Hardening (v2-rev37)
- Reverted `updates: security` → `updates: no` in autoinstall schema for offline compliance
- Added tech note `20_offline_install_hardening.md`

---

## File Change Heatmap

| File | Touches | Primary Changes |
|---|---|---|
| `autoinstall/build-ubuntu-autoinstall-iso.sh` | 15+ | Codename fix, disk script, boot params, IP logging, package bundling |
| `src/os_deployment/lib/utils.py` | 8 | Gen resolution, Redfish version, auth validation, event decoding |
| `src/os_deployment/lib/constants.py` | 5 | Gen-keyed dicts, new API constants, timeout values |
| `src/os_deployment/main.py` | 6 | Redfish version fetch, PostCode clear, umount, monitor loop |
| `autoinstall/ipmi_start_logger.py` | 4 | Multi-arg payload, binary-less IP logging, dedup lock |
| `src/os_deployment/lib/reboot.py` | 3 | PostCode clear, UefiShell boot target |
| `autoinstall/startup.nsh` | 2 | EFI boot detection, typo fix |
| `src/os_deployment/lib/auth.py` | 1 | Non-Redfish form auth |
| `autoinstall/scripts/find_disk.sh` | 1 | Extracted from heredoc, lsblk fix |
