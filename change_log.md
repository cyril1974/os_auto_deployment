# Change Log - os_auto_deployment

---

## 2026-03-24 - 2026-03-26: Forensic Telemetry Hardening and Multi-Gen Support (v2-rev35 - v2-rev40)

### Major Changes

1. **Generation-Aware Redfish Engine:**
   - Implemented `get_redfish_version()` to identify BMC firmware capabilities.
   - Added `_resolve_event_gen()` to dynamically switch between Gen-6 and Gen-7 SEL prefixes based on the Redfish version (Gate: `1.17.0`).
   - Standardized `LOG_FETCH_API` and `EventLogPrefix` as generation-keyed dictionaries in `constants.py`.
   - **Feature (Gen-7):** Automated retrieval of forensic markers from **`AdditionalDataURI`** for Gen-7 systems. The engine now detects if the `SENSOR_DATA` is stored externally and performs an authenticated GET to recover the payload for real-time monitoring.

2. **Binary-less IPMI Logging (ipmi_start_logger.py):**
   - Enhanced the Python-based IOCTL logger to support multi-byte payloads (up to 3 bytes).
   - Fully replaced `ipmitool` in the autoinstall ISO with the Python logger for:
     - OS Installation Start/Complete
     - IP Address Logging (Parts 1 & 2)
     - Storage Verification Audits (OK/ER)

3. **Observability and Forensic Accuracy:**
   - Standardized on `0x13` for IP Part 2 offset to avoid "PEF Action" label collisions in generic IPMI viewers.
   - Added ASCII decoding for the `0x05` Audit Marker (converting hex payload `4f4b` to `OK`).
   - Implemented `clear_postcode_log()` in `reboot.py` to ensure a clean forensic baseline for Gen-7 deployments.

4. **Reliability and Timeout Tuning:**
   - Doubled deployment timeouts (`REBOOT_TIMEOUT`: 1200s, `PROCESS_TIMEOUT`: 7200s) to accommodate Gen-7 hardware initialization.
   - Fixed a critical `TypeError` in `utils.py` caused by `EventLogPrefix` dictionary indexing.
   - Removed stale `boot_count` loop guards in PostCode log retrieval.

### Summary of File Changes (Recent)

| File | Change | Description |
|---|---|---|
| `src/os_deployment/lib/constants.py` | Modified | Added gen-keyed dicts for APIs and Prefixes; fixed `TypeError` |
| `src/os_deployment/lib/utils.py` | Modified | Redfish version gate logic; generation-aware event decoding |
| `src/os_deployment/lib/reboot.py` | Added | PostCode log clearing via Redfish |
| `src/os_deployment/main.py` | Modified | Integrated version detection, audit decoding, and log clearing |
| `autoinstall/ipmi_start_logger.py`| Modified | Multi-byte payload support for IP/Audit logging |
| `autoinstall/build-ubuntu-autoinstall-iso.sh` | Modified | Full transition to binary-less forensic logging |

---

## 2026-03-19: Advanced Offline Integrations (Docker/K8s) and Subiquity Fixes

**File:** `autoinstall/build-ubuntu-autoinstall-iso.sh` (Modified), `autoinstall/package_list` (Updated)

---

### Features & Fixes

1. **Docker and Kubernetes (v1.35) Offline Support:**
   - **Full Bundle Support:** The builder now automatically adds official repositories for both Docker and Kubernetes (v1.35) at build time, bundling all binary packages, their transitive dependencies, and their GPG keys into the ISO.
   - **Automatic Node Provisioning:** Updated `late-commands` to automatically set up the Kubernetes and Docker keyrings and repository source files (`/etc/apt/keyrings`, `kubernetes.list`, `docker.list`) on the target machine for a consistent post-installation state.
   - **Recursive Resolution:** Improved the dependency downloader to identify the complete recursive closure of required packages, ensuring no "level-2" libraries are missing in air-gapped installs.

2. **Subiquity Stability Fixes (Ubuntu 24.04/Noble):**
   - **Self-Update Bypass:** Disabled the `refresh-installer` update check. This prevents the frequent `TaskStatus.ERROR` failure where Subiquity would stall at boot while attempting to refresh itself in restricted network environments.
   - **Config Path Support:** Updated the automated empty-disk detection logic to support the new `/run/subiquity/cloud.autoinstall.yaml` path used in newer Ubuntu releases.
   - **Recursive Dependency Fix:** Switched to an isolated simulation-based downloader to fix binary dependency mismatches.

