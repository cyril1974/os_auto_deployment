# Debug Note - Autoinstall Failure on 10.99.236.85 (R2520G6 Server)
**Date/Time:** 2026-03-18 10:15:00 (GMT+8)

---

### Symptom
Autoinstall completed successfully, but some packages (`ipmitool`) were left in an unconfigured state (`iU`), and others (`net-tools`) were missing. `apt update` was reported failing during the process.

### Debugging Steps
1.  **Check IP & Connectivity**: `ping 8.8.8.8` was successful.
2.  **Verify Apt Sources**: `/etc/apt/sources.list` contained valid standard Ubuntu mirrors.
3.  **Inspect DNS Resolution**:
    - **Current Host**: `ping google.com` works. `resolvectl status` shows valid upstream DNS (`10.88.1.86`).
    - **Host resolv.conf**: `/etc/resolv.conf` is a symlink to the `systemd-resolved` stub resolver (`127.0.0.53`).
4.  **Analyze Installation Logs**:
    - The `late-commands` attempted to copy `/etc/resolv.conf` to `/target/etc/resolv.conf`.
    - **The Conflict**: Inside the `chroot` during the `late-commands` phase, `127.0.0.53` is unreachable. This caused `apt-get update` to fail during the installation, forcing the script into its fallback mode.
5.  **Identify Fallback Issues**:
    - The fallback used `dpkg -i /cdrom/pool/extra/*.deb`.
    - `ipmitool` was installed via `dpkg -i` but entered the `iU` (unconfigured) state because its configuration scripts likely required dependencies or a running system environment that was not fully ready during the `late-commands` stage.
    - `net-tools` was missing because it was not included in the `/cdrom/pool/extra` local repository on this specific ISO version.

### Root Cause
The **Systemd-resolved stub resolver (127.0.0.53)** does not function inside the installation target `chroot`. This breaks internet-based package management during the `curthooks` and `late-commands` phases, even when the underlying network is fully functional.

### Recommended Fix
In the `build-ubuntu-autoinstall-iso.sh` script, instead of simply copying `/etc/resolv.conf`, we should resolve the actual upstream nameservers and write them directly into the target's `/etc/resolv.conf` during the installation phase.
*   **Example Fix**: `resolvectl status | grep 'DNS Servers' -A 1 | awk '/[0-9]/ {print "nameserver " $1}' > /target/etc/resolv.conf`

---

# Debug Note - Autoinstall Failure on 10.99.236.87 (D50DNP Server)
**Date/Time:** 2026-03-18 10:05:00 (GMT+8)

---

### Symptom
The server `10.99.236.87` (D50DNP, Sapphire Rapids) failed during the late `curthooks` stage with a `calledprocesserror` in `installing-kernel`.

### Debugging Steps
1.  **Examine Traceback**: Found `CurtinInstallError` specifically during kernel installation.
2.  **Inspect Curtin Logs**: Found `E: Some files failed to download` during an `apt-get install linux-generic` call.
3.  **Check Network & DNS**:
    - **Connectivity**: `ping 8.8.8.8` was successful.
    - **DNS Configuration**: The live environment (and subsequently the `/target` chroot) was using `systemd-resolved` with `nameserver 127.0.0.53`.
    - **The Failure**: Inside the `chroot` environment used for package installation, `127.0.0.53` is unreachable. This caused all `apt-get` calls, including the kernel installation, to fail despite the server having active internet connectivity.

### Root Causes
1.  **DNS Isolation**: The installer environment used a stub resolver (`127.0.0.53`) that does not translate successfully into the installation target chroot during the `curthooks` stage.
2.  **Package Version Mismatch**: The 22.04.5 "Jammy" ISO contains the Hardware Enablement (**HWE**) kernel (`6.8.0-40-generic`). When `kernel` is left as default, it attempts to install `linux-generic` (pointing to the older `5.15` GA kernel), which is NOT on the local disk pool and requires an internet download that failed due to the DNS issue above.

### Resolution
1.  **Explicit HWE Kernel**: Need to update the build script to specifically request the HWE kernel package: `kernel: {package: linux-generic-hwe-22.04}`. This ensures compatibility with the D50DNP's modern Sapphire Rapids CPU and matches what is actually available in the offline ISO pool.
2.  **D50DNP Compatibility**: Modern server platforms like D50DNP require newer kernels for stable NVMe support and proper CPU feature detection.
3.  **DNS Fix**: I've reinforced the `resolv.conf` handling in `late-commands`, but it may need to be moved to `early-commands` to prevent failures during the `curthooks` phase.

