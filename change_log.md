# Change Log - os_auto_deployment

---

## 2026-03-09: Feature: Add `--iso` Parameter to Bypass ISO Generation

**File:** `src/os_deployment/main.py` (Modified)

---

### Description

Added a new optional `--iso` command-line parameter that allows users to provide a path to a pre-built ISO file. When specified, the entire ISO generation process (autoinstall script execution) is bypassed, and the provided ISO is used directly for deployment.

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

