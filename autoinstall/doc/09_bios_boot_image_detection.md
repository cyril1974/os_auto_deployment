# BIOS Boot Image Detection

## Problem
Different Ubuntu versions use different BIOS bootloaders. 20.04+ typically use GRUB-based `eltorito.img`, while older versions (like 18.04.6) use `isolinux/isolinux.bin`. Hardcoding one path broke compatibility with the other.

## Solution
Implemented dynamic discovery of the BIOS boot image within the extracted ISO content.

### Key Changes
-   **Probing Logic**: Added checks for both `boot/grub/i386-pc/eltorito.img` and `isolinux/isolinux.bin`.
-   **Dynamic Xorriso Args**: If ISOLINUX is detected, the script automatically adds `-b isolinux/isolinux.bin -c isolinux/boot.cat` to the `xorriso` command line.

### Code Reference
```bash
if [ -f "$WORKDIR/boot/grub/i386-pc/eltorito.img" ]; then
    BIOS_BOOT_IMG="boot/grub/i386-pc/eltorito.img"
elif [ -f "$WORKDIR/isolinux/isolinux.bin" ]; then
    BIOS_BOOT_IMG="isolinux/isolinux.bin"
fi
```
