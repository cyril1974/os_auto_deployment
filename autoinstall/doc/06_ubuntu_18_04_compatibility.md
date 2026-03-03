# Walkthrough: Ubuntu 18.04 Compatibility Fixes

I have successfully updated the `build-ubuntu-autoinstall-iso.sh` script to support Ubuntu 18.04.6 Live Server ISOs. Below is a summary of the fixes and verification results.

## Changes Made

### 1. Robust GRUB Configuration Patching
Updated the Python regex to handle variations in the Ubuntu menuentry text.
- **Before**: Only matched `"Try or Install Ubuntu Server"`.
- **After**: Matches both `"Try or Install Ubuntu Server"` and `"Install Ubuntu Server"`.
- Added `re.IGNORECASE` for extra robustness.

### 2. Case-Insensitive EFI File Handling
The script now searches for EFI boot files regardless of directory or file case.
- Uses `find EFI/BOOT EFI/boot` to locate `bootx64.efi`, `grubx64.efi`, etc.
- This is necessary because older ISOs often use uppercase paths.

### 3. Graceful Handling of Optional EFI Files
Modified the `mcopy` steps to continue even if certain non-essential files (like `mmx64.efi`) are missing.

### 4. Output Directory Lifecycle
Ensured the `./output_custom_iso` directory is recreated after being cleaned, preventing `xorriso` failures.

### 5. Dynamic BIOS Boot Image Detection
The script now automatically detects whether the ISO uses the newer GRUB-based boot image or the older `isolinux` format.
- Checks for `boot/grub/i386-pc/eltorito.img` first.
- Falls back to `isolinux/isolinux.bin` if the first one is missing.

## Verification Results

I ran the `os-deploy` command with the Ubuntu 18.04 ISO, and it completed successfully:

```text
[*] Patching GRUB configuration for autoinstall...
Patched 1 menuentry block(s).
[*] Rebuilding ISO...
[*] Extracting MBR from original ISO...
[*] Using MBR file: /usr/lib/ISOLINUX/isohdpfx.bin
[*] Creating EFI boot image...
[*] EFI boot image created: /tmp/efi.img
[*] Modification is ok
[*] Generate customize ISO
[*] Using BIOS boot image: isolinux/isolinux.bin
[*] Done. Autoinstall ISO created at: ./output_custom_iso/ubuntu_18.04.6_live_server_amd64_autoinstall.iso
```

### 6. Robust UEFI Boot Device Generation
I fixed a critical issue where the UEFI bootloader (Shim) could not find its next stage (GRUB) in the EFI partition.
- **Improved File Detection**: Replaced the fragile `find | xargs` logic with a robust `copy_file_robust` function that uses case-insensitive search (`-iname`).
- **Standard Casing**: Forced the use of uppercase `BOOT` directory (`/EFI/BOOT`) in the EFI FAT filesystem, which is required by many UEFI implementations.
- **Safety Measures**: Added `grub.cfg` to both `/boot/grub/` and `/EFI/BOOT/` to ensure the bootloader can find its configuration regardless of its search path.
- **Font Support**: Fixed the `font.pf2 not found` error by ensuring all assets in `boot/grub/` (specifically `font.pf2` for older Ubuntu versions) are copied into the EFI image.
- **Kernel Boot Fix**: Added the missing `boot=casper` parameter to the GRUB `linux` line. This is critical for Live ISOs (like Ubuntu 18.04.6) to find and mount the squashfs root filesystem.
- **BIOS Boot Autoinstall**: Added logic to patch the ISOLINUX configuration (`txt.cfg`) for BIOS/Legacy boot. This ensures that the `autoinstall` parameters are passed to the kernel regardless of the boot mode.
- **Preseed Support for 18.04**: Implemented a complete alternative automation path for Ubuntu 18.04 using a hybrid (Autoinstall + Preseed) approach.
    - **Version Detection**: Automatically detects 18.04 based on the ISO name.
    - **Hybrid Data Generation**: Generates both `preseed.cfg` and `user-data` to maximize compatibility with 18.04 Live's hybrid nature.
    - **Version-Specific Patching**: Uses `boot=casper`, `ds=nocloud`, and `preseed/file` parameters to ensure both UEFI and BIOS find the configuration.
- **Semicolon Escaping for GRUB**: Fixed a critical issue where semicolons in the `ds=nocloud;s=...` parameter were being interpreted by GRUB as statement separators. I've added logic to explicitly escape them as `\;` in the generated `grub.cfg`, ensuring the entire kernel command line is passed to the installer.
- **CD-ROM Scan Suppression**: Added `apt-setup/cdrom/set-first boolean false` and related directives to `preseed.cfg`. This resolves the interactive prompt "Repeat this process for the rest of the CDs in your set" that frequently blocked 18.04 automated installations.
- **Improved 18.04 Parameters**: Switched from `ds=nocloud-net` to the more robust `ds=nocloud` for local ISO media, and refined the formatting to ensure 18.04.6 Live doesn't revert to interactive mode.
- **Disabling Unattended Upgrades**: Added `updates: none` to Autoinstall and `update-policy: none` to Preseed. This prevents the installer from hanging or crashing during the post-install phase due to network security updates.
- **Clean Parameters**: Refined the patching logic to avoid duplicate parameters and ensure the correct data source syntax is used for each version.

## Verification Results

The EFI boot image contents were verified with `mdir`:
```text
Directory for ::/boot/grub
font     pf2      5004 2026-02-24  10:13 
```
The required font file is now present, and the primary boot files are correctly located:
```text
Directory for ::/EFI/BOOT
bootx64  efi    955656 2026-02-24   9:37 
grubx64  efi   1456000 2026-02-24   9:37 
```
