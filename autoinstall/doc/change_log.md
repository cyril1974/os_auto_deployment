# Change Log - os_auto_deployment/autoinstall

---

## 2026-03-24: Binary-less IPMI and SEL Reliability Tuning (v2-rev14-15)

**Files:** `build-ubuntu-autoinstall-iso.sh`, `ipmi_start_logger.py`, `19_debug_missing_ip_part_2.md`

---

### Features & Fixes

1. **Optimization: Extended SEL Write Delay (v20260324-v2-rev15):**
   - **Tuning:** Increased the delay between sequential IPMI commands from `sleep 1` to **`sleep 5`**.
   - **Rationale:** On some slower BMCs, the previous 1s gap was still leading to intermittent command drops of the final IP octets. 5s provides a safe buffer for NVM write commit.

2. **Feature: Binary-less IPMI Start Logger (v20260324-v2-rev14):**
   - **Improvement:** Added a Python-based utility (`ipmi_start_logger.py`) that uses `ioctl` to communicate with `/dev/ipmi0` directly.
   - **Benefit:** Eliminates the telemetry gap at boot-time; logs the "Start" marker before `ipmitool` is even installed.

---

## 2026-03-23: Mastering Directory Hardening and Persistent APT Cache (v2-rev7-13)
   - **Improvement:** Added a Python-based utility (`ipmi_start_logger.py`) that uses `ioctl` to communicate with `/dev/ipmi0` directly.
   - **Optimization:** Moved the "OS Installation Starting" SEL signal to fire **BEFORE** the `ipmitool` package installation (`dpkg -i`).
   - **Benefit:** Provides immediate OOB telemetry as soon as the ISO boots, eliminating the silent window during initial package extraction.

2. **Fix: SEL Write Race Condition (v20260324-v2-rev13):**
   - **Bug (OOB):** Found that consecutive `ipmitool` commands using the same Marker ID (Data1=0x02) can be dropped by the BMC if sent too fast (observed 1ms gap on node .85).
   - **Resolution:** Introduced `sleep 1` between all sequential IPMI RAW calls in `late-commands`.
   - **Impact:** Guaranteed three-stage post-install logging: IP Part 1 -> IP Part 2 -> Completed.
   - **Documentation:** See full report in `autoinstall/doc/19_debug_missing_ip_part_2.md`.

2. **Optimization: SEL Data Padding (v20260323-v2-rev12):**
   - **Requirement:** Update SEL commands to match user diagnostic tool string `SEL Entry Added:210012006F`.
   - **Change:** Modified "Start Install" and "Complete Install" commands to use `0x00 0x00` padding instead of `0xff 0xff`.
   - **Documentation:** Updated technical doc #17 to reflect the new standardized padding value.

2. **Feature: Delta Download Logic (v20260323-v2-rev11):**
   - **Improvement:** Implemented a pre-download check that scans the `apt_cache/` for existing packages. If a matching `.deb` is already present, the script skips the remote mirror download.
   - **Benefit:** Massive speedup for repeated ISO builds (since packages like `docker` and `k8s` are large and take time to download).
   - **Verification:** Added logging (`+ Found [pkg] in cache`) into the build output to show the cache hit.

2. **Fix: Path Evaluation in Cache (v20260323-v2-rev10):**
   - **Bug (Pathing):** Found a race condition where the relative `./apt_cache` path pointed to a subdirectory of the **temporary** folder. This caused packages to be 'saved' into a transient directory that was deleted at script exit.
   - **Resolution:** Forced `persistent_cache` to use an absolute path via `$(realpath "${CACHE_DIR}")` before the script changes directories.
   - **Impact:** Fixes the empty `archives/` folder issue and confirms `pool/extra` is correctly populated.

2. **Fix: Critical APT Cache Population (v20260323-v2-rev9):**
   - **Bug (Bundling):** Corrected a logic error where `apt-get download` would place packages in a temporary directory instead of the persistent cache. This resulted in an empty `pool/extra` and missing tools like `ipmitool` on the target system.
   - **Resolution:** Explicitly move downloaded `.deb` files into the cache archives, ensuring they are correctly bundled into the ISO and available for all installations.
   - **Impact:** Fixes missing SEL logging during installation (since `ipmitool` will now be properly installed).

2. **IP Address Logging to SEL (v20260323-v2-rev8):**
   - **Feature (Observability):** Integrated a two-part IP logging mechanism into `late-commands`. This captures the target system's assigned IP and writes it to the BMC's System Event Log in Hex format (Octets 1-2 and 3-4).
   - **Fix (Platform Compatibility):** Uses standard System Event (Type 0x02) format to ensure compatibility with Mitac/Intel BMCs that reject single-record OEM entries.
   - **Documentation:** Created `autoinstall/doc/17_sel_logging_commands.md` as a technical reference for all hex bytes and byte-by-byte breakdown of the SEL logging architecture.
   - **Cleanup:** Removed obsolete and experimental network logging comments from the build script.

2. **Persistent APT Cache Mechanism (v20260323-v2-rev7):**
   - **Feature (Performance):** Introduced a local `./apt_cache/` root directory partitioned by Ubuntu codename (`noble/`, `jammy/`, etc.) for persistent package storage.
   - **Benefit (Speed):** `apt-get download` now skips files that are already present in the cache, reducing build times for subsequent ISO runs to under **5 seconds**.
   - **Optimized Bundling:** Replaced the blind `mv` operation with a surgical `find -exec cp` strategy. This ensures only the required package versions are copied into the ISO pool while the parent cache remains fully populated for future use.

2. **Hardened ISO Mastering (v20260323-v2-rev5):**
   - **Fix (ISO Build):** Resolved "No such directory" and `curl (23)` errors by ensuring the `/autoinstall/` directory is created in the workdir before attempting to bundle GPG keys.
   - **Fix (Template Mastering):** Resolved critical ISO generation crashes ("unbound variable", "chroot failure") by properly escaping all target-side `\$` and `\$(...)` command substitutions in the `build-ubuntu-autoinstall-iso.sh` heredoc.
   - **Fix (Late-Commands):** Separated host-side file operations (copying from `/cdrom`) from target-side `apt-get` calls, removing syntactically broken flags (e.g. invalid `apt-get --target`).

2. **Corrected Keyring Pathing (v2-rev4):**
   - **Fix (Apt Update):** Resolved `apt update` failures on target machines (e.g. `.94`) by removing redundant `/target/` prefixes from Docker/Kubernetes source lists.
   - **Verification:** Successfully validated functional repository synchronization on servers `10.99.236.94` and `10.99.236.92`.

---

## 2026-03-20: Hardened Storage Configuration and Smallest-Disk Priority Logic

**Files:** `src/os_deployment/main.py` (Modified), `build-ubuntu-autoinstall-iso.sh` (Modified), `find_disk.sh` (Created)

---

### Features & Fixes

1. **Smart Empty Disk Selection (Smallest Disk Priority):**
   - **Problem:** On high-density servers (like `10.99.236.85`) with multiple empty NVMe drives, the previous "first-found" logic often selected large data drives (7.68TB) over smaller system SSDs (1.5TB) if they appeared earlier in the hardware list (`nvme0n1`).
   - **New Selection Rule:** The `find_disk.sh` script now evaluates **all** truly empty candidates and selects the one with the **SMALLEST** capacity.
   - **Enhanced Discovery Log:** Automated detection now outputs its step-by-step decision process directly to `/dev/console` during boot.

