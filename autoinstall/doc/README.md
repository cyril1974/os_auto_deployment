# Ubuntu Autoinstall ISO Builder - Documentation

## Documentation Structure

This directory contains comprehensive documentation for the Ubuntu Autoinstall ISO Builder project.

### Documents

1. **[Architecture](01_architecture.md)** - System architecture, component structure, and technology stack
2. **[Workflow](02_workflow.md)** - Build process flow, installation workflow, and error handling
3. **[Development Progress](03_development_progress.md)** - Project timeline, bug fixes, and feature status
4. **[Debugging Guide](04_debugging_guide.md)** - Troubleshooting, common issues, and solutions
5. **[Build Script Modification](05_build_script_modification.md)** - OS name lookup functionality and JSON integration
6. **[Ubuntu 18.04 Compatibility](06_ubuntu_18_04_compatibility.md)** - General overview
7. **[Preseed Implementation Plan](07_preseed_implementation_plan.md)** - Architectural plan for 18.04
8. **[UEFI Boot Fix](08_uefi_boot_fix.md)** - Solving EFI path/casing issues
9. **[BIOS Boot Image Detection](09_bios_boot_image_detection.md)** - Dynamic loader discovery
10. **[GRUB Font Loading Fix](10_grub_font_loading_fix.md)** - Resolving missing font errors
11. **[Kernel Boot Parameter Fix](11_kernel_boot_parameter_fix.md)** - Setting `boot=casper`
12. **[ISOLINUX Patching (BIOS)](12_isolinux_patching_bios.md)** - Legacy bootloader customization
13. **[Preseed Support (18.04)](13_preseed_support_18_04.md)** - Legacy automation details
14. **[Legacy 18.04 Boot Fixes](14_legacy_18_04_boot_fixes.md)** - Debugging and resolving boot failures with 18.04 unattended installations
15. **[ISO Comparison & EFI Boot Fix](15_iso_comparison_and_efi_boot_fix.md)** - Deep ISO comparison, UEFI boot chain analysis, and three rounds of boot failure resolution

### Change Log

- **[Change Log](change_log.md)** - Detailed record of all project changes and modifications

## Quick Links

### For Users
- **Getting Started**: See main [README.md](../README.md) (if exists) or run `./build-ubuntu-autoinstall-iso.sh --help`
- **Common Issues**: [Debugging Guide - Common Issues](04_debugging_guide.md#common-issues--solutions)
- **Installation Logs**: [Debugging Guide - Log Files](04_debugging_guide.md#log-file-reference)

### For Developers
- **System Design**: [Architecture - Overview](01_architecture.md#overview)
- **Build Process**: [Workflow - Build Process](02_workflow.md#build-process-flow)
- **Known Issues**: [Development Progress - Known Limitations](03_development_progress.md#known-limitations)

### For Troubleshooting
- **Boot Issues**: [Debugging Guide - Issue 1 & 2](04_debugging_guide.md#issue-1-iso-not-appearing-in-uefi-boot-menu)
- **Installation Errors**: [Debugging Guide - Issue 4 & 5](04_debugging_guide.md#issue-4-cloud-init-crash---nonetype-error)
- **Diagnostic Commands**: [Debugging Guide - Quick Diagnostics](04_debugging_guide.md#quick-diagnostic-commands)

## Project Overview

The Ubuntu Autoinstall ISO Builder creates custom Ubuntu Server ISOs for fully automated installations via BMC virtual media. The system uses cloud-init's autoinstall feature with hybrid UEFI/BIOS boot support.

### Key Features
- ✅ GPT partition table for UEFI compatibility
- ✅ Hybrid BIOS/UEFI boot support
- ✅ Automated installation with no user interaction
- ✅ SSH server with key-based authentication
- ✅ Configurable user credentials
- ✅ Root access enabled
- ✅ Sudo configuration
- ✅ Optional package installation

### Technology Stack
- **Build**: bash, xorriso, mtools, mkpasswd
- **Boot**: GRUB2, El Torito, GPT/MBR
- **Install**: cloud-init, subiquity, curtin

## Document Conventions

### Diagrams
- Mermaid diagrams for visual representation
- Flowcharts for processes
- Sequence diagrams for interactions

### Code Blocks
- Bash commands with syntax highlighting
- Configuration examples
- Log output samples

### Status Indicators
- ✅ Complete/Working
- ⚠️ Warning/Caution
- ❌ Error/Failed
- 🔧 In Progress

## Contributing to Documentation

When updating documentation:
1. Keep diagrams up-to-date with code changes
2. Add new issues to debugging guide
3. Update progress tracking
4. Include examples and verification steps

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-10 | Initial documentation release |
| 1.1 | 2026-02-10 | Added OS name lookup functionality |
| 1.2 | 2026-02-23 | Added Ubuntu 18.04 compatibility fixes |
| 1.3 | 2026-02-24 | Added Preseed implementation plan for 18.04 |
| 1.4 | 2026-02-24 | Added Legacy 18.04 boot fixes documentation |
| 1.5 | 2026-02-25 | Added ISO comparison & EFI boot fix analysis, change log |

## Support

For issues or questions:
1. Check [Debugging Guide](04_debugging_guide.md)
2. Review [Development Progress](03_development_progress.md) for known issues
3. Examine log files during installation
4. Create detailed bug report with logs
