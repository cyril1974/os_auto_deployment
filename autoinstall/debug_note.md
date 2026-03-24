# Debug Note - Autoinstall Failure on 10.99.236.85 (R2520G6 Server)
**Date/Time:** 2026-03-18 10:15:00 (GMT+8)

---

### Symptom
Autoinstall completed successfully, but some packages (`ipmitool`) were left in an unconfigured state (`iU`), and others (`net-tools`) were missing. `apt update` was reported failing during the process.

### Root Cause
The **Systemd-resolved stub resolver (127.0.0.53)** does not function inside the installation target `chroot`. This breaks internet-based package management during the `curthooks` and `late-commands` phases, even when the underlying network is fully functional.

---

# Debug Note - Autoinstall Failure on 10.99.236.87 (D50DNP Server)
**Date/Time:** 2026-03-18 10:05:00 (GMT+8)

---

### Symptom
The server `10.99.236.87` (D50DNP, Sapphire Rapids) failed during the late `curthooks` stage with a `calledprocesserror` in `installing-kernel`.

### Root Causes
1.  **DNS Isolation**: The installer environment used a stub resolver (`127.0.0.53`) that does not translate successfully into the installation target chroot during the `curthooks` stage.
2.  **Package Version Mismatch**: The 22.04.5 "Jammy" ISO contains the Hardware Enablement (**HWE**) kernel (`6.8.0-40-generic`). When `kernel` is left as default, it attempts to install `linux-generic` (pointing to the older `5.15` GA kernel), which is NOT on the local disk pool and requires an internet download that failed due to the DNS issue above.

---

# Debug Note - Empty Disk Detection on 10.99.236.91
**Date/Time:** 2026-03-19 17:45:00 (GMT+8)

---

### Symptom
Tested the automated disk identification logic on server `10.99.236.91` to ensure it correctly selects the intended 1.5T KIOXIA drive.

### Result
**SUCCESS**: The function returned the correct serial for `nvme2n1`: `KIOXIA_KCD81VUG1T60_44H0A02GTLSJ_1`.

---

# Debug Note - OS Installed on Wrong Disk on 10.99.236.85 / .87 (7.68T vs 1.5T)
**Date/Time:** 2026-03-20 09:15:00 (GMT+8)

---

### Symptom
OS successfully installed but targeted the 7.68T disk (`nvme0n1`) instead of the intended 1.5T SSD.

### Resolution (v2-rev2)
Refactored `find_disk.sh` to evaluate all empty candidates and select the one with the smallest capacity. Switched from `layout: direct` to an **explicit storage configuration list**. This strictly binds the installer to the discovered serial, bypassing Subiquity's "guided largest" heuristics.

---

# Debug Note - Installation Failure on 10.99.236.90 (UEFI Validation Error)
**Date/Time:** 2026-03-20 13:30:00 (GMT+8)

---

### Symptom
Installation failed storage validation with: `Exception: autoinstall config did not create needed bootloader partition`.

### Resolution (v2-rev2)
Updated the explicit storage schema:
- **Partition Flag**: Moved `grub_device: true` to the EFI partition entry.
- **Partition Type**: Added explicit ESP GUID (`c12a7328-f81f-11d2-ba4b-00a0c93ec93b`).
- **Standards**: Set EFI size to `512M` and filesystem to `vfat`.

---

# Debug Note - Apt Update Failure on 10.99.236.91
**Date/Time:** 2026-03-20 14:20:00 (GMT+8)

---

### Symptom
`apt update` failed with signature errors for Docker/K8s.

### Diagnosis
Found `signed-by=/target/etc/apt/...` paths in `.list` files. Replaced with correct relative paths. Verified functional repository synchronization.

---

# Debug Note - Installation failure on 10.99.236.92 (E7142)
**Date/Time:** 2026-03-23 09:30:00 (GMT+8)

---

### Symptom
Installation crashed in `late-commands` (status 2); ISO generation subsequently failed on the builder with "unbound variable" errors.

### Diagnosis
1.  **Late-Commands Error**: Invalid `apt-get --target=/target` flag used inside a chroot.
2.  **Builder Crash**: Unescaped `$(chroot /target ...)` substitutions in the template were executed by the host shell at Master-time.

### Resolution (v2-rev4)
Thoroughly escaped all `\$` and `\$(...)` in the `user-data` heredoc for deferred evaluation on the target. Cleaned up host/target process isolation.

---

# Debug Note - Apt Update Failure on 10.99.236.94
**Date/Time:** 2026-03-23 09:45:00 (GMT+8)

---

### Symptom
`apt update` failed with signature verification errors for Docker/K8s.

### Diagnosis
Found `/etc/apt/keyrings/` was empty because the installer tried to write to a recursive `/target/target/` path during mastering. Also found redundant `/target/` prefixes in source lists.

### Resolution (v2-rev4)
Manually fixed paths and keys on server. Permanent fix implemented in build script via correct escaping and pathing.

---

# Debug Note - ISO Generation Failure (Missing Directory)
**Date/Time:** 2026-03-23 10:00:00 (GMT+8)

---

### Symptom
Builder failed with `curl: (23) client returned ERROR` and `gpg: can't create ... : No such file or directory`.

### Root Cause
The script attempted to save GPG keys to `/autoinstall/` before the directory was created in the workdir.

### Resolution (v2-rev5)
Added `mkdir -p "$workdir/autoinstall"` at the start of the `download_extra_packages` function. Validated correct pathing for all master assets.

---

