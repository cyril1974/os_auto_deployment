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
