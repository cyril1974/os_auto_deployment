# ISOLINUX Patching (BIOS Boot)

## Problem
The build script originally only patched `grub.cfg`, which works for UEFI boot. However, BIOS boot uses ISOLINUX, which relied on unpatched configuration files, causing the installer to remain interactive.

## Solution
Developed a targeted patching mechanism for ISOLINUX configuration files.

### Key Changes
-   **Target Files**: Identified `txt.cfg` and `adtxt.cfg` as the primary configuration sources for ISOLINUX.
-   **Regex Matching**: Implemented a Python-based regex replacement to locate the `label live` block and update its `append` parameters while avoiding duplicate entries.

### Code Reference
```bash
pattern = r'(label\s+live\s+.*?kernel\s+/casper/vmlinuz\s+append\s+)(.*?)(\s+---)'
repl = rf'\1{boot_params} \3'
```