---

---

## 2026-03-18: Purely Offline Installation Mode via 'package_list'

**File:** `autoinstall/build-ubuntu-autoinstall-iso.sh` (Modified)

---

### Description

1. **Custom Offline Package Bundling:**
   - **Feature:** Introduced a `package_list` mechanism. The build script now looks for this file and automatically downloads all listed packages (and their full dependency chains) for the target Ubuntu version, bundling them into the ISO's `/pool/extra` directory.
   - **Offline-Only Workflow:** When `package_list` is used, the autoinstall `user-data` is dynamically reconfigured to use a **Purely Offline** installation strategy. The installer will skip all internet repositories and install directly from the bundled local files, ensuring 100% reliability in air-gapped environments.
   - **Resilience:** Guaranteed inclusion of `ipmitool` for SEL logging, regardless of whether it was explicitly listed.

---

---

## 2026-03-17: Hybrid Online/Offline Installation Strategy and Robust ISO Patching

**Files:** `autoinstall/build-ubuntu-autoinstall-iso.sh` (Modified), `/ClusterManagement/user-data` (Modified)

---

### Description

1. **Hybrid Package Installation with Internet Fallback:**
   - **Problem:** Installations on servers without internet access (`10.99.236.94`, `10.99.236.97`) crashed during the `curthooks` or `postinstall` phases because Subiquity tried to download newer package versions (like `grub-efi-amd64` or `net-tools`) from the internet.
   - **Fix:** Implemented a robust installation logic in `late-commands`. The installer now attempts to fetch latest versions from the internet but, upon failure, automatically falls back to installing version-matched `.deb` files from the local ISO pool (`/cdrom/pool/extra`).
   - **Benefit:** Guarantees 100% successful installation in both air-gapped and connected environments.

2. **Subiquity Schema Validation Fix:**
   - **Problem:** Using `updates: none` caused a "Malformed autoinstall" error on some server versions (e.g., `10.99.236.95`) because Subiquity expects specific enum values (`security`, `all`).
   - **Fix:** Reverted to `updates: security` but combined it with `refresh-installer: update: no` and a defunct mirror (127.0.0.1) as a temporary measure, then finalized to used standard mirrors with the `late-commands` fallback logic.

3. **Robust GRUB/ISOLINUX Patching:**
   - **Problem:** ISOs sometimes booted into interactive mode because the GRUB patching regex was too strict. It failed to match single quotes in menu titles or `hwe` (Hardware Enablement) kernels common in point releases (.3, .4, .5).
   - **Fix:** Updated the Python-based patching regex to handle single/double quotes, multiple spaces, and `hwe-vmlinuz` variants. Added a generic fallback match to ensure the `autoinstall` parameter is always injected.

4. **Build-Time Expansion Fix:**
   - **Problem:** Build script generated "unbound variable" errors because target-side shell variables (like `\$IP`) were being expanded by the host build environment during ISO creation.
   - **Fix:** Ensured all shell variables in the `user-data` heredoc are correctly escaped with backslashes.

5. **Fixed User-Data YAML Syntax:**
   - **Problem:** Booting to interactive UI because `early-commands:` key was missing in the autoinstall config.
   - **Fix:** Restored the missing key and verified indentation.

---

---

## 2026-03-16: Fix IP Parsing Syntax Error and Shellcheck Warnings

**File:** `autoinstall/build-ubuntu-autoinstall-iso.sh` (Modified)

---

### Description

1. **IP Address Parsing Syntax Error (Dash Compatibility):**
   - **Problem:** The `late-commands` logic used Bash-specific herestrings (`<<<`) to parse the system IP address into octets. On Ubuntu, `/bin/sh` is `dash`, which does not support this syntax, causing a `non-zero exit status 2` (syntax error) at the very end of the installation.
   - **Fix:** Rewrote IP parsing using portable `awk` and `printf` commands that work in any POSIX-compliant shell.
   - **Benefit:** The installation now completes successfully without halting on the final OEM SEL logging step.

