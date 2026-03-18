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