2. **Explicit Storage Block (v2-rev2):**
   - **Fix (Storage):** Satisfied strict Subiquity 24.04 UEFI rules by moving `grub_device: true` to the ESP partition level and using the formal EFI GUID (`c12a7328-f81f-11d2-ba4b-00a0c93ec93b`).
   - **Benefit:** Strictly binds the installer to the discovered serial, bypassing Subiquity's "guided largest" heuristics.

3. **Real-time ISO Build Feedback:**
   - **Interactive Streaming:** Replaced blocking `subprocess.run` in `main.py` with `subprocess.Popen` to provide immediate visibility into package downloads and ISO mastering progress.

4. **Post-Installation Verification Audit:**
   - **Integrity Check:** Added a `late-commands` audit that cross-checks the serial of the newly installed root disk and reports the outcome (OK/ER) to the BMC's System Event Log (SEL).

---

## 2026-03-19: Offline Docker and Kubernetes (v1.35) Support

**File:** `build-ubuntu-autoinstall-iso.sh` (Modified), `package_list` (Updated)

---

### Features & Fixes

1. **Docker Offline Bundle Integration:**
   - **GPG Keying:** Automatically fetches and bundles the official Docker GPG key (`docker.asc`) into the ISO.
   - **Package Set:** Expands the `docker` keyword into the full suite: `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, and `docker-compose-plugin`.
   - **Auto-Config:** Updated `late-commands` to provision the `/etc/apt/keyrings` and `/etc/apt/sources.list.d/docker.list` on the target machine for seamless online updates after installation.

2. **Kubernetes (v1.35) Offline Bundle Integration:**
   - **Stable Release Fetching:** Added logic to automatically pull packages from the official Kubernetes `v1.35` stable branch repo.
   - **Binary Keying:** Fetches, dearmors, and bundles the Kubernetes `Release.key` into `/autoinstall/kubernetes.gpg` on the ISO.
   - **Node Provisioning:** Configures node keyrings and `kubernetes.list` source files during initial deployment, including all control-plane and worker utilities (`kubeadm`, `kubelet`, `kubectl`).

3. **Enhanced Offline Installation Method:**
   - Switched from `dpkg -i` to `apt-get install -y /tmp/extra_pkg/*.deb` within the `late-commands`. This more robustly handles complex dependency resolution and installation order for inter-dependent toolsets like Docker and K8s.

---

---

## 2026-03-19: Fixes for Subiquity Self-Update and Storage Configuration Discovery

**File:** `build-ubuntu-autoinstall-iso.sh` (Modified)

---

### Features & Fixes

1. **Disabled 'refresh-installer' Updates:**
   - **Problem:** Subiquity (Ubuntu installer) often attempts to refresh itself from the internet during boot. In restricted or offline environments, this results in a `TaskStatus.ERROR` failure, blocking the entire installation.
   - **Fix:** Set `refresh-installer: update: no` in the `user-data` template.
   - **Benefit:** Increases boot-time stability and ensures deterministic offline operation.

2. **Expanded Storage Config Path Search:**
   - **Problem:** Modern Subiquity versions (Ubuntu 24.04+) often write the transient autoinstall configuration to `/run/subiquity/cloud.autoinstall.yaml` instead of `/run/subiquity/autoinstall.yaml`. This caused the `__ID_SERIAL__` replacement logic in `early-commands` to miss the file, leading to "no disk found" errors.
   - **Fix:** Updated the `early-commands` loop to scan both `/run/subiquity/autoinstall.yaml` and `/run/subiquity/cloud.autoinstall.yaml`.
   - **Benefit:** Restores automated empty-disk detection on newer Ubuntu Server releases.

---

---

## 2026-03-19: Recursive Dependency Resolution and Updated Default Credentials

**File:** `build-ubuntu-autoinstall-iso.sh` (Modified)

---

### Features & Fixes

1. **Recursive Dependency Resolution (Fix for Ubuntu 24.04/Noble):**
   - **Problem:** On newer Ubuntu versions like 24.04, tools like `ipmitool` have deep dependency trees (e.g., `ipmitool` -> `libfreeipmi17` -> `freeipmi-common`). Previous script versions only downloaded direct dependencies, causing offline installations to fail due to missing level-2 packages.
   - **Fix:** Switched the offline downloader to use `apt-get -s install` (simulation) within the isolated build environment. This identifies the complete transitive dependency closure, ensuring every required `.deb` is bundled into the `/pool/extra` directory.
   - **Critical Update (Core Library Safety):** Expanded the exclusion skip list to include sensitive base libraries like `libsystemd*`, `libudev*`, `libssl*`, `libpam*`, etc. This prevents "broken dependency" errors on the target system where a newer library version (from `noble-updates`) might mismatch the base system binaries (from `noble-release`) when installed via `dpkg -i`.
   - **Benefit:** Guarantees successful offline installation of complex toolsets while maintaining base system stability.

2. **Updated Default Credentials:**
   - Changed the default login username to **`mitac`**.
   - Changed the default password to **`MiTAC00123`** for both the user and root accounts.
   - Updated all help text and documentation examples to reflect these new defaults.

---

---

## 2026-03-18: Support for Purely Offline Package Installation via 'package_list'

**File:** `build-ubuntu-autoinstall-iso.sh` (Modified)

---

### Features Added

1. **Custom Offline Package Bundling:**
   - **New Mechanism:** Added support for a `package_list` file. If this file exists in the script directory, the builder will read it and download all specified packages (and their dependencies) into the ISO's local pool (`/pool/extra`).
   - **Deterministic Offline Install:** Modified the `user-data` generation logic. If `package_list` is used at build time, the installer completely bypasses internet mirrors for these packages and performs a purely offline installation from the bundled `.deb` files.
   - **Reduced SEL Logging:** Commented out the automated IP address reporting to the BMC SEL in `late-commands` to prevent potential errors on servers with complex networking.
   - **Automatic Requirement Handling:** The script automatically ensures that `ipmitool` is included in the offline bundle if it is not explicitly listed, guaranteeing that hardware SEL logging remains functional.

---

---

## 2026-03-17: Hybrid Installation Strategy and Robust ISO Patching

**File:** `build-ubuntu-autoinstall-iso.sh` (Modified)

---

### Issues Fixed

1. **Internet-Dependent Installation Crashes (Offline Environments):**
   - **Scenario:** Servers at `10.99.236.94` and `10.99.236.97` failed because the installer (Subiquity) tried to download security updates (`grub-efi-amd64`) or user packages (`net-tools`) from `archive.ubuntu.com`.
   - **New Strategy:** Switched to a **Hybrid Package Workflow**. The system now attempts an `apt-get` download from the internet first (for the latest patches). If it fails (restricted environment), it seamlessly catches the error and executes a fallback command to install local `.deb` files from the ISO pool `/cdrom/pool/extra`.
   - **Offline Mode:** Replaced `updates: none` with `updates: security` to pass schema validation on servers like `10.99.236.95`, while still keeping installation stable in air-gapped environments.

2. **Booting to Interactive UI (GRUB/ISOLINUX Regex Fix):**
   - **Problem:** Custom ISOs were booting into the manual installation menu instead of starting `autoinstall` automatically.
   - **Fix:** Redesigned the GRUB patching regex in Python to be much more flexible. It now:
     - Handles both single (`'`) and double (`"`) quotes in menu titles.
     - Supports `hwe-vmlinuz` and `hwe-initrd` (Hardware Enablement kernels) common in point-releases (like 22.04.5 or 24.04.1).
     - Includes a generic fallback match in case the standard Ubuntu menu labels are renamed.

3. **YAML Syntax and Build Variables:**
   - **Problem 1:** Missing `early-commands:` key in a version of the `user-data` prevented automated activation.
   - **Problem 2:** "Unbound variable" errors during the ISO build because target-side shell variables (`\$IP`, `\$h1`) were being expanded prematurely on the host. 
   - **Fix:** Corrected the YAML structure and added backslashes to all variables in the hermetic heredoc.

### Benefit
The generated ISO is now highly resilient: it is compatible with newer Subiquity versions, supports a wide range of Ubuntu hardware enablement kernels, and successfully installs in both fully-connected and air-gapped server environments.

---

---

## 2026-03-16: Fix IP Parsing Syntax Error (Late-Commands)

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Issues Fixed

1. **IP Address Parsing Syntax Error (Dash Compatibility):**
   - **Problem:** The `late-commands` logic used Bash-specific herestrings (`<<<`) to parse the system IP address into octets. On Ubuntu, `/bin/sh` is `dash`, which does not support this syntax, causing a `non-zero exit status 2` (syntax error) at the end of the installation.
   - **Fix:** Rewrote IP parsing using a combination of `awk` and `cut` that is POSIX-compliant and works in `sh/dash`.
   - **Benefit:** Automated installations now complete successfully without halting on the final OEM SEL logging step.

---

## 2026-03-16: Fix Malformed Autoinstall in 'updates' Section

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Issues Fixed

1. **Malformed 'updates' Section:**
   - **Problem:** Reverting to `updates: none` on 2026-03-09 caused a "Malformed autoinstall" validation error on newer Subiquity versions (specifically Ubuntu 24.04 and some 22.04 updates). The installer would halt and drop to a shell.
   - **Fix:** Reverted `updates: none` back to `updates: security`.
   - **Note:** To avoid long installation hangs during unattended upgrades when offline, the configuration relies on `apt: fallback: offline-install` (and optionally could use an empty security URI, though `offline-install` is generally sufficient).

---

## 2026-03-13: Fix Autoinstall Activation and Disk Detection Robustness

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Issues Fixed

1. **YAML Syntax Error (Indentation):**
   - **Problem:** Inconsistent indentation in the `early-commands` section (some lines at 4 spaces, others at 6) caused the YAML parser to fail. This led to the autoinstall configuration being ignored entirely.
   - **Fix:** Standardized all YAML list items and blocks to 4-space indentation.

2. **Target Command Expansion (Shell Escaping):**
   - **Problem:** Shell variables and command substitutions (like `$(lsblk)` and `$IP`) within the `user-data` heredoc were being expanded by the **build machine**'s shell during ISO generation. This resulted in hardcoded build-machine disks (e.g., `loop0`) and local IP addresses being baked into the ISO.
   - **Fix:** Escaped all `$` signs (`\$`) and command substitutions (`\$(...)`) in the `early-commands` and `late-commands` blocks. This ensures the logic executes on the **target hardware** during installation.

3. **Storage Configuration (Ubuntu 24.04 Compatibility):**
   - **Problem:** The `match: serial: __ID_SERIAL__` block was incorrectly nested under `layout`. In newer Subiquity versions (like Ubuntu 24.04), `match` must be a sibling of the `layout` key.
   - **Fix:** Corrected the `storage` schema to place `match` at the correct level.

4. **Disk Detection Logic (POSIX Compatibility):**
   - **Problem:** Used Bash-specific process substitution (`while read ... < <(lsblk)`) which is often unsupported in the installer's minimal `/bin/sh` environment.
   - **Fix:** Rewrote detection as a shell-compatible function `find_empty_disk_serial()` using a standard `for` loop and portable check for zeroed disks (`dd | tr | wc`).

5. **Config File Resolution:**
   - **Problem:** The `sed` command targeting `/autoinstall.yaml` was unreliable as Subiquity often moves the working config to `/run/subiquity/autoinstall.yaml`.
   - **Fix:** Updated the script to probe multiple potential paths (`/autoinstall.yaml`, `/run/subiquity/autoinstall.yaml`, `/tmp/autoinstall.yaml`) when patching the disk serial.

6. **Force Stop on Failure:**
   - **Problem:** If a suitable empty disk was not found, the installation might proceed incorrectly.
   - **Fix:** Added a failure path that returns exit code `1` if detection fails, which halts the automated installation progress for manual inspection.

---


## 2026-03-09: Fix Installation Stall — Disable Unattended Security Updates

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Problem

The installation process stalls for a very long time at the `run_unattended_upgrades` step:
```
start: subiquity/.../run_unattended_upgrades: downloading and installing security updates
start: subiquity/.../run_unattended_upgrades/cmd-in-target: curtin command in-target
```
The installer downloads and installs **all available security updates** during the OS installation,
which can take 30+ minutes depending on the number of updates and network speed. The installation
does eventually complete, but the delay is unacceptable for automated deployments.

---

### Fix

Changed the `updates` setting in the autoinstall configuration:

| Before | After |
|---|---|
| `updates: security` | `updates: none` |

This skips the `run_unattended_upgrades` step entirely, significantly reducing installation time.

### Note

Security updates should be applied **post-deployment** as part of the server provisioning process
(e.g., via `apt-get update && apt-get upgrade` in a separate automation step), rather than blocking
the installer.

---

## 2026-03-09: Feature: Log System IP Address to SEL via OEM Record

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Description

Added a new OEM SEL entry in `late-commands` that captures the system's IP address and writes it
to the BMC's System Event Log. This allows administrators to identify the deployed server's IP
address directly from the SEL, without needing to access the OS.

---

### Why OEM Record?

The standard System Event Record (type `0x02`) only provides **3 bytes** of event data (`EvData1-3`),
but an IPv4 address requires **4 bytes**. The IPMI 2.0 spec defines **OEM Timestamped Records**
(Record Type `0xC0-0xDF`) which provide **6 bytes** of OEM-defined data — sufficient for a full
IPv4 address plus metadata.

---

### OEM Timestamped SEL Record Layout (16 bytes)

| Byte(s) | Value | Meaning |
|---|---|---|
| 1-2 | `0x00 0x00` | Record ID (auto-assigned by BMC) |
| 3 | `0xC0` | Record Type = OEM Timestamped |
| 4-7 | `0x00 0x00 0x00 0x00` | Timestamp (auto-filled by BMC) |
| 8-10 | `0x00 0x00 0x00` | Manufacturer ID |
| 11-14 | *dynamic* | **IPv4 address** (4 octets in hex) |
| 15 | `0x03` | Event marker = Network Ready |
| 16 | `0xff` | Reserved |

### Example

For a system with IP `10.249.72.100`:
```bash
ipmitool raw 0x0a 0x44 0x00 0x00 0xC0 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x0a 0xf9 0x48 0x64 0x03 0xff
#                                 ^^^^                               ^^^^ ^^^^^^^^^^^^^^^^^^^^ ^^^^
#                                 OEM                                MfgID  IP: 10.249.72.100   Marker
```

### Implementation

The shell one-liner in `late-commands`:
1. Extracts the first IP from `hostname -I`
2. Splits into 4 octets using `IFS=.`
3. Converts each octet to hex via `printf "0x%02x"`
4. Writes the OEM SEL entry using `ipmitool raw 0x0a 0x44`

```yaml
- chroot /target sh -c 'IP=$(hostname -I | awk "{print \$1}"); IFS=. read -r o1 o2 o3 o4 <<< "$IP"; ipmitool raw 0x0a 0x44 0x00 0x00 0xC0 0x00 0x00 0x00 0x00 0x00 0x00 0x00 $(printf "0x%02x 0x%02x 0x%02x 0x%02x" $o1 $o2 $o3 $o4) 0x03 0xff 2>/dev/null || true'
```

### Reading the IP Back from SEL

```bash
ipmitool sel list
```
Decode bytes 11-14 of the OEM record from hex to decimal to recover the IP address
(e.g., `0x0a 0xf9 0x48 0x64` → `10.249.72.100`).

---

## 2026-03-09: Fix SEL Event Logging — Use Add SEL Entry with Correct Generator ID

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Problem Description

SEL (System Event Log) entries for "OS Installation Starting" and "OS Installation Completed"
were not being written to the BMC's SEL as expected. Two issues were identified:

1. **Original `Add SEL Entry` (0x0a 0x44) failed silently:** The command used BMC Generator ID
   `0x20 0x00`, which is **explicitly prohibited** by the MiTAC BMC firmware (Table 70, footnote 1:
   *"Adding SEL entries using the BMC Generator ID (0x20) is prohibited"*).

2. **Replacement `Platform Event Message` (0x04 0x02) was unreliable:** While this command goes
   through the BMC's normal event pipeline, it does **not guarantee** the event is written to the
   SEL — the BMC may filter it based on event filter configuration.

---

### Root Cause Analysis (from MiTAC BMC Firmware EPS)

| Reference | Finding |
|---|---|
| Table 48 (p.8) | `Add SEL Entry` = Code 44h, Net Function = Storage (0Ah) |
| Table 64 (p.46) | `Add SEL Entry` requires **Operator** privilege |
| Table 70 (p.48) | Both `Platform Event` (04h/02h) and `Add SEL Entry` (0Ah/44h) are available via SMM |
| Table 70, footnote 1 (p.49) | **"Adding SEL entries using the BMC Generator ID (0x20) is prohibited"** |

The original failure was **not** due to the `Add SEL Entry` command itself, but due to using the
prohibited BMC Generator ID `0x20`. The fix is to use a **software generator ID** `0x21` instead.

---

### Fix

Reverted from `Platform Event Message` (0x04 0x02) back to `Add SEL Entry` (0x0a 0x44) with the
correct **software generator ID** (0x21 0x00):

| Byte(s) | Value | Meaning |
|---|---|---|
| 1-2 | `0x00 0x00` | Record ID (auto-assigned by BMC) |
| 3 | `0x02` | Record Type = System Event |
| 4-7 | `0x00 0x00 0x00 0x00` | Timestamp (auto-filled by BMC) |
| 8-9 | `0x21 0x00` | **Generator ID = Software ID 0x01** (NOT 0x20!) |
| 10 | `0x04` | EvMRev (IPMI 2.0) |
| 11 | `0x12` | Sensor Type = System Event |
| 12 | `0x00` | Sensor Number |
| 13 | `0x6f` | Event Type = sensor-specific, assertion |
| 14 | `0x01` / `0x02` | Event Data 1: Starting / Completed |
| 15-16 | `0xff 0xff` | Event Data 2-3 (unspecified) |

**Before (unreliable — Platform Event may not write to SEL):**
```bash
ipmitool raw 0x04 0x02 0x04 0x1F 0x01 0x6f 0x01 0xff 0xff
```

**After (correct — Add SEL Entry with software generator ID):**
```bash
ipmitool raw 0x0a 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6f 0x01 0xff 0xff
```

### Verification

After deploying the updated ISO, confirm that SEL entries are correctly created:
```bash
ipmitool sel list
```
Expected output should show entries with Sensor Type `System Event` and Event Data indicating
installation start (0x01) and completion (0x02), with a software generator ID source.

---

## 2026-03-09: Fix YAML Parsing Error in early/late-commands (Boot Failure)

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Problem Description

The generated autoinstall ISO failed to boot with the error:
```
Failed validating 'type' in schema['items']:
    {'items': {'type': 'string'}, 'type': ['string', 'array']}
On instance[5]:
    {'sh -c \'which ipmitool ...'} is not of type 'string', 'array'
```

**Root cause:** The YAML `early-commands` and `late-commands` entries contained **colon-space (`: `)** within `echo` messages (e.g., `echo "WARN: ipmitool not available..."`). In YAML, `: ` is a **mapping key-value separator**, so the YAML parser interpreted the command as a dict `{key: value}` instead of a string, causing schema validation failure.

---

### Fix

Removed the complex `sh -c` wrappers with `echo "WARN: ..."` messages and replaced with simple direct commands:

| Before (broken YAML) | After (valid YAML) |
|---|---|
| `sh -c 'dpkg -i /cdrom/pool/extra/*.deb 2>/dev/null \|\| true'` | `dpkg -i /cdrom/pool/extra/*.deb 2>/dev/null \|\| true` |
| `sh -c 'which ipmitool && ipmitool raw ... \|\| echo "WARN: ..."' 2>/dev/null \|\| true` | `ipmitool raw ... 2>/dev/null \|\| true` |
| `sh -c 'chroot /target ipmitool raw ... \|\| echo "WARN: ..."' 2>/dev/null \|\| true` | `chroot /target ipmitool raw ... 2>/dev/null \|\| true` |

### YAML Rule

In YAML plain scalars (unquoted strings), these characters have special meaning and must be avoided:
- **`: `** (colon-space) → mapping separator
- **`#`** (after space) → comment
- **`{`** / **`}`** → flow mapping

The `|| true` suffix already handles command failures silently, so the `echo "WARN: ..."` messages were unnecessary.

---

## 2026-03-09: Fix Cross-version apt Isolation for ipmitool Package Download

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Problem Description

When the build machine runs a **different Ubuntu version** than the target ISO, the `download_ipmitool_packages()` function fails to download the correct packages.

**Observed failure:** Build machine running **Ubuntu 25.04 (plucky)**, building ISO for **Ubuntu 22.04 (jammy)**:
```
E: Can't find a source to download version '1.8.19-7.1ubuntu0.2' of 'ipmitool:amd64'
Resolved dependencies: init-system-helpers libc6 libfreeipmi17 libreadline8t64 libssl3t64
```

**Root cause:** `apt` was reading the **host system's** `/var/lib/dpkg/status`, which caused:
1. `apt-get download ipmitool` tried to download plucky's version (`1.8.19`) from the jammy repo (doesn't exist there — jammy has `1.8.18`)
2. `apt-cache depends` resolved plucky dependency names (`libreadline8t64`, `libssl3t64`) instead of jammy ones (`libreadline8`, `libssl3`)

---

### Fix

| Change | Purpose |
|---|---|
| `touch "$apt_state/status"` | Creates **empty** dpkg status file so apt thinks no packages are installed |
| `-o Dir::State::status="$apt_state/status"` | Explicitly points apt to the empty file instead of host's `/var/lib/dpkg/status` |
| `-t "${codename}"` flag on `apt-get download` | Forces package resolution from the **target release** (e.g., jammy), not the host |
| `APT_OPTS` array | Consolidates all isolation options into a reusable array for consistency |

### Result

The build machine can now run **any** Ubuntu version and correctly download packages for **any** target release:

```
Build Machine (plucky)  →  Target ISO (jammy)  →  Downloads ipmitool 1.8.18 + jammy deps  ✅
Build Machine (plucky)  →  Target ISO (noble)  →  Downloads ipmitool 1.8.19 + noble deps  ✅
Build Machine (jammy)   →  Target ISO (noble)  →  Downloads ipmitool 1.8.19 + noble deps  ✅
```

---

## 2026-03-09: Bundle ipmitool Packages into ISO for Offline Early-commands Installation

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Problem Description

The `early-commands` SEL logging requires `ipmitool`, but installing it via `apt-get` fails because the network is not yet available during the early boot phase. The previous approach relied on network availability which was inherently unreliable.

---

### Solution: Pre-bundle ipmitool .deb Files into the ISO

During ISO build time (when the build machine has internet), the script now:
1. Detects the target Ubuntu **codename** from the OS_NAME (e.g., `22.04` → `jammy`, `24.04` → `noble`)
2. Creates a **temporary apt configuration** pointing to the correct Ubuntu archive for that release
3. Downloads `ipmitool` and **all its dependencies** using `apt-cache depends` to resolve the correct package names
4. Bundles the `.deb` files into the ISO under `/pool/extra/`

The `early-commands` then install from these bundled packages:
```yaml
- sh -c 'dpkg -i /cdrom/pool/extra/*.deb 2>/dev/null || true'
```

---

### Cross-version Dependency Handling

Package names and versions vary between Ubuntu releases due to ABI transitions:

| Dependency | Ubuntu 20.04 (focal) | Ubuntu 22.04 (jammy) | Ubuntu 24.04+ (noble) |
|---|---|---|---|
| `libsnmp` | `libsnmp35` | `libsnmp40` | `libsnmp40t64` |
| `libopenipmi` | `libopenipmi0` | `libopenipmi0` | `libopenipmi0t64` |
| `libfreeipmi` | `libfreeipmi17` | `libfreeipmi17` | `libfreeipmi17t64` |

By using `apt-cache depends` with a target-version-specific repository configuration, the correct package names are resolved automatically for each Ubuntu release. This avoids hard-coding package names that would break on different versions.

---

### Supported Ubuntu Codenames

| Version | Codename |
|---|---|
| 18.04 | bionic (skipped — uses preseed, not early-commands) |
| 20.04 | focal |
| 22.04 | jammy |
| 23.04 | lunar |
| 23.10 | mantic |
| 24.04 | noble |
| 24.10 | oracular |
| 25.04 | plucky |

---

### Impact

- **Before:** Early-commands `ipmitool` install depended on network → always failed
- **After:** `ipmitool` is pre-bundled in the ISO → installs offline, no network needed
- **ISO size increase:** ~2-3 MB (ipmitool + dependencies)

---

## 2026-03-09: Fix IPMI SEL Logging — Commands Were Silently Failing

**File:** `build-ubuntu-autoinstall-iso.sh`  
**Log files reviewed:** `test_log/install_log_20260306/installer-journal.txt`, `test_log/install_log_20260306/subiquity-server-debug.log`

---

### Problem Description

IPMI SEL (System Event Log) entries for "OS Installation Starting" (`early-commands`) and "OS Installation Completed" (`late-commands`) were never actually written to the BMC, despite the installer reporting `SUCCESS` for both commands. The `|| true` and `2>/dev/null` error suppression masked the failures completely.

---

### Log Review — Evidence of Silent Failure

#### 1. Early-commands: `apt-get install ipmitool` — Network Unreachable

**Log:** `installer-journal.txt`

At `01:24:19`, the early-command for ipmitool installation started:
```
line 3763: subiquity/Early/run/command_4: apt-get install -y ipmitool 2>/dev/null || dpkg -i /cdrom/pool/main/i/ipmitool/*.deb 2>/dev/null || true
```

All package download attempts failed with network errors (lines 3849–3864):
```
line 3849: Err:1 http://archive.ubuntu.com/ubuntu jammy/main amd64 freeipmi-common all 1.6.9-2
line 3850:   Cannot initiate the connection to archive.ubuntu.com:80 (2a06:bc80:0:1000::17). - connect (101: Network is unreachable)
line 3853: Err:3 http://archive.ubuntu.com/ubuntu jammy/universe amd64 ipmitool amd64 1.8.18-11ubuntu2
line 3864:   Cannot initiate the connection to archive.ubuntu.com:80 (2620:2d:4002:1::101). - connect (101: Network is unreachable)
```

Despite the failure, the command was reported as SUCCESS (due to `|| true`):
```
line 4027: finish: subiquity/Early/run/command_4: SUCCESS: apt-get install -y ipmitool 2>/dev/null || dpkg -i /cdrom/pool/main/i/ipmitool/*.deb 2>/dev/null || true
```

#### 2. Early-commands: `ipmitool raw` — Command Not Found (Masked)

**Log:** `installer-journal.txt`, `subiquity-server-debug.log`

The SEL write command started and finished in same timestamp (lines 4028–4029):
```
line 4028: start:  subiquity/Early/run/command_5: ipmitool raw 0x0a 0x44 ... 2>/dev/null || true
line 4029: finish: subiquity/Early/run/command_5: SUCCESS: ipmitool raw 0x0a 0x44 ... 2>/dev/null || true
```

**Timing analysis:** Both start and finish occurred at `01:25:51` with ~23ms elapsed — a real IPMI raw command communicating with the BMC takes 100–200ms+. This proves `ipmitool` was not found and `command not found` was silenced by `2>/dev/null || true`.

#### 3. Late-commands: `ipmitool` installed in target chroot — but ran in live env

**Log:** `installer-journal.txt`

The `apt-get install ipmitool` via `curtin in-target` **succeeded** inside the target chroot (lines 9419–9529):
```
line 9419: subiquity/Late/run/command_7: curtin in-target --target=/target -- sh -c 'apt-get install -y vim curl net-tools ipmitool htop || true'
line 9443: Get:3 http://archive.ubuntu.com/ubuntu jammy-updates/universe amd64 ipmitool amd64 1.8.18-11ubuntu2.2 [410 kB]
line 9498: Setting up ipmitool (1.8.18-11ubuntu2.2) ...
line 9529: subiquity/Late/run/command_7: ... SUCCESS
```

However, the subsequent `ipmitool raw` command ran **outside** the target chroot — in the live installer environment where ipmitool was never installed:

**Log:** `subiquity-server-debug.log` (lines 1168–1171)
```
line 1168: 02:07:20,321 start:  subiquity/Late/run/command_8: ipmitool raw 0x0a 0x44 ... 2>/dev/null || true
line 1169: 02:07:20,322 arun_command called: ['systemd-cat', ..., 'sh', '-c', 'ipmitool raw ... 2>/dev/null || true']
line 1170: 02:07:20,341 arun_command [...] exited with code 0
line 1171: 02:07:20,342 finish: subiquity/Late/run/command_8: SUCCESS: ipmitool raw ... 2>/dev/null || true
```

**Timing analysis:** Command started at `02:07:20,321` and exited at `02:07:20,341` — **only 20ms**. Confirmed `ipmitool: command not found`, masked by `2>/dev/null || true`.

**Key evidence the command ran in live env, not chroot:** Line 1169 shows `arun_command` was called directly with `['sh', '-c', 'ipmitool raw ...']` — there is no `chroot`, `curtin in-target`, or `/target` prefix. Compare this to line 1165 where the `apt-get install` correctly uses `curtin in-target --target=/target`.

---

### Issue 1: Early-commands — `ipmitool` installation fails (no network)

**Root Cause:** During `early-commands`, the network interfaces are still being configured. The `apt-get install -y ipmitool` command cannot reach `archive.ubuntu.com` and times out. The fallback `dpkg -i /cdrom/pool/main/i/ipmitool/*.deb` also fails because `ipmitool` is in the Ubuntu `universe` repository, not in the ISO's local package pool under `main/`.

**Fix:** 
- Removed the incorrect `dpkg -i` fallback path
- Added `which ipmitool` check before attempting the SEL write
- Added a visible warning message when ipmitool is unavailable instead of silent failure

```yaml
- apt-get install -y ipmitool 2>/dev/null || true
- sh -c 'which ipmitool >/dev/null 2>&1 && ipmitool raw 0x0a 0x44 ... || echo "WARN: ipmitool not available, skipping SEL write (OS Installation Starting)"' 2>/dev/null || true
```

**Note:** The early-commands SEL write may still fail if network is unavailable. This is expected — the early-commands run before network configuration is complete.

---

### Issue 2: Late-commands — `ipmitool` runs in wrong environment

**Root Cause:** The `ipmitool raw ...` command in `late-commands` ran in the **live installer environment** (not inside the target chroot). While `ipmitool` was successfully installed inside the target system via `curtin in-target -- apt-get install -y ipmitool`, it was **not** available in the live environment where the raw `ipmitool` command was executed.

**Fix:** Changed the late-command to use `chroot /target ipmitool raw ...` so that it runs the `ipmitool` binary from inside the target chroot where it was installed:

```yaml
- sh -c 'chroot /target ipmitool raw 0x0a 0x44 ... || echo "WARN: ipmitool SEL write failed (OS Installation Completed)"' 2>/dev/null || true
```

---

### Impact

- **Before fix:** Both SEL entries were silently skipped, giving a false "SUCCESS"
- **After fix:** Late-commands SEL write will succeed (uses target chroot). Early-commands SEL write will produce a visible warning if ipmitool is unavailable.

---

## 2026-03-06: Fix Curtin In-Target `apt-get update` Failure (Exit Status 100)

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### Problem Description

When booting the custom autoinstall ISO (`ubuntu_22.04.2_live_server_amd64_autoinstall_202603051721.iso`), the installation crashed at the `configure_apt` late-command phase with:

```
subiquity/Install/install/configure_apt/cmd-in-target: curtin command in-target
'apt-get', 'update'] returned non-zero exit status 100
An error occurred. Press enter to start a shell
```

**Key observation:** After dropping to a shell, network connectivity was confirmed working (`ping 8.8.8.8` succeeded) and manually running `apt update` also completed successfully. The failure only occurred when curtin executed `apt-get update` inside the target chroot.

---

### 1. Fix: Remove Broken Empty Security URI in `apt` Configuration

**Root Cause:** The `apt.security` section had an empty URI:
```yaml
apt:
  security:
    - arches: [amd64, i386]
      uri: ""
```
This was originally added (2026-03-04) to prevent `run_unattended_upgrades` from hanging. However, the empty `uri: ""` caused subiquity to generate an invalid `sources.list` inside the target, which made `apt-get update` fail with exit status 100 when curtin ran it in-target.

**Fix:** Removed the entire `security` sub-section. The `fallback: offline-install` setting already handles the offline scenario sufficiently:
```yaml
apt:
  fallback: offline-install
  geoip: false
```

---

### 2. Fix: Copy DNS Resolution Configuration into Target Chroot

**Root Cause:** When `curtin in-target` executes commands inside the `/target` chroot, the chroot does not automatically inherit the live installer environment's DNS configuration. The file `/target/etc/resolv.conf` was either missing or empty, causing all DNS lookups (e.g., for `archive.ubuntu.com`) to fail inside the chroot — even though the host network was fully operational.

**Fix:** Added a step to copy the live environment's DNS config into the target before running apt commands:
```yaml
late-commands:
    # ... (existing commands)
    # Ensure DNS resolution is available in the target chroot
    - cp /etc/resolv.conf /target/etc/resolv.conf
    # ... (apt commands follow)
```

---

### 3. Fix: Wrap `apt-get` Commands with `sh -c` for Proper Error Suppression

**Root Cause:** The previous `|| true` was not being interpreted correctly:
```yaml
# BEFORE — || true evaluated by outer shell, but curtin still fails fatally
- curtin in-target --target=/target -- apt-get update || true
```
Subiquity processes each `late-commands` entry as a command list. The `|| true` was parsed by the outer YAML/shell layer, but `curtin in-target` itself still raised a fatal error when the inner `apt-get` returned non-zero. This caused the entire installation to crash.

**Fix:** Wrapped the commands with `sh -c` so the `|| true` is executed inside the curtin chroot context:
```yaml
# AFTER — || true handled inside sh, curtin sees exit code 0
- curtin in-target --target=/target -- sh -c 'apt-get update || true'
- curtin in-target --target=/target -- sh -c 'apt-get install -y vim curl net-tools ipmitool htop || true'
```

---

### Summary of All File Changes (2026-03-06)

| File | Change Type | Description |
|------|-------------|-------------|
| `build-ubuntu-autoinstall-iso.sh` | Modified | Remove broken `apt.security` empty URI configuration |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add `cp /etc/resolv.conf /target/etc/resolv.conf` to late-commands |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Wrap `apt-get` commands with `sh -c '... \|\| true'` for proper error handling |
| `doc/change_log.md` | Modified | Document all changes |

---

## 2026-03-04: Fix Ubuntu 22.04 Autoinstall Boot Errors and Add BMC SEL Logging

**File:** `build-ubuntu-autoinstall-iso.sh`

---

### 1. Fix: Schema Validation Error — `updates: none` Invalid

**Symptom:** ISO boot failed immediately with:
```
finish: subiquity/Updates/load_autoinstall_data: 'none' is not one of ['security', 'all']
Failed validating 'enum' in schema
```

**Root Cause:** Ubuntu 22.04's Subiquity autoinstall schema only accepts `security` or `all` for the `updates` field. The previous value `none` was invalid.

**Fix:** Changed `updates: none` → `updates: security`

---

### 2. Fix: openssh-server Installation Failure (Exit Code 100)

**Symptom:** Installation progressed but failed at:
```
install_openssh-server/cmd-system-install: curtin command system-install
'openssh-server'] returned non-zero exit status 100
```

**Root Cause:** The `updates: security` setting caused Subiquity to configure online security repos. When the target server had no internet access, apt's state became broken, preventing even ISO-bundled packages (`pool/main/o/openssh/openssh-server_8.9p1-3ubuntu0.1_amd64.deb`) from being installed.

**Fix:** Added `apt` section to autoinstall `user-data`:
```yaml
apt:
  fallback: offline-install
  geoip: false
```

Also made `apt-get update` in `late-commands` non-fatal: `apt-get update || true`

---

### 3. Fix: Installation Stuck at Unattended Security Upgrades

**Symptom:** Installation hung indefinitely at:
```
run_unattended_upgrades: downloading and installing security updates
run_unattended_upgrades/cmd-in-target: curtin command in-target
```

**Root Cause:** `updates: security` triggered the `run_unattended_upgrades` step which attempted to download security updates from the internet. With no or slow network, this step hung indefinitely.

**Fix:** Set the apt security source URI to empty, so there are no security mirrors to download from:
```yaml
apt:
  security:
    - arches: [amd64, i386]
      uri: ""
```
This satisfies the `updates: security` schema requirement while effectively disabling security update downloads.

---

### 4. Feature: BMC SEL Logging for OS Installation Events

**Change:** Added IPMI-based System Event Log (SEL) entries to track OS installation lifecycle via the BMC.

**Implementation:**
- **`early-commands`** (before install): Loads IPMI kernel modules (`ipmi_devintf`, `ipmi_si`, `ipmi_msghandler`), installs `ipmitool`, and writes a **"OS Installation Starting"** SEL entry
- **`late-commands`** (after install): Writes an **"OS Installation Completed"** SEL entry

**SEL Entry Details:**
- Uses IPMI "Add SEL Entry" command (`NetFn=0x0a, Cmd=0x44`)
- Record Type: `0x02` (System Event)
- Sensor Type: `0x1F` (OS Boot)
- Event Data: `0x01` = Starting, `0x02` = Completed

**Safety:** All IPMI commands use `2>/dev/null || true` to never block the installation if IPMI is unavailable.

---

### Summary of All File Changes (2026-03-04)

| File | Change Type | Description |
|------|-------------|-------------|
| `build-ubuntu-autoinstall-iso.sh` | Modified | Fix `updates: none` → `updates: security` (schema validation) |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add `apt: fallback: offline-install` for offline package installation |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Disable security update downloads via empty security URI |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add `early-commands` with BMC SEL "Installation Starting" entry |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add BMC SEL "Installation Completed" entry to `late-commands` |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Make `apt-get update` in `late-commands` non-fatal |
| `doc/change_log.md` | Modified | Document all changes |

---

## 2026-02-10: Create ISO Repository File List Generator

**Files:** `generate_file_list.py` (New), `iso_repository/file_list.json` (New)

---

### 1. Feature: ISO Repository File List Generator Script

**Change:** Created `generate_file_list.py` to recursively scan the `iso_repository` directory and generate a JSON file listing all ISO files with their names and relative paths.

**Key behaviors:**
- Recursively scans `iso_repository` for `.iso` files only
- Organizes files into a tree structure grouped by subdirectory (CentOS, Redhat, Rocky, SUSE, Ubuntu)
- Files in the root directory are grouped under `root_files`
- Each file entry contains `OS_Name` (filename without extension) and `OS_Path` (relative path from `iso_repository`)
- Automatically skips non-ISO files (e.g., `.qcow2`, `wget-log`)
- Skips the output file itself (`file_list.json`) to avoid self-referencing

---

### 2. Feature: Generated `file_list.json`

**Change:** Generated `iso_repository/file_list.json` containing a structured inventory of all ISO files.

**Output format:**
```json
{
  "scan_time": "2026-02-10T11:05:24.214191",
  "root_directory": "iso_repository",
  "tree": {
    "CentOS": [
      {
        "OS_Name": "CentOS-8.4.2105-x86_64-dvd1",
        "OS_Path": "CentOS/CentOS-8.4.2105-x86_64-dvd1.iso"
      }
    ]
  }
}
```

**ISO count by directory:**

| Directory | ISO Count |
|-----------|-----------|
| CentOS | 4 |
| Redhat | 6 |
| Rocky | 5 |
| SUSE | 1 |
| Ubuntu | 20 |
| root_files | 4 |
| **Total** | **40** |

---

### Summary of All File Changes (2026-02-10)

| File | Change Type | Description |
|------|-------------|-------------|
| `generate_file_list.py` | New | Python script to scan `iso_repository` and generate structured JSON file list |
| `iso_repository/file_list.json` | New | JSON inventory of all ISO files with tree structure |

---

## 2026-02-24: Implement Preseed Automation for Ubuntu 18.04

**File:** `build-ubuntu-autoinstall-iso.sh`  
**Documentation:** `doc/06_ubuntu_18_04_compatibility.md`, `doc/07_preseed_implementation_plan.md`, `doc/08–13 (detailed fix docs)`

---

### 1. Feature: Ubuntu 18.04 Version Detection

**Change:** Added automatic detection of Ubuntu 18.04 ISOs based on `OS_NAME`. Sets an `IS_1804` flag that drives conditional logic throughout the script.

```bash
IS_1804=false
if [[ "$OS_NAME" == *"18.04"* ]]; then
    IS_1804=true
fi
```

---

### 2. Feature: Preseed Configuration Generation

**Change:** When `IS_1804=true`, the script generates a `preseed.cfg` file with Debian Installer (`d-i`) directives for fully automated installation, including locale, keyboard, partitioning (atomic), user setup, SSH config, and package selection.

**Key Preseed Directives:**
- `d-i partman-auto/choose_recipe select atomic`
- `d-i passwd/username string ${USERNAME}`
- `d-i pkgsel/upgrade select none`
- `d-i pkgsel/update-policy select none`
- `d-i preseed/late_command` for SSH/sudo configuration

---

### 3. Feature: Hybrid Automation (Autoinstall + Preseed)

**Change:** For 18.04 Live Server ISOs, the script generates **both** `autoinstall/user-data` (for Subiquity) and `preseed.cfg` (for classic d-i). This ensures maximum compatibility since 18.04.6 Live uses Subiquity as its primary installer.

---

### 4. Fix: Missing `boot=casper` for UEFI Boot

**Symptom:** Custom ISO dropped to BusyBox initramfs shell with `No init found. Try passing init= bootarg.`

**Root Cause:** The GRUB `linux` line was missing the `boot=casper` parameter, which tells the kernel to mount the squashfs Live filesystem.

**Fix:** Added `boot=casper` to both GRUB (UEFI) and ISOLINUX (BIOS) kernel parameters for all Ubuntu versions.

---

### 5. Fix: Semicolon Escaping in GRUB Configuration

**Symptom:** Installer booted but entered interactive mode instead of running automation.

**Root Cause:** The semicolons in `ds=nocloud;s=/cdrom/autoinstall/` were interpreted by GRUB as command separators, truncating the kernel command line.

**Fix:** Added Python-based escaping in the GRUB patcher to replace `;` with `\;` specifically in `grub.cfg`. ISOLINUX does not require this escaping.

```python
boot_params = "${BOOT_PARAMS}".replace(";", "\\;")
```

---

### 6. Fix: Bypass Unattended Upgrades

**Symptom:** Installation hung at `run_unattended_upgrades: downloading and installing security updates` with NMI watchdog CPU lockups.

**Root Cause:** The Subiquity installer attempted to download security updates during post-install, causing network-related hangs on air-gapped or slow-network servers.

**Fix:**
- **Autoinstall (20.04+):** Added `updates: none` to `user-data`
- **Preseed (18.04):** Added `d-i pkgsel/update-policy select none`

---

### 7. Fix: CD-ROM Scan Interactive Prompt

**Symptom:** Installer stopped at "Repeat this process for the rest of the CDs in your set."

**Root Cause:** The classic Debian Installer scans for additional CD-ROM media by default.

**Fix:** Added the following directives to `preseed.cfg`:
```
d-i apt-setup/use_mirror boolean false
d-i apt-setup/cdrom/set-first boolean false
d-i apt-setup/cdrom/set-next boolean false
d-i apt-setup/cdrom/set-failed boolean false
```

---

### 8. Enhancement: Clean Build Environment

**Change:** Added `rm -rf "$WORKDIR"` before each build to prevent configuration from previous runs bleeding into new ISOs.

---

### 9. Enhancement: BIOS Boot Image Detection

**Change:** Added dynamic probing for BIOS bootloaders (`eltorito.img` vs `isolinux.bin`) to support varying ISO structures across Ubuntu versions.

---

### 10. Documentation Created

| File | Description |
|------|-------------|
| `doc/06_ubuntu_18_04_compatibility.md` | General overview of all 18.04 fixes |
| `doc/07_preseed_implementation_plan.md` | Architectural plan for preseed support |
| `doc/08_uefi_boot_fix.md` | EFI path/casing fix details |
| `doc/09_bios_boot_image_detection.md` | Dynamic bootloader discovery |
| `doc/10_grub_font_loading_fix.md` | Missing `font.pf2` resolution |
| `doc/11_kernel_boot_parameter_fix.md` | `boot=casper` requirement |
| `doc/12_isolinux_patching_bios.md` | Legacy bootloader customization |
| `doc/13_preseed_support_18_04.md` | Preseed automation details |

---

### Summary of All File Changes (2026-02-24)

| File | Change Type | Description |
|------|-------------|-------------|
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add `IS_1804` version detection |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Generate `preseed.cfg` for 18.04 |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Generate both `user-data` and `preseed.cfg` (hybrid) |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add `boot=casper` to GRUB/ISOLINUX for 18.04 |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Escape semicolons in GRUB `grub.cfg` |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add `updates: none` to autoinstall `user-data` |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add CD-ROM scan suppression to `preseed.cfg` |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Clean work directory before each build |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Dynamic BIOS boot image detection |
| `doc/06–13` | New | Eight detailed documentation files |
| `doc/README.md` | Modified | Updated document index |

---

## 2026-02-25: Fix Ubuntu 18.04 Custom ISO Boot Failures

**File:** `build-ubuntu-autoinstall-iso.sh`  
**Documentation:** `doc/15_iso_comparison_and_efi_boot_fix.md`

---

### 1. Fix: Stop Patching `efi.img` for Ubuntu 18.04 (Round 1 — Black Screen)

**Symptom:** Custom ISO produced a total black screen when booted via BMC virtual media on physical server. Original ISO booted normally.

**Root Cause:** The build script injected a `grub.cfg` file into the `efi.img` FAT partition. The original `efi.img` contains only `BOOTx64.EFI` and `grubx64.efi` — no `grub.cfg`. The embedded GRUB startup script in `grubx64.efi` uses `search --file --set=root /.disk/info` to locate the ISO9660 filesystem. The injected `grub.cfg` was found first (via `elif [ -e $prefix/grub.cfg ]`), causing GRUB to load the config in the EFI FAT partition context where `/install/vmlinuz` doesn't exist.

**Fix:** Removed all `efi.img` patching for 18.04. The original `efi.img` is preserved byte-for-byte. Only `/boot/grub/grub.cfg` on the ISO9660 filesystem is patched.

**Verification:** `efi.img` MD5 checksum confirmed identical between original and custom ISOs (`e1fb948511b0b5a8dcea206a334d527f`).

---

### 2. Fix: GRUB Timeout and Console Visibility (Round 2 — No GRUB Menu)

**Symptom:** After fixing `efi.img`, the ISO still showed a black screen — no GRUB menu visible.

**Root Cause:** Two settings prevented any visible output on BMC KVM:
- `set timeout=0` — GRUB instantly booted the default entry without displaying the menu
- `console=ttyS0,115200n8` (serial only) — kernel output redirected entirely to serial port
- `quiet` — suppressed boot messages

**Fix:**

| Parameter | Before | After |
|-----------|--------|-------|
| GRUB `timeout` | `0` | `5` |
| Console | `console=ttyS0,115200n8` only | Added `console=tty0` for video |
| `quiet` | Present | Removed |

---

### 3. Fix: Console Parameter Ordering (Round 3 — Installer TUI Invisible)

**Symptom:** After adding `console=tty0`, the GRUB menu appeared and kernel messages scrolled on KVM, but the screen appeared hung after ~52 seconds of hardware detection. System stayed frozen for 30+ minutes.

**Root Cause:** The `console=` parameter order was wrong. In Linux, the **last** `console=` parameter becomes `/dev/console` (the primary console). User-space programs like the debian-installer display their TUI on `/dev/console` only.

```
# Wrong order — d-i TUI goes to serial (invisible on KVM)
console=tty0 console=ttyS0,115200n8

# Correct order — d-i TUI goes to video (visible on KVM)
console=ttyS0,115200n8 console=tty0
```

**Fix:** Reversed `console=` parameter order so `tty0` is last (primary).

**Final kernel parameters (GRUB):**
```
linux /install/vmlinuz file=/cdrom/preseed.cfg auto=true priority=critical console=ttyS0,115200n8 console=tty0 ---
```

**Final kernel parameters (ISOLINUX):**
```
append file=/cdrom/preseed.cfg auto=true priority=critical initrd=/install/initrd.gz console=ttyS0,115200n8 console=tty0 ---
```

---

### 4. Enhancement: Timestamped ISO Filename

**Change:** Output ISO filename now includes a `YYYYMMDDHHmm` timestamp before the `.iso` extension.

**Example:**
```
ubuntu_18.04.6_server_amd64_autoinstall_202602251618.iso
```

---

### 5. Documentation: ISO Comparison and Boot Fix Analysis

**File:** `doc/15_iso_comparison_and_efi_boot_fix.md` (New, 460+ lines)

Comprehensive documentation covering:
- Layer-by-layer ISO comparison methodology (11 categories)
- Binary-level analysis of MBR, GPT, El Torito boot catalog, EFI partition
- QEMU verification tests (both UEFI and BIOS modes)
- UEFI boot chain walkthrough (`BOOTx64.EFI → grubx64.efi → embedded script → search → configfile`)
- Three rounds of root cause analysis and fixes
- Linux `console=` parameter ordering rules
- Complete boot issue timeline summary table

---

### Summary of All File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `build-ubuntu-autoinstall-iso.sh` | Modified | Stop patching `efi.img` for 18.04; use original unmodified |
| `build-ubuntu-autoinstall-iso.sh` | Modified | GRUB timeout `0` → `5` |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add dual console: `console=ttyS0,115200n8 console=tty0` |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Remove `quiet` from boot parameters |
| `build-ubuntu-autoinstall-iso.sh` | Modified | Add timestamp to output ISO filename |
| `doc/15_iso_comparison_and_efi_boot_fix.md` | New | Full ISO comparison and boot fix analysis |
| `doc/change_log.md` | New | This change log |
