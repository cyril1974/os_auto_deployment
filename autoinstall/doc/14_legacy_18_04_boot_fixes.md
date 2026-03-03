# Legacy 18.04 ISO Boot Fixes

**Date:** 2026-02-24
**Subject:** Debugging and resolving boot failures with Ubuntu 18.04 fully unattended installations.

## Overview
Automating the installation of Ubuntu 18.04 requires distinct approaches compared to 20.04+ versions due to the transitional nature of installers during the 18.04 lifecycle. Several underlying issues in the build process caused boot failures, interactive installer prompts, and silent crashes when attempting to automate 18.04. This document records the four primary issues encountered, their root causes, and resolutions. 

---

### Issue 1: Installer Falling back to Interactive Mode
**Symptom:** The installer logs (`subiquity-server-debug.log`) showed warnings like `skipping Filesystem as interactive` and `skipping Identity as interactive`, dropping the user into the manual installation menu despite the injection of an `autoinstall` cloud-config `user-data` file.
**Root Cause:** The `ubuntu-18.04.6-live-server-amd64.iso` uses an early version of the Subiquity installer. This version does not fully support the modern `#cloud-config autoinstall` schema (introduced officially in 20.04). Additionally, this `live-server` ISO does not fall back to parsing `preseed.cfg`.
**Resolution:** We must use the traditional, non-live "legacy" server ISO: **`ubuntu-18.04.6-server-amd64.iso`**. This ISO uses the classic `debian-installer` (d-i) which natively and robustly supports automated installations using `preseed.cfg`.

---

### Issue 2: GRUB Error "file '/install/vmlinuz' not found"
**Symptom:** After switching to the legacy server ISO, the EFI boot sequence paused at GRUB with the error `file '/install/vmlinuz' not found`.
**Root Cause:** The `live-server` ISOs (20.04+) place the kernel at `/casper/vmlinuz`. The legacy server ISOs (18.04) place the kernel at `/install/vmlinuz`. The `build-ubuntu-autoinstall-iso.sh` Python regex logic was hardcoded to search for and replace `linux /casper/vmlinuz`. Because it failed to patch `/install/vmlinuz` correctly, it passed invalid paths to the bootloader.
**Resolution:** Updated the regex logic in Python to perform conditional patching based on `$IS_1804`:
- If building 18.04, target and patch `/install/vmlinuz` and `/install/initrd.gz`.
- If building 20.04+, target and patch `/casper/vmlinuz` and `/casper/initrd`.

---

### Issue 3: GRUB Still Cannot Find the Kernel (EFI Partition Traps)
**Symptom:** Even after correcting the kernel paths to `/install/vmlinuz`, GRUB still reported the file could not be found. 
**Root Cause:** When booting via UEFI, the system initially boots from the small, 32MB FAT partition (`efi.img`). Because the `search` command was omitted from the 18.04 GRUB menu entry during the regex replacement, GRUB tried to load `/install/vmlinuz` from within the 32MB EFI partition instead of the main ISO ISO9660 filesystem. 
**Resolution:** Reinserted the `search --no-floppy --set=root --file /install/vmlinuz` command into the 18.04 GRUB `menuentry`. This explicitly tells GRUB to scan all attached volumes, locate the volume holding the kernel, and switch its root pointer to that filesystem before attempting to load the kernel image.

---

### Issue 4: Silent Freeze/Black Screen on Boot
**Symptom:** The ISO would not boot, presenting a solid black screen instantly without entering the GRUB menu or showing kernel logs.
**Root Cause:** Modern ISOs (20.04+) expect `xorriso` to build a **GPT** partition table with an appended EFI partition. However, the legacy 18.04 internal bootloader (`grubx64.efi`) strictly expects a backward-compatible **MBR-Hybrid** layout. Because it could not parse the GPT partition geometry, it failed silently before loading the UI.
**Resolution:** Branched the Xorriso build arguments in `build-ubuntu-autoinstall-iso.sh`. 
- If `$IS_1804` is true, Xorriso now repacks the CD-ROM using traditional El-Torito properties (`-isohybrid-mbr`, `-isohybrid-gpt-basdat`). 
- If false, Xorriso utilizes the modern GPT appended partition (`-appended_part_as_gpt`). 
This guarantees legacy bootloader compatibility on older images while retaining modern layouts for new ones.
