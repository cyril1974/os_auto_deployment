# Change Log - os_auto_deployment

---

## 2026-03-04: Bug Fixes, Code Cleanup, and Project Structure

**Files:** `src/os_deployment/main.py` (Modified), `src/os_deployment/lib/reboot.py` (Modified), `autoinstall/build-ubuntu-autoinstall-iso.sh` (Modified)  
**New Files:** `README.md`, `config.json.template`, `pyproject.toml`, `poetry.lock`, `doc/main_usage.md`, various library modules, tests

---

### 1. Fix: Module Import Path in `reboot.py`

**Change:** Fixed incorrect import `mcup_deployer.lib.state_manager` → `os_deployment.lib.state_manager` to match the renamed project package.

---

### 2. Fix: Enable `constants` Module Import in `main.py`

**Change:** Uncommented `from .lib import constants` import, which is required for `constants.PROCESS_TIMEOUT` and other constant references used in the monitoring loop.

---

### 3. Fix: Build Script Log Output in `main.py`

**Change:** Changed `build_script` → `build_script.name` in the print statement at the ISO build step, so the log displays only the script filename instead of the full path object.

---

### 4. Fix: Remove Debug Exit (`sys.exit("DEBUG!!!")`) in `main.py`

**Change:** Removed the `sys.exit("DEBUG!!!")` statement (previously at line 298) that was blocking all code flow beyond the remote mount step. This re-enables the full deployment pipeline including reboot, monitoring, and event log processing.

---

### 5. Fix: Replace `target` with `bmcip` Variable in `main.py`

**Change:** Fixed multiple references from undefined `target` variable to the properly defined `bmcip` variable in the following calls:
- `reboot.reboot_cdrom(bmcip, config_json)`
- `utils.getTargetBMCDateTime(bmcip, auth_string)`
- `reboot.set_boot_cdrom(bmcip, auth_string)`
- `utils.check_redfish_api(bmcip, auth_string)`
- `utils.reboot_detect(bmcip, auth_string, ...)`
- `utils.getSystemEventLog(bmcip, auth_string, ...)`

---

### 6. Cleanup: Simplify Reboot Detection Block in `main.py`

**Change:** Replaced the large reboot detection handler (which included utility re-mounting, version checking, and complex state management) with a simple `pass` statement. The old logic referenced undefined variables and functions (`utility_mount`, `use_endpoint`) and was not functional in the current flow.

---

### 7. Cleanup: Remove Obsolete SUP Updating Logic in `main.py`

**Change:** Removed `sup_updating` state tracking and its related conditional blocks from the monitoring loop, as this firmware update monitoring feature is not part of the OS deployment scope.

---

### 8. Change: Default Username in `build-ubuntu-autoinstall-iso.sh`

**Change:** Changed the default `USERNAME` parameter from `admin` to `autoinstall` to avoid conflicts with system-reserved usernames on some Linux distributions.

---

### 9. New: Project Structure Files

**New files added to repository:**
- `README.md` — Project documentation
- `config.json.template` — Configuration template
- `pyproject.toml` / `poetry.lock` — Python project and dependency management
- `doc/main_usage.md` — Usage documentation for `main.py`
- `src/os_deployment/__init__.py`, `_version.py` — Package initialization
- `src/os_deployment/lib/` — Library modules (`auth.py`, `board_version.py`, `config.py`, `constants.py`, `generation.py`, `monitor.py`, `nfs.py`, `redfish.py`, `remote_mount.py`, `state_manager.py`, `utility_mount.py`, `uefi_utility/`)
- `src/os_deployment/test_function.py` — Test utilities
- `tests/` — Test suite
- `config.json` — Local configuration (runtime)

---

### Summary of All File Changes (2026-03-04)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/os_deployment/lib/reboot.py` | Modified | Fix import path `mcup_deployer` → `os_deployment` |
| `src/os_deployment/main.py` | Modified | Enable `constants` import |
| `src/os_deployment/main.py` | Modified | Fix `build_script` → `build_script.name` in log output |
| `src/os_deployment/main.py` | Modified | Remove `sys.exit("DEBUG!!!")` blocking statement |
| `src/os_deployment/main.py` | Modified | Fix `target` → `bmcip` variable references |
| `src/os_deployment/main.py` | Modified | Simplify reboot detection; remove obsolete SUP logic |
| `autoinstall/build-ubuntu-autoinstall-iso.sh` | Modified | Default username `admin` → `autoinstall` |
| `README.md` | New | Project documentation |
| `config.json.template` | New | Configuration template |
| `pyproject.toml`, `poetry.lock` | New | Python project management |
| `doc/main_usage.md` | New | Usage documentation |
| `src/os_deployment/lib/*` | New | Library modules added to repo |
| `tests/` | New | Test suite |

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