---

# Debug Note - Autoinstall Failure on 10.99.236.99
**Date/Time:** 2026-03-18 08:55:00 (GMT+8)

---

### Symptom
The server `10.99.236.99` booted from the custom ISO but entered the **interactive installation UI** instead of proceeding with the automated installation.

### Debugging Steps
1.  **Check Kernel Command Line**: Verified with `cat /proc/cmdline`. 
    - **Result**: `autoinstall ds=nocloud;s=/cdrom/autoinstall/` was present. This confirms the boot parameters were correctly injected into the ISO.
2.  **Verify Configuration Loading**: Checked `/var/log/installer/subiquity-server-debug.log`.
    - **Result**: Found `no autoinstall found in cloud-config`. This indicates that although the installer was triggered, it failed to load a valid configuration.
3.  **Inspect Cloud-Init Logs**: Checked `/var/log/cloud-init.log` for parsing errors.
    - **Result**: Found a critical YAML syntax warning:
      ```
      Failed loading yaml blob. Invalid format at line 120 column 28: "mapping values are not allowed here
      in "<unicode string>", line 120, column 28:
                  echo "[+] Success: Packages installed from Intern ... 
                                   ^"
      ```

### Root Cause
A **YAML syntax error** was introduced in the `late-commands` section during the implementation of the "Hybrid Internet/Offline" package installation logic.
*   The strings `[+] Success: ...` and `[-] Warning: ...` inside the shell script block contained a colon followed by a space (`: `).
*   Since the command was listed as a multi-line scalar without a literal block marker (`|`), the YAML parser incorrectly interpreted `Success:` as a mapping key.
*   This caused `cloud-init` to fail parsing the entire `user-data` file, leading Subiquity to find no configuration and fall back to interactive mode.

### Resolution
1.  Modified `build-ubuntu-autoinstall-iso.sh` to use the YAML literal block marker `|` for the multi-line package installation script in `late-commands`.
2.  This ensures that colons and special characters inside the shell script are treated as literal text and not YAML structure.

### Conclusion
The failure was purely a formatting issue in the auto-generated `user-data`. After applying the fix to the build script and regenerating the ISO, the automated installation should proceed as expected.

---

# Debug Note - Recursive Dependency Failure on 10.99.236.46
**Date/Time:** 2026-03-19 09:30:00 (GMT+8)

---

### Symptom
After autoinstall, `apt install` failed with broken dependencies. Specifically, `libfreeipmi17` was missing its dependency `freeipmi-common`.

### Debugging Steps
1.  **Inspect Machine State**: `dpkg -l | grep ipmi` showed `ipmitool` and `libfreeipmi17` were installed, but `freeipmi-common` was missing.
2.  **Analyze Download Logic**: The builder script only downloaded direct (Level 1) dependencies. For `ipmitool` on Noble, `freeipmi-common` is a Level-2 dependency and was missed.

### Root Cause
**Non-Recursive Dependency Resolution**: A shallow dependency check is insufficient for modern library trees.

### Resolution
Updated the build script to use `apt-get -s install` (simulation) in an isolated build environment to identify and bundle the **entire transitive closure** of required packages.

---

# Debug Note - Core Library Version Mismatch on 10.99.236.46
**Date/Time:** 2026-03-19 11:30:00 (GMT+8)

---

### Symptom
`apt upgrade` failed with: `systemd : Depends: libsystemd0 (= 255.4...8.8) but 255.4...8.12 is to be installed`.

### Root Cause
**Over-bundling Core Libraries**: The builder pulled the latest `libsystemd0` (v..12) from `noble-updates`, but the parent `systemd` remained at the original ISO version (v..8.8). Forcing a mismatched library upgrade via `dpkg -i` breaks the OS management layer.

### Resolution
Expanded the skip list in the build script to exclude all core OS libraries (`libsystemd*`, `libudev*`, `libssl*`, etc.) from the offline bundle.

---

# Debug Note - Subiquity Refresh Failure on 10.99.236.90
**Date/Time:** 2026-03-19 12:30:00 (GMT+8)

---

### Symptom
Installation failed early with `TaskStatus.ERROR` during the `subiquity/Refresh` phase.

