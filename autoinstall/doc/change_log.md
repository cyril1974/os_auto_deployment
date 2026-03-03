# Change Log - os_auto_deployment/autoinstall

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