# Debug Note - Partial Apt Failure on 10.99.236.88
**Date/Time:** 2026-03-23 10:35:00 (GMT+8)

---

### Symptom
`apt update` succeeded for Docker but failed for Kubernetes (`NO_PUBKEY 234654DA9A296436`).

### Diagnosis
Audit of `/etc/apt/sources.list.d/`:
- `docker.list`: `signed-by=/etc/apt/keyrings/...` (**Correct**)
- `kubernetes.list`: `signed-by=/target/etc/apt/keyrings/...` (**Incorrect**)

### Root Cause (v2-rev4 regression)
The Docker entry was successfully updated to use relative paths, but the Kubernetes `echo` line was skipped in the previous hardening sweep.

### Resolution (v2-rev6)
1.  **Manual Fix**: Corrected path on `.88` using `sed`.
2.  **Permanent Fix**: Updated `build-ubuntu-autoinstall-iso.sh` (Line 621) to remove the remaining `/target/` prefix from the Kubernetes configuration.

---

# Debug Note - Missing SEL IP Part 2 on 10.99.236.85
**Date/Time:** 2026-03-24 08:30:00 (GMT+8)

---

### Symptom
SEL logs showed "Install Starting" and "Install Completed" but skipped the second half of the IP address (Data1=0x02). Entry `F02EC55` was missing.

### Diagnosis
Audit of `/var/log/installer/subiquity-server-debug.log`:
Consecutive `ipmitool` commands for IP Part 2 and Completion signal were sent with a **1ms gap**. Manual testing confirmed the raw command works on root shell.

### Root Cause (v2-rev13)
The BMC (Mitac G6) cannot process back-to-back SEL writes using the same Marker ID (0x02) at such high speeds; the second command collides with the first in the NVM buffer.

### Resolution (v2-rev15)
1.  **Fix**: Added `sleep 5` between each IPMI RAW call in `late-commands`.
2.  **Verification**: Continuous logging on `.85` now shows all three segments reliably.

---

# Debug Note - Script Crash during ISO Mastering
**Date/Time:** 2026-03-24 09:15:00 (GMT+8)

---

### Symptom
The `build-ubuntu-autoinstall-iso.sh` crashed with `BASE_DIR: unbound variable`.

### Diagnosis
`set -u` (strict mode) caught an uninitialized global variable used in a `cp` command within the `download_extra_packages` function.

### Root Cause (v2-rev14 regression)
The newly introduced `ipmi_start_logger.py` copy logic used `BASE_DIR` instead of a resolved local path.

### Resolution (v2-rev16)
1.  **Fix**: Specifically defined `SCRIPT_DIR` at the script header using `cd $(dirname $0)` to ensure canonical path resolution.
2.  **Fix**: Corrected the source path for `ipmi_start_logger.py`.

---

# Debug Note - Python Traceback (struct.error) in ipmi_start_logger.py
**Date/Time:** 2026-03-24 10:10:00 (GMT+8)

---

### Symptom
The `ipmi_start_logger.py` utility failed with a Python traceback during `early-commands`:
`struct.error: argument for 's' must be a bytes object`.

### Diagnosis
The script used manual `struct.pack` calls to build the `ipmi_system_interface_addr` and `ipmi_req` structures. Under Python 3's `struct` module, the "s" (bytes) and "P" (void pointer) formatting requires exact byte-object alignment which is sensitive to OS and CPU architecture.

### Root Cause (v2-rev14 regression)
Manual byte-packing in Python 3 is unreliable for complex C-structures containing nested pointers (like `struct ipmi_req msg`). The alignment for the `addr` buffer was incorrectly specified in the format string.

### Resolution (v2-rev17)
1.  **Refactor**: Replaced `struct.pack` with **`ctypes.Structure`** for `IPMIReq`, `IPMIMsg`, and `IPMISystemInterfaceAddr`.
2.  **Benefit**: `ctypes` handles the underlying C-style pointer mapping (void*) to Python's memory buffer automatically, ensuring binary compatibility with the Linux kernel driver across all platforms.

---

# Debug Note - [Errno 22] IOCTL Failure on 10.99.236.91
**Date/Time:** 2026-03-24 11:15:00 (GMT+8)

---

### Symptom
The updated `ipmi_start_logger.py` (v2-rev17-19) failed to emit a Start signal on node `.91`, reporting `[Errno 22] Invalid argument` in the IOCTL call.

### Diagnosis
1.  **Verification**: Manual `ipmitool raw` worked, confirming the BMC and driver were functional.
2.  **Forensics**: Ran `strace -e ioctl -v ipmitool raw ...` and confirmed the `IPMICTL_SEND_COMMAND` IOCTL was being used correctly by the system.
3.  **Probing**: A custom scanner script tested multiple NetFn (shifted vs non-shifted) and Address Channel (0x00 vs 0x0F) combinations.

### Root Cause (v2-rev20 hardware variance)
Node `.91` (and potentially other servers in the cluster) requires **Channel 15 (0x0f)** and a **Raw (Non-shifted) NetFn (0x0a)** to communicate with the BMC through the Linux `devintf` driver. Our previous iteration hardcoded Channel `0x00` and shifted NetFn `0x28`.

### Resolution (v2-rev20)
1.  **Hardening**: Updated `ipmi_start_logger.py` to become a "smart probe".
2.  **Implementation**: It now attempts to send the marker by iterating through multiple permutations of Channels (0x00, 0x0F) and NetFn formats (0x0a, 0x28).
3.  **Validation**: Successfully established telemetry on `.91` using **NetFn=0x0a** and **Channel=0x0f**.