2. **Shellcheck Cleanup:** Fixed several "masking return value" warnings by separating variable declaration and assignment.

---

## 2026-03-16: Fix Malformed Autoinstall in 'updates' Section

**File:** `autoinstall/build-ubuntu-autoinstall-iso.sh` (Modified)

---

### Description

1. **Malformed 'updates' Section:**
   - **Problem:** Reverting to `updates: none` on 2026-03-09 caused a "Malformed autoinstall" validation error on newer Subiquity versions (specifically Ubuntu 24.04 and some 22.04 updates). The installer would halt and drop to a shell.
   - **Fix:** Reverted `updates: none` back to `updates: security`.
   - **Note:** To avoid long installation hangs during unattended upgrades when offline, the configuration relies on `apt: fallback: offline-install` (and optionally could use an empty security URI, though `offline-install` is generally sufficient).

---

## 2026-03-09: Feature: Add `--iso` Parameter to Bypass ISO Generation

**File:** `src/os_deployment/main.py` (Modified)

---

### Description

1. **Added a new optional `--iso` command-line parameter that allows users to provide a path to a pre-built ISO file.** When specified, the entire ISO generation process (autoinstall script execution) is bypassed, and the provided ISO is used directly for deployment.

Additionally, `-O/--os` is now **conditionally required**: it is only required when `--iso` is not provided. When `--iso` is used, `-O` can be omitted since no ISO generation is needed.

### Behavior

| Scenario | Action |
|---|---|
| `--iso` **not provided**, `-O` **provided** | Normal flow: generates a custom autoinstall ISO via `build-ubuntu-autoinstall-iso.sh` |
| `--iso` **not provided**, `-O` **not provided** | Exits with error: `-O/--os is required when --iso is not provided.` |
| `--iso /path/to/file.iso` (with or without `-O`) | Validates the file exists → bypasses ISO generation → uses the provided ISO |
| `--iso /invalid/path.iso` | Exits with error: `Pre-built ISO not found: /invalid/path.iso` |
| `--iso /path/to/directory/` | Exits with error: `Pre-built ISO path is not a file: /path/to/directory/` |

### Usage Example

```bash
# Normal flow (generates ISO, -O is required)
os-deploy -B 10.x.x.x -BU admin -BP password -N 10.y.y.y -O ubuntu-22.04.2-live-server-amd64

# With pre-built ISO (skips generation, -O is optional)
os-deploy -B 10.x.x.x -BU admin -BP password -N 10.y.y.y \
    --iso ./output_custom_iso/ubuntu_22.04.2_autoinstall_20260306.iso
```

### Output (when `--iso` is used)

```
Option --iso is set: ./output_custom_iso/ubuntu_22.04.2_autoinstall_20260306.iso
[2026-03-09T11:00:00] *** Bypassing ISO generation (--iso provided) ***
[2026-03-09T11:00:00] Using pre-built ISO: /absolute/path/to/iso
```

---

## 2026-03-03: Add BMC Authentication Validation

**Files:** `src/os_deployment/lib/utils.py` (Modified), `src/os_deployment/main.py` (Modified)

---

### 1. Feature: `check_auth_valid()` Function in `utils.py`

**Change:** Added a new function `check_auth_valid(target, auth)` that validates BMC credentials by sending a GET request to the Redfish endpoint `/redfish/v1/SessionService`.

**Key behaviors:**
- Sends an authenticated GET request to `/redfish/v1/SessionService`
- HTTP 200 → returns `{"status": "ok", "message": "Authentication is valid"}`
- HTTP 401 → returns `{"status": "unauthorized", "message": "Authentication failed: invalid username or password"}`
- No response / exception → returns `{"status": "error", "message": "..."}`
- Distinct from `check_redfish_api()` which only checks BMC reachability at the unauthenticated `/redfish/v1` root endpoint

---

### 2. Feature: Early Auth Validation in `main.py`

**Change:** Added BMC authentication validation step in `main()` **before** the ISO generation process. This ensures invalid credentials are caught early, before the time-consuming ISO build.

**Flow:**
1. `auth_string` is now created earlier in the flow (moved up from post-NFS-deploy)
2. Calls `utils.check_auth_valid(bmcip, auth_string)` against `/redfish/v1/SessionService`
3. If valid → prints `OK` and continues to ISO generation
4. If invalid → prints `FAIL` and exits with error message including guidance to check parameters or `config.json`