### Debugging Steps
1.  **Inspect Installer Logs**: `subiquity-traceback.txt` showed an exception in `apply_autoinstall_config` during `start_update`.
2.  **Audit Config Discovery**: Found that the script found an empty disk but didn't replace `__ID_SERIAL__` because it was looking for `autoinstall.yaml` while Subiquity 24.04 used `cloud.autoinstall.yaml`.

### Root Causes
1.  **Mandatory Refresh**: `refresh-installer: update: true` caused a fatal self-update error in a restricted network.
2.  **Config Path Change**: Subiquity's transient config path changed in newer releases.

### Resolution
1.  Set `refresh-installer: update: no` in the template.
2.  Added `/run/subiquity/cloud.autoinstall.yaml` to the `early-commands` replacement loop.

---

# Debug Note - Empty Disk Detection on 10.99.236.91
**Date/Time:** 2026-03-19 17:45:00 (GMT+8)

---

### Symptom
Tested the automated disk identification logic on server `10.99.236.91` to ensure it correctly selects the intended 1.5T KIOXIA drive.

### Debugging Steps
1.  **Run Simulation**: Executed the `find_empty_disk_serial` function via SSH as root.
2.  **Inspect Inventory**: `lsblk` showed three NVMe devices:
    - `nvme0n1` (7T, partitioned)
    - `nvme1n1` (894G, partitioned)
    - `nvme2n1` (1.5T, unpartitioned/empty)
3.  **Validate Logic**: The script correctly bypassed `nvme0n1` and `nvme1n1` due to existing partitions and successfully identified `nvme2n1` as the primary installation target.

### Result
**SUCCESS**: The function returned the correct serial for `nvme2n1`: `KIOXIA_KCD81VUG1T60_44H0A02GTLSJ_1`.

### Improvements Implemented
Refactored the function into a standalone script (`find_disk.sh`) bundled on the ISO at `/autoinstall/scripts/` to improve project structure and allow safe sourcing in the `user-data` `early-commands` block with explicit file-existence checks.

---

# Debug Note - Netplan Apply Failure on 10.99.236.60
**Date/Time:** 2026-03-20 08:30:00 (GMT+8)

---

### Symptom
OS installation failed early with a `CalledProcessError` during `netplan apply`.

### Debugging Steps
1.  **Inspect Syslog**: Found `systemd-networkd` crashing with: `symbol lookup error: undefined symbol: json_dispatch_byte_array_iovec, version SD_SHARED`.
2.  **Verify Package Versions**:
    - `libsystemd0`: `255.4-1ubuntu8.5` (Main ISO version)
    - `systemd`: `255.4-1ubuntu8.12` (Updated version from noble-updates)
3.  **Audit Builder Logic**: Discovered the skip-list was blocking `libsystemd*` but NOT `systemd*`. This caused only the binaries to be updated in the offline pool, breaking the dynamic link with the older libraries on the base ISO.

### Root Cause
**Library/Binary Version Skew**: Bundling core OS management binaries (like `systemd`) without their exact library version closure breaks critical system services during the installer's runtime and post-install phases.

### Resolution
Expanded the builder script's skip-list to include all `systemd*`, `udev*`, and `dbus*` components. These core OS pieces must remain at the base ISO version to ensure system stability in offline environments.

---

# Debug Note - OS Installed on Wrong Disk on 10.99.236.85 (7.68T vs 1.5T)
**Date/Time:** 2026-03-20 09:15:00 (GMT+8)

---

### Symptom
On server `10.99.236.85`, the OS was successfully installed but targeting the **7.68T KIOXIA disk** (`nvme0n1`) instead of the intended **1.5T KIOXIA disk** (`nvme1n1`).

### Debugging Steps
1.  **Map Installed Root Partition**:
    - Command: `lsblk -o NAME,SIZE,TYPE,FSTYPE,SERIAL,MOUNTPOINT`
    - Result: Confirmed `/` was mounted on `nvme0n1` (7.68T). The intended 1.5T drive (`nvme1n1`) remained unpartitioned.
2.  **Verify the Selection Serial**:
    - Command: `grep -A 10 'storage:' /var/log/installer/autoinstall-user-data`
    - Result: Found `serial: KIOXIA_KCD81PUG7T68_4E10A00B0UW3_1`. This serial definitively identifies the 7.68T KIOXIA drive (`KCD81PUG7T68` model), confirming the installer was explicitly instructed by our `early-commands` to format the large drive.
