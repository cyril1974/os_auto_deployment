# Kernel Boot Parameter Fix (boot=casper)

## Problem
Customized ISOs would frequently fail during kernel initialization with an error like `No init found. Try passing init= bootarg.` or `Target filesystem doesn't have requested /sbin/init`. This was due to the absence of the `boot=casper` parameter on the kernel command line.

## Solution
Modified the GRUB and ISOLINUX patching logic to explicitly include the `boot=casper` parameter.

### Key Changes
-   **Explicit Parameter**: Added `boot=casper` to the `linux` (GRUB) and `append` (ISOLINUX) lines.
-   **Requirement**: This parameter tells the kernel to seek and mount the `casper/filesystem.squashfs` as the Live root filesystem.

### Code Reference
```bash
linux /casper/vmlinuz boot=casper autoinstall ...
```