**Output examples:**
```
[2026-03-03T05:00:00] Validating BMC authentication (10.x.x.x) ....OK
```
```
[2026-03-03T05:00:00] Validating BMC authentication (10.x.x.x) ....FAIL
BMC Auth Validation Failed: Authentication failed: invalid username or password (Please check your parameter or config.json)
```

---

### 3. Cleanup: Remove Duplicate `auth_string` Assignment

**Change:** Removed the redundant `auth_string = auth.get_auth_header(bmcip, config_json)` that was previously located after the NFS deployment step, since `auth_string` is now set earlier during the auth validation step.

---

### 4. Cleanup: Suppress Config Debug Output

**Change:** Commented out `print(config_json)` after config loading to avoid exposing credentials and config data in console output.

---

### Summary of All File Changes (2026-03-03 - Auth Validation)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/os_deployment/lib/utils.py` | Modified | Added `check_auth_valid()` function using `/redfish/v1/SessionService` |
| `src/os_deployment/main.py` | Modified | Added early BMC auth validation before ISO generation |
| `src/os_deployment/main.py` | Modified | Moved `auth_string` assignment earlier; removed duplicate |
| `src/os_deployment/main.py` | Modified | Commented out config debug print |
| `change_log.md` | New | This change log |

---

## 2026-03-03: Change Boot Target from UEFI Shell to CD-ROM

**Files:** `src/os_deployment/lib/reboot.py` (Modified), `src/os_deployment/main.py` (Modified)

---

### 5. Refactor: Rename `_set_boot_uefi` → `_set_boot_cdrom` in `reboot.py`

**Change:** Renamed the internal function `_set_boot_uefi()` to `_set_boot_cdrom()` and changed the Redfish `BootSourceOverrideTarget` from `"UefiShell"` to `"Cd"`. All related log messages updated from "UEFI" to "CD-ROM".

**Redfish payload change:**
```json
// Before
{"Boot": {"BootSourceOverrideTarget": "UefiShell", "BootSourceOverrideEnabled": "Once"}}

// After
{"Boot": {"BootSourceOverrideTarget": "Cd", "BootSourceOverrideEnabled": "Once"}}
```

---

### 6. Refactor: Rename `reboot_uefi` → `reboot_cdrom` in `reboot.py`

**Change:** Renamed the public function `reboot_uefi()` to `reboot_cdrom()` and updated its internal call to use `_set_boot_cdrom()`.

---

### 7. Update: Enable `reboot` Module Import and Update Initial Reboot Call in `main.py`

**Changes:**
- Uncommented `from .lib import reboot` import
- Updated "Reboot to UEFI" section header to "Reboot to CD-ROM"
- Changed `reboot.reboot_uefi(target, config_json)` → `reboot.reboot_cdrom(target, config_json)` at the initial reboot step
- Changed print message to use `bmcip` instead of `target`

---

### ⚠️ Known Issues (Needs Follow-Up)

| Location | Issue |
|----------|-------|
| `reboot.py` line 125–131 | `set_boot_uefi()` wrapper still calls `_set_boot_uefi()` which no longer exists — will cause `NameError` |
| `main.py` line 329, 384 | Still reference `reboot.set_boot_uefi()` (should be updated to CD-ROM equivalent) |
| `main.py` line 382, 427 | Still reference `reboot.reboot_uefi()` (should be `reboot.reboot_cdrom()`) |
| `main.py` lines 305+ | Variable `target` used but never defined — should be `bmcip` (currently unreachable due to `sys.exit("DEBUG!!!")` on line 298) |

---

### Summary of All File Changes (2026-03-03 - Boot Target)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/os_deployment/lib/reboot.py` | Modified | Renamed `_set_boot_uefi` → `_set_boot_cdrom`; boot target `UefiShell` → `Cd` |
| `src/os_deployment/lib/reboot.py` | Modified | Renamed `reboot_uefi` → `reboot_cdrom` |
| `src/os_deployment/main.py` | Modified | Uncommented `reboot` import; updated initial reboot call to `reboot_cdrom` |
| `change_log.md` | Modified | Added boot target refactor entries |
