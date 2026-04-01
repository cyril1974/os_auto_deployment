# Ubuntu Autoinstall ISO Builder - Documentation

## Documentation Structure

```
doc/
├── README.md                             (this file)
├── change_log.md                         (full project changelog)
│
├── 01_overview/                          (project background & status)
│   ├── architecture.md
│   ├── workflow.md
│   ├── development_progress.md
│   └── weekly_summary_2026-03-25.md
│
├── 02_reference/                         (stable reference material)
│   ├── autoinstall_level1_keys.md
│   ├── autoinstall_storage_manual.md
│   └── architecture_diagrams.md
│
├── 03_boot_and_iso/                      (boot chain & ISO build fixes)
│   ├── uefi_boot_fix.md
│   ├── bios_boot_image_detection.md
│   ├── grub_font_loading_fix.md
│   ├── kernel_boot_parameter_fix.md
│   ├── isolinux_patching_bios.md
│   └── iso_comparison_and_efi_fix.md
│
├── 04_ubuntu_18_04_legacy/               (Ubuntu 18.04 preseed support)
│   ├── compatibility_overview.md
│   ├── preseed_implementation_plan.md
│   ├── preseed_support.md
│   └── legacy_boot_fixes.md
│
├── 05_features/                          (feature designs & implementation)
│   ├── build_script_modification.md
│   ├── apt_cache_mechanism_design.md
│   ├── offline_install_hardening.md
│   └── binaryless_ipmi_plan.md
│
├── 06_ipmi_and_telemetry/                (IPMI SEL logging & BMC telemetry)
│   ├── sel_logging_commands.md
│   ├── debug_missing_sel_logs.md
│   └── debug_missing_ip_part2.md
│
└── 07_debugging/                         (incident investigations & bug fixes)
    ├── debugging_guide.md
    ├── debug_ip_zero_awk.md
    ├── kubernetes_gpg_fix.md
    ├── debug_autoinstall_no_disk.md
    ├── debug_multipath_abi.md
    ├── codename_multiline_bug_fix.md
    └── debug_duplicate_ipmi_markers.md
```

---

## Quick Links

### For Users
- **Getting Started**: Run `./build-ubuntu-autoinstall-iso.sh --help`
- **Common Issues**: [Debugging Guide](07_debugging/debugging_guide.md)
- **Autoinstall Config Keys**: [Level-1 Keys Reference](02_reference/autoinstall_level1_keys.md)
- **Storage Config**: [Storage Manual](02_reference/autoinstall_storage_manual.md)

### For Developers
- **System Design**: [Architecture](01_overview/architecture.md)
- **Build Process**: [Workflow](01_overview/workflow.md)
- **Architecture Diagrams**: [Mermaid Charts](02_reference/architecture_diagrams.md)
- **Feature Status**: [Development Progress](01_overview/development_progress.md)

### For Troubleshooting
- **Boot Issues**: [Boot & ISO](03_boot_and_iso/) folder
- **IPMI / SEL Issues**: [IPMI & Telemetry](06_ipmi_and_telemetry/) folder
- **Installation Failures**: [Debugging](07_debugging/) folder

---

## Project Overview

The Ubuntu Autoinstall ISO Builder creates custom Ubuntu Server ISOs for fully automated
installations via BMC virtual media. The system uses cloud-init's autoinstall feature
with hybrid UEFI/BIOS boot support.

### Key Features
- ✅ GPT partition table for UEFI compatibility
- ✅ Hybrid BIOS/UEFI boot support
- ✅ Automated installation with no user interaction
- ✅ SSH server with key-based authentication
- ✅ Configurable user credentials
- ✅ Root access enabled
- ✅ Sudo configuration
- ✅ Optional package installation
- ✅ Ubuntu 18.04 legacy preseed support
- ✅ Persistent APT cache for offline installs

### Technology Stack
- **Build**: bash, xorriso, mtools, mkpasswd
- **Boot**: GRUB2, El Torito, GPT/MBR, ISOLINUX
- **Install**: cloud-init, subiquity, curtin

---

## Document Conventions

- ✅ Complete/Working
- ⚠️ Warning/Caution
- ❌ Error/Failed
- 🔧 In Progress

Diagrams use Mermaid syntax (flowcharts, sequence diagrams).
Code blocks use bash/yaml syntax highlighting.

---

## Contributing to Documentation

1. Place new docs in the appropriate subfolder
2. Use descriptive filenames without numeric prefixes
3. Keep diagrams in sync with code changes
4. Log all significant changes in `change_log.md`