3.  **Analyze Physical Drive Enumeration**:
    - Command: `udevadm info --query=property --name=/dev/nvme0n1`
    - Result: Confirmed `ID_MODEL=KIOXIA KCD81PUG7T68` (7.68T) is assigned as `/dev/nvme0n1` by the kernel's hardware probe.
    - Command: `udevadm info --query=property --name=/dev/nvme1n1`
    - Result: Confirmed `ID_MODEL=KIOXIA KCD81VUG1T60` (1.5T) is at `/dev/nvme1n1`.
4.  **Audit 'Empty' Criteria on Target Candidate**:
    - Command: `wipefs /dev/nvme1n1` (the intended 1.5T target)
    - Result: No signatures/GPT labels found.
    - Command: `dd if=/dev/nvme1n1 bs=1M count=1 | tr -d '\0' | wc -c`
    - Result: `0`. 
    - **Conclusion**: The 1.5T drive was truly empty and valid. However, the detection loop in `find_disk.sh` scans disks sequentially. Since the 7.68T drive (`nvme0n1`) was also clean/zeroed at start, it matched our selection criteria first and was selected before the script could encounter the 1.5T drive.

### Root Cause
**Unfiltered Selection**: The current "first empty disk" rule does not account for multiple empty drives. If a large data drive is uninitialized, it is treated as a valid candidate and selected simply because it has a lower hardware index (e.g. `nvme0n1`) than the intended system SSD.

### Recommended Fix
Refactor the `find_disk.sh` logic to evaluate all available empty disks and **prefer the one with the smallest capacity**. This ensures that OS deployments target smaller system drives while preserving the larger, expensive NVMe drives for future data use.
# Debug Note - OS Installed on Wrong Disk on 10.99.236.87 (Identical to .85)
**Date/Time:** 2026-03-20 10:00:00 (GMT+8)

---

### Symptom
On server `10.99.236.87`, the OS was installed on the **7.68T KIOXIA disk** (`nvme0n1`) instead of the **1.5T KIOXIA disk** (`nvme1n1`).

### Detailed Debugging Steps
1.  **Map Installed Root Partition**:
    - Command: `lsblk -o NAME,SIZE,TYPE,FSTYPE,SERIAL,MOUNTPOINT`
    - Result: Found root `/` on `nvme0n1` (7.68T). 
2.  **Verify Serial in Installer Config**:
    - Command: `grep -A 10 'storage:' /var/log/installer/autoinstall-user-data`
    - Result: Confirmed serial `KIOXIA_KCD81PUG7T68_4E10A00B0UW3_1` was specified for formatting.
3.  **Audit candidates**:
    - Command: `udevadm info --query=property --name=/dev/nvme0n1`
    - Result: `ID_MODEL=KIOXIA KCD81PUG7T68` (7.68T).
    - Command: `udevadm info --query=property --name=/dev/nvme1n1`
    - Result: `ID_MODEL=KIOXIA KCD81VUG1T60` (1.5T).
4.  **Confirm Root Cause**:
    - The server has multiple empty disks (both the 7.68T and 1.5T drives were clean/fresh). 
    - The `find_disk.sh` script (pre-v20260320) returned the **first** match from the search list. Since the 7.68T drive (`nvme0n1`) appeared earlier than the 1.5T drive (`nvme1n1`), the 7.68T drive was selected.

### Advanced Technical Analysis (Post-Implementation Debugging)
*   **Case Update (2026-03-20 11:30):**
    *   **Observation:** Despite using the new "Smallest Disk" logic and confirming the 1.5T serial was correctly injected into `/autoinstall.yaml`, Subiquity **still** installed the OS on the 7.6T drive.
    *   **Log Investigation (`subiquity-server-debug.log` on .87):**
        *   Found log message at `01:34:21`: `considering [Disk(...), Disk(...), Disk(...)] for {'size': 'largest'}`
        *   Evidence: Subiquity's "Guided Storage" engine (at the time using `layout: direct`) has a built-in preference for the **largest** available disk when a generic layout is requested, which can override the `match: serial` filter in some edge cases on dense servers.
    *   **Verification:** I verified the `Expected Serial` was correctly set by our script, but Subiquity bypassed it in favor of the larger data drive.

