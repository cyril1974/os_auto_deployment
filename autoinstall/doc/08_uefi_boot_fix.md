# UEFI Boot Loading Fix

## Problem
Generated ISOs failed to boot on some UEFI systems with the error `Failed to open \EFI\BOOT\grubx64.efi`. This was caused by:
1.  **Path Sensitivity**: Many UEFI firmwares require the directory and filename to be exactly `\EFI\BOOT\BOOTX64.EFI`.
2.  **Case Variations**: Original ISOs used varying cases (e.g., `efi/boot` vs `EFI/BOOT`), and previous `mcopy` calls were case-sensitive.

## Solution
Implemented a robust file acquisition and placement strategy in the EFI image creation process.

### Key Changes
-   **Robust Copying**: Created a `copy_file_robust` function using `find -iname` to locate bootloaders regardless of their original casing.
-   **Standardized Paths**: Forced all bootloader files into the uppercase `::/EFI/BOOT/` directory within the FAT32 boot image.
-   **Increased Buffer**: Expanded the EFI image size to 32MB to ensure enough overhead for secondary loaders and configurations.

### Code Reference
```bash
copy_file_robust() {
  local src_pattern="$1"
  local dest_path="$2"
  # ... find -iname ...
  mcopy -v -i "$EFI_IMG" "$found_file" "$dest_path"
}
```
