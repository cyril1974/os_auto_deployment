# Preseed Support for Ubuntu 18.04

This plan adds support for Ubuntu 18.04 by using the Debian Installer (d-i) preseed system, as the YAML-based autoinstall feature is only available in Ubuntu 20.04 and later.

## Proposed Changes

### [build-ubuntu-autoinstall-iso.sh](file:///AppDevelope/ClusterManagement/os_auto_deployment/autoinstall/build-ubuntu-autoinstall-iso.sh)

1.  **Version Detection**:
    *   Detect if `$OS_NAME` contains "18.04".
    *   Set a flag `IS_1804`.

2.  **Conditional Data Generation**:
    *   If `IS_1804`:
        *   Generate `preseed.cfg` with:
            *   Network/Locale settings.
            *   Partitioning (atomic).
            *   User/Root setup.
            *   Late commands for SSH config and root password.
        *   Place `preseed.cfg` at the root of the ISO work directory.
    *   Else (20.04+):
        *   Continue generating `user-data` and `meta-data` in the `/autoinstall` directory.

3.  **Boot Parameter Patching**:
    *   Modify the GRUB and ISOLINUX patching logic.
    *   If `IS_1804`:
        *   Patch boot lines to include `auto=true priority=critical preseed/file=/cdrom/preseed.cfg`.
    *   Else:
        *   Keep current `autoinstall ds=nocloud;s=...` logic.

## Verification Plan

### Automated Tests
*   Run the script with `ubuntu-18.04.6-live-server-amd64` and verify:
    *   `preseed.cfg` exists in the work directory.
    *   `grub.cfg` has the `preseed/file` parameter.
    *   `txt.cfg` (ISOLINUX) has the `preseed/file` parameter.
*   Run the script with a 22.04 ISO to ensure no regression in the autoinstall path.

### Manual Verification
*   Boot the generated 18.04 ISO and confirm it proceeds without interaction.
