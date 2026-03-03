# Preseed Support (Ubuntu 18.04)

## Problem
Ubuntu 18.04 DOES NOT support the modern `autoinstall` YAML configuration (introduced in 20.04). Attempting to use the `ds=nocloud` kernel parameter results in an interactive installer.

## Solution
Built a dedicated Preseed (Debian Installer) automation path for legacy ISOs.

### Key Changes
-   **Version Detection**: The script now parses the `OS_NAME` to determine if a Preseed-based installer is required.
-   **Preseed Generation**: Automatically generates a `preseed.cfg` if 18.04 is detected, covering disk partitioning, user creation, and late-stage SSH configuration.
-   **Boot Parameters**: Switches from `autoinstall` parameters to `auto=true priority=critical preseed/file=/cdrom/preseed.cfg` when in 18.04 mode.

### Logic Summary
```bash
if [ "$IS_1804" = true ]; then
  # Generate preseed.cfg
else
  # Generate user-data/meta-data
fi
```
