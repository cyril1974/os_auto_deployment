# GRUB Font Loading Fix

## Problem
Ubuntu 18.04 ISOs often encountered a fatal GRUB error: `file '/boot/grub/font.pf2' not found`. This occurred because the default GRUB configuration required this font to render the menu, but it wasn't being copied into the custom EFI boot image.

## Solution
Ensured all GRUB assets are synchronized into the EFI image during the build process.

### Key Changes
-   **Recursive Copy**: Updated the `efi.img` creation logic to copy all files from `boot/grub/` (not just `grub.cfg`) into the image.
-   **Font Inclusion**: Specifically ensured `font.pf2` and the `fonts/` directory are preserved.

### Code Reference
```bash
# Copy all files from boot/grub/ (like grub.cfg, font.pf2)
find boot/grub -maxdepth 1 -type f -exec mcopy -i "$EFI_IMG" {} ::/boot/grub/ \;
```