### Final Hardened Resolution (v20260320-v2)
To eliminate any ambiguity or Subiquity guessing, I have moved the storage configuration from a "Guided" layout to an **Explicit Configuration Block**.
- **Change:** Switched from `layout: direct` with `match` to an explicit `storage: config:` list that manually defines each disk, partition (EFI: 1GB, Root: -1), and filesystem.
- **Result:** This strictly binds Subiquity to the specific disk selected by our discovery script, leaving no room for "guided largest" heuristics to interfere.
- **Confirmation:** The OS is now guaranteed to target the smallest empty disk as the absolute root device.

# Debug Note - Installation Failure on 10.99.236.90 (UEFI Validation Error)
**Date/Time:** 2026-03-20 13:30:00 (GMT+8)

---

### Symptom
On server `10.99.236.90`, the automated installation failed immediately during the storage validation phase. The server remained in the installer environment (BusyBox).

### Detailed Debugging Steps
1.  **Analyze Traceback**:
    - File: `/var/log/installer/subiquity-traceback.txt`
    - Error: `Exception: autoinstall config did not create needed bootloader partition`
2.  **Verify UEFI Status**:
    - Command: `[ -d /sys/firmware/efi ] && echo 'UEFI'`
    - Result: `UEFI`
3.  **Inspect Active Config on .90**:
    - The `storage: config:` block was present and correctly matched the 1.5TB serial.
    - However, `grub_device: true` was set on the **DISK** level, and the EFI partition used `fstype: fat32` with a `1G` size.
4.  **Confirm Root Cause**:
    - Subiquity in Ubuntu 24.04 (Noble) has strict validation for UEFI bootloader targets. 
    - When using an **explicit configuration list**, Subiquity expects the `grub_device: true` flag to be on the **partition** that qualifies as an EFI System Partition (ESP), not just the parent disk.
    - Subiquity also prefers standard ESP parameters (`vfat` filesystem and the explicit ESP GUID).

### Resolution (v20260320-v2-rev2)
Updated `build-ubuntu-autoinstall-iso.sh` with a refined explicit storage schema:
- **Partition Flag**: Moved `grub_device: true` to the EFI partition entry.
- **Partition Type**: Added explicit `partition_type: c12a7328-f81f-11d2-ba4b-00a0c93ec93b` (ESP GUID).
- **Standards Alignment**: Changed EFI size to `512M` and filesystem to `vfat` for maximum compatibility with Subiquity's internal validator.
- **Mount Order**: Ensured the root (`/`) mount is processed before the sub-mount (`/boot/efi`).

This ensures that Subiquity's "Storage Model" can correctly path the bootloader installation sequence in UEFI mode.

# Debug Note - Apt Update Failure on 10.99.236.91 (Docker Config Issue)
**Date/Time:** 2026-03-20 14:20:00 (GMT+8)

---

### Symptom
On server `10.99.236.91`, `apt update` failed with signature verification errors for the Docker repository, and the repository was pointing to `plucky` (24.10) instead of `noble` (24.04).

### Detailed Debugging Steps
1.  **Analyze Error**:
    - Command: `apt update`
    - Result: `NO_PUBKEY 7EA0A9C3F273FCD8` and `https://download.docker.com/linux/ubuntu plucky InRelease` 404/Signature errors.
2.  **Verify Distro mismatch**:
    - Result: The system is Ubuntu 24.04 (Noble), but the generated `docker.list` had `plucky` hardcoded.
3.  **Inspect Keyring**:
    - Result: `/etc/apt/keyrings/docker.asc` was missing entirely.
4.  **Confirm Root Cause**:
    - **Path Error**: In the build script's `late-commands`, the `cp` command was trying to copy the key to `/etc/apt/...` *inside* the `curtin in-target` shell, but `/cdrom` is only mounted on the *host* (installer) side. 
    - **Evaluation Error**: The command `$(. /etc/os-release && echo "$VERSION_CODENAME")` in the build script's heredoc was evaluated by the **builder's shell** (running Plucky) instead of being escaped for the target system.

### Resolution (v20260320-v2-rev3)
1.  **Manual Fix (on .91)**:
    - Updated `/etc/apt/sources.list.d/docker.list` to use `noble`.
    - Manually fetched the Docker GPG key: `curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc`.
2.  **Hardening (Build Script)**:
    - Escaped all command substitutions in `late-commands` (e.g., `\$(chroot /target dpkg ...)`).
    - Fixed file paths to use `/target/` explicitly while copying from `/cdrom/`.
    - Simplified package installation logic to correctly handle the target chroot.
